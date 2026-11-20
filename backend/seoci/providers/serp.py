from typing import Protocol

from seoci.app_settings import resolve_settings
from seoci.diagnostics import classify, ProviderFailure, observed
from seoci.models import now
from seoci.providers.demo_topics import topic_sources
from seoci.providers.network import cached, dfs, dfs_location, request


class SerpProvider(Protocol):
    def search(self, query: str, locale: str, device: str = "desktop") -> dict: ...


class MockSerp:
    def search(self, query, locale, device="desktop"):
        sources = topic_sources(query)
        if sources:
            return {"query": query, "locale": locale, "device": device, "provider": "mock", "captured_at": now(),
                    "mock": True, "results": [{"rank": i + 1, **source} for i, source in enumerate(sources)]}
        return {"query": query, "locale": locale, "device": device, "provider": "mock",
                "captured_at": now(), "mock": True, "results": [
                    {"rank": 1, "url": "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
                     "title": "Sample reference: Creating helpful content (not a competitor)", "snippet": "Offline SEO documentation example, not a search result for this keyword."},
                    {"rank": 2, "url": "https://developers.google.com/search/docs/fundamentals/seo-starter-guide",
                     "title": "SEO Starter Guide", "snippet": "Use descriptive titles and organize information clearly for readers."}]}


class DataForSEOSerp:
    def search(self, query, locale, device="desktop"):
        language, country = locale.split("-", 1)
        def fetch():
            result = dfs("serp/google/organic/live/advanced", {"keyword": query, **dfs_location(country),
                         "language_code": language, "device": device, "depth": 10})
            items = result[0].get("items", []) if result else []
            rows = [{"rank": x["rank_group"], "url": x["url"], "title": x["title"],
                     "snippet": x.get("description", "")} for x in items if x.get("type") == "organic"]
            if not rows:
                raise RuntimeError("SERP returned no organic results; retry or change query")
            return {"query": query, "locale": locale, "device": device, "provider": "dataforseo", "captured_at": now(), "results": rows}
        return cached("dataforseo-serp", query, locale, device, fetch)


class SerperSerp:
    @observed("Serper", endpoint="https://google.serper.dev")
    def search(self, query, locale, device="desktop"):
        language, country = locale.split("-", 1)
        def fetch():
            config = resolve_settings().values
            if not config["serper_api_key"]:
                raise RuntimeError("Serper API key is not configured")
            try:
                data = request("POST", "https://google.serper.dev/search",
                               headers={"X-API-KEY": config["serper_api_key"]},
                               json={"q": query, "gl": country.lower(), "hl": language.lower(), "num": 10}).json()
                rows = [{"rank": item.get("position", index + 1), "url": item["link"],
                         "title": item["title"], "snippet": item.get("snippet", "")}
                        for index, item in enumerate(data.get("organic", []))]
                if not rows:
                    raise ValueError("No organic results")
                return {"query": query, "locale": locale, "device": device, "provider": "serper", "captured_at": now(),
                        "results": rows, "people_also_ask": data.get("peopleAlsoAsk", []),
                        "related_searches": data.get("relatedSearches", [])}
            except Exception as exc:
                raise ProviderFailure(classify(exc, "Serper", endpoint="https://google.serper.dev")) from None
        return cached("serper-serp", query, locale, device, fetch)


def get_serp():
    return {"dataforseo": DataForSEOSerp, "serper": SerperSerp}.get(resolve_settings().values["serp_provider"], MockSerp)()
