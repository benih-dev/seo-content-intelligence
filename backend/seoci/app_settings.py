import os
from dataclasses import dataclass, field

from sqlalchemy import select

from seoci.config import settings
from seoci.db import Session
from seoci.models import AppSetting

PUBLIC_FIELDS = ("llm_model", "llm_api_base", "serp_provider", "dataforseo_login", "github_api_url")
SECRET_FIELDS = ("llm_api_key", "dataforseo_password", "github_token")
SETTING_FIELDS = (*PUBLIC_FIELDS, *SECRET_FIELDS)


@dataclass(repr=False)
class ResolvedSettings:
    values: dict = field(repr=False)
    sources: dict = field(repr=False)

    def public(self):
        return {**{key: self.values[key] for key in PUBLIC_FIELDS},
                **{key: {"configured": bool(self.values[key]), "source": self.sources[key]} for key in SECRET_FIELDS},
                "modes": {"llm": "live" if self.values["llm_model"] else "mock", "serp": self.values["serp_provider"]}}


def resolve_settings(db=None):
    if db is None:
        with Session() as session:
            return resolve_settings(session)
    saved = dict(db.execute(select(AppSetting.key, AppSetting.value)).all())
    values = {key: saved[key] if key in saved else getattr(settings, key) for key in SETTING_FIELDS}
    if "llm_api_key" not in saved and not values["llm_api_key"]:
        model = values["llm_model"]
        provider_key = "ANTHROPIC_API_KEY" if model.startswith(("anthropic/", "claude")) else "OPENAI_API_KEY" if model.startswith(("openai/", "gpt-", "o1", "o3", "o4")) else None
        if provider_key:
            values["llm_api_key"] = os.environ.get(provider_key, "")
    sources = {key: "db" if key in saved else "env" if values[key] else "none" for key in SECRET_FIELDS}
    return ResolvedSettings(values, sources)
