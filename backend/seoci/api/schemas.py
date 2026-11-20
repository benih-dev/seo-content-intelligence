from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str
    niche: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    language: str = "id"
    country: str = "ID"
    voice_profile: str = "clear, practical, helpful"
    rules: dict = Field(default_factory=dict)
    business_objective: str = "Educate readers"

    @field_validator("name", "niche", "audience", mode="before")
    @classmethod
    def strip_required(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("domain")
    @classmethod
    def domain_valid(cls, value):
        value = value.strip()
        if "://" not in value:
            value = f"https://{value}"
        parsed = urlparse(value)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname or
                parsed.username is not None or parsed.password is not None or
                (parsed.port is not None and parsed.port <= 0) or
                any(char.isspace() for char in value)):
            raise ValueError("Enter a website domain such as example.com or https://example.com")
        return value.rstrip("/")

    @field_validator("language", "country")
    @classmethod
    def locale_valid(cls, value):
        if not value.isalpha() or len(value) not in {2, 3}:
            raise ValueError("Use ISO language/country code")
        return value


class RunInput(BaseModel):
    project_id: str
    mode: Literal["selected", "discovery"] = "selected"
    primary_keyword: str = Field(min_length=2, max_length=200)
    locale: str | None = None

    @field_validator("primary_keyword")
    @classmethod
    def keyword_valid(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Keyword is empty")
        return value


class ApprovalInput(BaseModel):
    stage: Literal["keyword", "brief", "final"]
    decision: Literal["approve", "request_revision"] = "approve"
    payload: dict = Field(default_factory=dict)
    comment: str = ""


class ContentItemInput(BaseModel):
    url: str
    title: str = ""
    slug: str = ""
    status: str = "published"
    metadata_json: dict = Field(default_factory=dict)


class InventoryInput(BaseModel):
    items: list[ContentItemInput] = Field(max_length=200)


class SitemapInput(BaseModel):
    url: str


class DraftInput(BaseModel):
    body_md: str = Field(min_length=1)
    metadata_json: dict | None = None
