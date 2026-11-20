from urllib.parse import urlparse
from xml.etree import ElementTree

from seoci.providers.network import request, safe_url


def import_sitemap(url, domain, max_urls=200):
    urls, failures, seen = [], [], set()
    def walk(current, depth=0):
        if current in seen or depth > 3 or len(seen) >= 20:
            return
        seen.add(current)
        try:
            if urlparse(current).hostname != urlparse(domain).hostname:
                raise ValueError("Sitemap must belong to the project domain")
            response = request("GET", safe_url(current))
            if len(response.content) > 2_000_000:
                raise ValueError("Sitemap too large")
            root = ElementTree.fromstring(response.content)
            locations = [el.text for el in root.iter() if el.tag.split("}")[-1] == "loc" and el.text]
            for loc in locations[:max_urls]:
                if root.tag.split("}")[-1] == "sitemapindex":
                    walk(loc, depth + 1)
                elif len(urls) < max_urls:
                    try:
                        safe_url(loc)
                        if urlparse(loc).hostname != urlparse(domain).hostname:
                            raise ValueError("URL outside project domain")
                        urls.append({"url": loc, "title": urlparse(loc).path.strip("/").replace("-", " ")})
                    except Exception as exc:
                        failures.append({"url": loc, "error": str(exc)})
        except Exception as exc:
            failures.append({"url": current, "error": str(exc)})
    walk(url)
    return {"items": urls, "failures": failures}
