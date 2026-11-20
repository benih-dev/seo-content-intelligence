import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class PublishingConfig(BaseModel):
    github_repo: str = ""
    base_branch: str = Field(default="main", min_length=1)
    content_dir: str = "src/content/blog"
    file_extension: Literal["md"] = "md"

    @field_validator("github_repo")
    @classmethod
    def repo_valid(cls, value):
        if value and not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", value):
            raise ValueError("github_repo must be owner/name")
        return value

    @field_validator("content_dir")
    @classmethod
    def directory_valid(cls, value):
        if not value or value.startswith("/") or "\\" in value or any(part in {"", ".", ".."} for part in value.split("/")) or ":" in value:
            raise ValueError("content_dir must be a relative path without '..'")
        return value


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str
    niche: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    language: str = "id"
    country: str = "ID"
    voice_profile: str = "clear, practical, helpful"
    rules: dict = Field(default_factory=dict)
    publishing: PublishingConfig = Field(default_factory=PublishingConfig)
    business_objective: str = "Educate readers"

    @field_validator("domain")
    @classmethod
    def domain_valid(cls, value):
        if urlparse(value).scheme not in {"https", "http"} or not urlparse(value).hostname:
            raise ValueError("domain must be a full HTTP(S) URL")
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
