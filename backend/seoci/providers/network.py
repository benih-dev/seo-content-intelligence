import hashlib
import ipaddress
import json
import socket
import time
from contextvars import ContextVar
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from seoci.config import settings
from seoci.db import Session
from seoci.models import ResponseCache

active_session = ContextVar("provider_session", default=None)


def safe_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) URLs are allowed")
    for addr in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        if not ipaddress.ip_address(addr[4][0]).is_global:
            raise ValueError("Private/reserved network URLs are forbidden")
    return url


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, max=2),
       retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)), reraise=True)
def request(method, url, **kwargs):
    with httpx.Client(timeout=settings.network_timeout, follow_redirects=False) as client:
        response = client.request(method, url, **kwargs)
        response.raise_for_status()
        return response


def cached(provider, query, locale, device, fetch):
    key = hashlib.sha256(json.dumps([provider, query, locale, device], sort_keys=True).encode()).hexdigest()
    def resolve(db):
        row = db.scalar(select(ResponseCache).where(ResponseCache.key == key))
        if row and row.expires_at > time.time():
            return row.data
        data = fetch()
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
        statement = insert(ResponseCache).values(key=key, data=data, expires_at=time.time() + settings.cache_ttl_seconds)
        db.execute(statement.on_conflict_do_update(index_elements=[ResponseCache.key],
                   set_={"data": statement.excluded.data, "expires_at": statement.excluded.expires_at}))
        if row:
            db.expire(row)
        return data
    if active_session.get() is not None:
        return resolve(active_session.get())
    with Session() as db:
        data = resolve(db)
        db.commit()
        return data


def dfs(endpoint, payload):
    data = request("POST", "https://api.dataforseo.com/v3/" + endpoint,
                   auth=(settings.dataforseo_login, settings.dataforseo_password), json=[payload]).json()
    tasks = data.get("tasks") or []
    if not tasks or tasks[0].get("status_code") != 20000:
        raise RuntimeError("DataForSEO task failed: " + str(data.get("status_message", tasks[0].get("status_message") if tasks else "no tasks")))
    return tasks[0].get("result") or []


def dfs_location(country, family="serp/google"):
    if len(country) != 2:
        return {"location_name": country}
    def fetch():
        data = request("GET", f"https://api.dataforseo.com/v3/{family}/locations/{country.lower()}",
                       auth=(settings.dataforseo_login, settings.dataforseo_password)).json()
        tasks = data.get("tasks") or []
        if not tasks or tasks[0].get("status_code") != 20000:
            raise RuntimeError("DataForSEO location lookup failed")
        locations = tasks[0].get("result") or []
        row = next((x for x in locations if x.get("country_iso_code", "").upper() == country.upper()
                    and x.get("location_type", "").lower() == "country"), None)
        if not row:
            raise ValueError(f"Unsupported DataForSEO country: {country}")
        return {"location_code": row["location_code"]}
    return cached(f"{family}-location", country.upper(), "", "", fetch)
