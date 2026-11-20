import re
import httpx
from html import unescape
from urllib.parse import urlparse

from seoci.models import now
from seoci.providers.network import request, safe_url
from seoci.providers.serp import get_serp


def untrusted(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return "<untrusted_source>" + unescape(text).replace("<", "&lt;").replace(">", "&gt;")[:6000] + "</untrusted_source>"


class ResearchProvider:
    def find_sources(self, queries, locale, fetch_pages=False):
        sources = {}
        for query in queries[:3]:
            snapshot = get_serp().search(query, locale)
            for row in snapshot["results"][:5]:
                text = row["snippet"]
                if fetch_pages:
                    try:
                        text += " " + request("GET", safe_url(row["url"])).text[:100000]
                    except (ValueError, OSError, RuntimeError, httpx.HTTPError):
                        pass
                sources[row["url"]] = {**row, "publisher": urlparse(row["url"]).hostname,
                    "published_at": None, "retrieved_at": now(), "snippet": untrusted(text),
                    "mock": snapshot.get("mock", False)}
        return list(sources.values())
