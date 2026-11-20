from typing import Protocol

from seoci.config import settings
from seoci.models import now
from seoci.providers.demo_topics import topic_sources
from seoci.providers.network import cached, dfs, dfs_location


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


def get_serp():
    return DataForSEOSerp() if settings.serp_provider == "dataforseo" else MockSerp()
