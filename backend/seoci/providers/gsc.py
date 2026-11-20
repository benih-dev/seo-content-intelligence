import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2 import service_account

from seoci.app_settings import resolve_settings
from seoci.config import settings
from seoci.diagnostics import classify, ProviderFailure, observed
from seoci.models import now
from seoci.providers.network import cached, request

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class SearchConsoleKeywords:
    @observed("Search Console", endpoint="https://www.googleapis.com")
    def rows(self, query=None):
        config = resolve_settings().values
        site = config["gsc_site_url"]
        raw = config["gsc_service_account_json"]
        if not site or not raw:
            raise RuntimeError("Search Console requires a site URL and service-account JSON")
        end = datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=1)
        start = end - timedelta(days=89)
        period = f"{start.isoformat()} to {end.isoformat()}"

        def fetch():
            try:
                info = {**json.loads(raw), "token_uri": "https://oauth2.googleapis.com/token"}
                credentials = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
                transport = Request()

                def refresh_request(url, method="GET", body=None, headers=None, **kwargs):
                    return transport(url, method=method, body=body, headers=headers, timeout=settings.network_timeout)

                credentials.refresh(refresh_request)
                payload = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                           "dimensions": ["query"], "rowLimit": 10 if query is None else 1}
                if query is not None:
                    payload["dimensionFilterGroups"] = [{"filters": [{"dimension": "query", "operator": "equals", "expression": query}]}]
                response = request("POST", "https://www.googleapis.com/webmasters/v3/sites/" + quote(site, safe="") + "/searchAnalytics/query",
                                   headers={"Authorization": "Bearer " + credentials.token}, json=payload).json()
                rows = response.get("rows", [])
                rows = sorted(rows, key=lambda row: row.get("clicks", 0), reverse=True)
                return {"rows": rows, "period": period}
            except Exception as exc:
                raise ProviderFailure(classify(exc, "Search Console", endpoint="https://www.googleapis.com")) from None

        identity = hashlib.sha256(raw.encode()).hexdigest()
        return cached("search-console", [site, identity, period, query], "own-site", "all", fetch)

    def suggestions(self, seed, locale):
        queries = [row["keys"][0] for row in self.rows()["rows"] if row.get("keys")]
        if not queries:
            raise RuntimeError("No Search Console queries found for this property in the last 90 days")
        return queries

    def metrics(self, keywords, locale):
        metrics = {}
        for keyword in keywords:
            data = self.rows(keyword)
            row = next((row for row in data["rows"] if row.get("keys") == [keyword]), {})
            metrics[keyword] = {"volume": None, "competition": None, "provider": "search_console",
                                "provenance": "Search Console (own site)", "locale": "own-site (all countries/languages)",
                                "period": data["period"], "captured_at": now(),
                                "status": "available" if row else "unavailable", "confidence": .4,
                                "clicks": row.get("clicks"), "impressions": row.get("impressions"),
                                "ctr": row.get("ctr"), "position": row.get("position"),
                                "note": "Own-site impressions, not search volume." if row else
                                "Query not found in Search Console for this property in the last 90 days; no metrics available."}
        return metrics
