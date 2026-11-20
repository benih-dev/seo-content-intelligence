from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

from seoci.providers.network import request, safe_url


def project_url(url, domain):
    try:
        parsed = urlparse(url)
        valid = (
            parsed.scheme in {"http", "https"} and parsed.hostname
            and parsed.username is None and parsed.password is None
            and (parsed.port is None or parsed.port > 0)
            and not any(char.isspace() for char in url)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Enter a complete URL starting with https:// or http://")
    if parsed.hostname.removeprefix("www.") != urlparse(domain).hostname.removeprefix("www."):
        raise ValueError("URL must belong to the project website")
    return parsed


def fetch_sitemap(url, domain):
    seen = set()
    for _ in range(6):
        project_url(url, domain)
        if url in seen:
            break
        seen.add(url)
        try:
            response = request("GET", safe_url(url), allow_redirect_response=True)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {404, 410}:
                raise ValueError("Sitemap not found. Check the XML sitemap URL and try again.") from exc
            raise ValueError(f"The website returned HTTP {status}. Check that the sitemap is public.") from exc
        except (httpx.RequestError, OSError) as exc:
            raise ValueError("Could not reach the sitemap. Check the URL and try again.") from exc
        if not response.has_redirect_location:
            return response.content
        url = urljoin(url, response.headers["location"])
    raise ValueError("Sitemap redirects too many times. Try the final sitemap URL directly.")


def import_sitemap(url, domain, max_urls=200):
    items, failures, seen = {}, [], set()

    def walk(current, depth=0):
        if current in seen or depth > 3 or len(seen) >= 20 or len(items) >= max_urls:
            return
        seen.add(current)
        try:
            content = fetch_sitemap(current, domain)
            if len(content) > 2_000_000:
                raise ValueError("Sitemap too large")
            root = ElementTree.fromstring(content)
            kind = root.tag.rsplit("}", 1)[-1]
            if kind not in {"sitemapindex", "urlset"}:
                raise ValueError("This URL does not contain an XML sitemap. Use a sitemap index or URL set.")
        except (ElementTree.ParseError, LookupError):
            failures.append({"url": current, "error": "This URL did not return a valid XML sitemap."})
            return
        except ValueError as exc:
            failures.append({"url": current, "error": str(exc)})
            return
        tag = "sitemap" if kind == "sitemapindex" else "url"
        for entry in root.findall(f"{{*}}{tag}")[:max_urls]:
            loc = (entry.findtext("{*}loc") or "").strip()
            if not loc or loc in items:
                continue
            if kind == "sitemapindex":
                walk(loc, depth + 1)
            else:
                try:
                    project_url(loc, domain)
                except ValueError as exc:
                    failures.append({"url": loc, "error": str(exc)})
                    continue
                item = {"url": loc}
                lastmod = (entry.findtext("{*}lastmod") or "").strip()
                if lastmod:
                    item["metadata_json"] = {"sitemap_lastmod": lastmod}
                items[loc] = item
            if len(items) >= max_urls:
                break

    walk(url)
    return {"items": list(items.values()), "failures": failures}
