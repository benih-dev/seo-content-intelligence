import json
import re
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from seoci.app_settings import SETTING_FIELDS, resolve_settings
from seoci.db import Session
from seoci.models import AppSetting, AuditEvent, now


class SettingsRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                fields = sorted({str(error["loc"][1]) for error in exc.errors()
                                 if len(error["loc"]) > 1 and error["loc"][1] in SETTING_FIELDS})
                return JSONResponse(status_code=422, content={"detail": "Invalid settings fields", "fields": fields})
        return safe_handler


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_model: str | None = Field(default=None, max_length=512)
    llm_api_base: str | None = Field(default=None, max_length=2048)
    llm_api_key: SecretStr | None = Field(default=None, min_length=1, max_length=16384)
    serp_provider: Literal["mock", "dataforseo", "serper"] | None = None
    keyword_provider: Literal["", "mock", "dataforseo", "search_console"] | None = None
    serper_api_key: SecretStr | None = Field(default=None, min_length=1, max_length=16384)
    gsc_service_account_json: SecretStr | None = Field(default=None, min_length=1, max_length=65536)
    gsc_site_url: str | None = Field(default=None, max_length=2048)
    dataforseo_login: str | None = Field(default=None, max_length=512)
    dataforseo_password: SecretStr | None = Field(default=None, min_length=1, max_length=16384)
    github_token: SecretStr | None = Field(default=None, min_length=1, max_length=16384)
    github_api_url: str | None = Field(default=None, max_length=2048)

    @field_validator("llm_api_base", "github_api_url")
    @classmethod
    def valid_url(cls, value, info):
        if value is None or (value == "" and info.field_name == "llm_api_base"):
            return value
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or any(char.isspace() for char in value)):
            raise ValueError("Use an HTTP(S) URL without credentials, query or fragment")
        parsed.port
        return value.rstrip("/")

    @field_validator("gsc_site_url")
    @classmethod
    def valid_property(cls, value):
        if not value:
            return value
        if value.startswith("sc-domain:"):
            if not re.fullmatch(r"sc-domain:(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}", value):
                raise ValueError("Use a Search Console domain property")
            return value
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or any(char.isspace() for char in value)):
            raise ValueError("Use a Search Console HTTP(S) URL-prefix property")
        parsed.port
        return value

    @field_validator("gsc_service_account_json")
    @classmethod
    def valid_service_account(cls, value):
        if value is not None:
            try:
                data = json.loads(value.get_secret_value())
                if (not isinstance(data, dict) or data.get("type") != "service_account"
                        or not isinstance(data.get("client_email"), str) or "@" not in data["client_email"]
                        or not isinstance(data.get("private_key"), str) or not data["private_key"].strip()):
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError("Use a service-account JSON with client_email and private_key") from None
        return value

    @field_validator("llm_api_key", "dataforseo_password", "github_token", "serper_api_key")
    @classmethod
    def nonblank_secret(cls, value):
        if value is not None and not value.get_secret_value().strip():
            raise ValueError("Secret must not be blank")
        return value


def database():
    with Session() as db:
        yield db


router = APIRouter(route_class=SettingsRoute)


@router.get("/api/settings")
def get_settings(db=Depends(database)):
    return JSONResponse(resolve_settings(db).public(), headers={"Cache-Control": "no-store"})


@router.put("/api/settings")
def update_settings(body: SettingsUpdate, db=Depends(database)):
    changed = []
    try:
        for key in sorted(body.model_fields_set):
            value = getattr(body, key)
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            row = db.get(AppSetting, key)
            if value is None:
                if row:
                    db.delete(row)
                    changed.append(key)
            elif row is None or row.value != value:
                insert = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
                statement = insert(AppSetting).values(key=key, value=value, updated_at=now())
                db.execute(statement.on_conflict_do_update(index_elements=[AppSetting.key],
                           set_={"value": statement.excluded.value, "updated_at": statement.excluded.updated_at}))
                changed.append(key)
        if changed:
            db.add(AuditEvent(actor="user", action="settings_updated", data={"fields": changed}))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Settings could not be saved; please retry") from None
    return JSONResponse(resolve_settings(db).public(), headers={"Cache-Control": "no-store"})
