from typing import Protocol

from seoci.app_settings import resolve_settings
from seoci.models import now
from seoci.providers.network import cached, dfs, dfs_location


class KeywordProvider(Protocol):
    def suggestions(self, seed: str, locale: str) -> list[str]: ...
    def metrics(self, keywords: list[str], locale: str) -> dict: ...


class MockKeywords:
    def suggestions(self, seed, locale):
        return [seed, f"{seed} untuk pemula" if locale.startswith("id") else f"{seed} for beginners",
                f"panduan {seed}" if locale.startswith("id") else f"{seed} guide"]

    def metrics(self, keywords, locale):
        return {k: {"volume": None, "competition": None, "provider": "mock", "status": "unavailable",
                    "locale": locale, "period": "unavailable", "captured_at": now()} for k in keywords}


class DataForSEOKeywords:
    def suggestions(self, seed, locale):
        language, country = locale.split("-", 1)
        data = cached("dfs-suggestions", seed, locale, "desktop", lambda: {"items": dfs(
            "keywords_data/google_ads/keywords_for_keywords/live",
            {"keywords": [seed], "language_code": language, **dfs_location(country, "keywords_data/google_ads")})})
        return [x["keyword"] for x in data["items"][:10]] or [seed]

    def metrics(self, keywords, locale):
        language, country = locale.split("-", 1)
        data = cached("dfs-metrics", keywords, locale, "desktop", lambda: {"items": dfs(
            "keywords_data/google_ads/search_volume/live",
            {"keywords": keywords, "language_code": language, **dfs_location(country, "keywords_data/google_ads")})})
        lookup = {x["keyword"]: x for x in data["items"]}
        return {k: {"volume": lookup.get(k, {}).get("search_volume"), "competition": lookup.get(k, {}).get("competition"),
                    "provider": "dataforseo", "locale": locale, "period": "provider latest monthly average",
                    "captured_at": now(), "status": "available" if lookup.get(k, {}).get("search_volume") is not None else "unavailable"} for k in keywords}


def get_keywords():
    return DataForSEOKeywords() if resolve_settings().values["serp_provider"] == "dataforseo" else MockKeywords()
