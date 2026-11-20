from typing import Literal

from fastapi import APIRouter, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy import select

from seoci.app_settings import resolve_settings
from seoci.db import Session
from seoci.diagnostics import classify, context, protect_logging, record_event
from seoci.models import DiagnosticEvent
from seoci.providers.keywords import get_keywords
from seoci.providers.llm import LiteLLMClient
from seoci.providers.network import cache_bypassed
from seoci.providers.serp import get_serp

class DiagnosticRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Invalid diagnostics request"})
        return safe_handler


router = APIRouter(prefix="/api", route_class=DiagnosticRoute)


class Probe(BaseModel):
    reply: str


@router.get("/logs")
def logs(run_id: str | None = Query(default=None, max_length=36), level: Literal["info", "error"] | None = None):
    with Session() as db:
        query = select(DiagnosticEvent).order_by(DiagnosticEvent.created_at.desc(), DiagnosticEvent.id.desc()).limit(500)
        if run_id:
            query = query.where(DiagnosticEvent.run_id == run_id)
        if level:
            query = query.where(DiagnosticEvent.level == level)
        return [row.data for row in db.scalars(query)]


@router.post("/settings/test/{kind}")
def test_connection(kind: Literal["llm", "serp", "keyword"]):
    config = resolve_settings().values
    protect_logging(config)
    mode = resolve_settings().public()["modes"][kind]
    token = context.set({"stage": "connection_test", "run_id": None})
    cache_token = cache_bypassed.set(True)
    try:
        if kind == "llm" and config["llm_model"]:
            LiteLLMClient().complete_json("connection_test", 'Return {"reply":"ok"}.', Probe)
        elif kind == "serp":
            get_serp().search("gardening", "en-US")
        elif kind == "keyword":
            get_keywords().metrics(["gardening"], "en-US")
        message = f"{kind.upper()} connection test succeeded ({mode})."
        record_event(message=message, provider=mode, model=config["llm_model"] if kind == "llm" else "")
        return {"ok": True, "message": message, "hint": "Mock mode makes no network calls." if mode == "mock" else "Saved settings were tested. Provider usage may be billed."}
    except Exception as exc:
        error = classify(exc, mode, config["llm_model"] if kind == "llm" else "", config["llm_api_base"] if kind == "llm" else "", config)
        record_event(level="error", message=error["message"], error=error, provider=error["provider"], model=error["model"], status=error["status"])
        return {"ok": False, **error}
    finally:
        cache_bypassed.reset(cache_token)
        context.reset(token)
