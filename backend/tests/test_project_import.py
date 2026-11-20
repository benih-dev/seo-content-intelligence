import httpx
import pytest

from seoci.providers import network, sitemap
from seoci.worker import work_once


def test_profile_validation_and_queued_run_snapshot(client, project):
    profile_url = f"/api/projects/{project['id']}"
    updated = {
        "name": "  Balcony Garden  ",
        "domain": "www.example.com",
        "niche": "Balcony gardening",
        "audience": "First-time growers",
        "language": "en",
        "country": "US",
        "voice_profile": "Friendly and practical",
        "rules": {"instructions": "Use plain language.", "exclusions": ["pesticide brands"]},
        "business_objective": "Help people grow food",
    }
    for field in ("name", "niche", "audience"):
        response = client.put(profile_url, json={**updated, field: "   "})
        assert response.status_code == 422
    response = client.put(profile_url, json=updated)
    assert response.status_code == 200
    saved = response.json()
    assert saved["name"] == "Balcony Garden"
    assert saved["domain"] == "https://www.example.com"
    assert saved["version"] == 2
    assert client.get(profile_url).json() == saved

    run = client.post("/api/runs", json={"project_id": project["id"], "primary_keyword": "balcony gardens"})
    assert run.status_code == 201
    assert client.put(profile_url, json={**updated, "rules": {"instructions": "New rules."}}).status_code == 200
    assert work_once()
    run_detail = client.get(f"/api/runs/{run.json()['id']}").json()
    assert run_detail["state"] == "keyword_review"
    assert run_detail["locale"] == "en-US"
    assert run_detail["context"] == {"project": saved, "project_version": 2}


def test_manual_import_skips_invalid_rows_without_erasing_existing_fields(client, project):
    path = f"/api/projects/{project['id']}/content-items"
    url = "https://www.example.com/growing-basil"
    result = client.post(path, json={"items": [
        {"url": f" {url} ", "title": "Growing basil", "metadata_json": {"source": "manual"}},
        {"url": "example.com/missing-scheme"},
        {"url": "https://[invalid"},
        {"url": "https://other.example/foreign"},
        {"url": url},
        {"url": "http://example.com/mint"},
    ]})
    assert result.status_code == 200
    report = result.json()
    assert [row["url"] for row in report["items"]] == [url, "http://example.com/mint"]
    assert report["items"][0]["title"] == "Growing basil"
    assert report["items"][0]["slug"] == "growing-basil"
    assert report["items"][0]["metadata_json"] == {"source": "manual"}
    assert ["starting with https://" in row["error"] for row in report["failures"]] == [True, True, False]
    assert "project website" in report["failures"][2]["error"]
    assert {row["url"]: row for row in client.get(path).json()} == {row["url"]: row for row in report["items"]}


def test_sitemap_import_follows_site_aliases_and_preserves_metadata(client, project, monkeypatch):
    path = f"/api/projects/{project['id']}"
    page_url = "https://www.example.com/growing-basil"
    assert client.post(f"{path}/content-items", json={"items": [
        {"url": page_url, "title": "Growing basil", "metadata_json": {"source": "manual"}},
    ]}).status_code == 200
    fetched = []
    responses = {
        "https://example.com/index.xml": (301, "", {"Location": "https://www.example.com/index.xml"}),
        "https://www.example.com/index.xml": (200, """
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <sitemap><loc> https://example.com/posts.xml </loc></sitemap>
              <sitemap><loc>https://example.com/missing.xml</loc></sitemap>
              <sitemap><loc>https://example.com/other.xml</loc></sitemap>
            </sitemapindex>
        """, {}),
        "https://example.com/posts.xml": (307, "", {"Location": "https://www.example.com/posts.xml"}),
        "https://www.example.com/posts.xml": (200, f"""
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="urn:images">
              <url><loc> {page_url} </loc><lastmod>2025-05-08</lastmod>
                <image:image><image:loc>https://www.example.com/photo.jpg</image:loc></image:image>
              </url>
              <url><loc>{page_url}</loc></url>
            </urlset>
        """, {}),
        "https://example.com/missing.xml": (404, "", {}),
        "https://example.com/other.xml": (302, "", {"Location": "https://external.example/sitemap.xml"}),
    }

    def handle(request):
        url = str(request.url)
        fetched.append(url)
        status, text, headers = responses[url]
        return httpx.Response(status, text=text, headers=headers)

    original_client = httpx.Client
    monkeypatch.setattr(network.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handle), **kwargs,
    ))
    monkeypatch.setattr(sitemap, "safe_url", lambda url: url)
    monkeypatch.setattr(network.request.retry, "sleep", lambda _: None)
    response = client.post(f"{path}/sitemap", json={"url": "https://example.com/index.xml"})
    assert response.status_code == 202
    report = response.json()
    assert len(report["items"]) == 1
    row = report["items"][0]
    assert row["title"] == "Growing basil"
    assert row["metadata_json"] == {"source": "manual", "sitemap_lastmod": "2025-05-08"}
    assert "Sitemap not found" in report["failures"][0]["error"]
    assert "project website" in report["failures"][1]["error"]
    assert set(fetched) == set(responses)
    assert client.get(f"{path}/content-items").json() == [row]


@pytest.mark.parametrize(("content", "error"), [
    ("<html><loc>https://example.com/guide</loc></html>", "does not contain an XML sitemap"),
    ("<urlset>", "did not return a valid XML sitemap"),
])
def test_sitemap_rejects_non_sitemap_content(client, project, monkeypatch, content, error):
    monkeypatch.setattr(sitemap, "safe_url", lambda url: url)
    monkeypatch.setattr(sitemap, "request", lambda *args, **kwargs: httpx.Response(200, text=content))
    response = client.post(f"/api/projects/{project['id']}/sitemap", json={"url": "https://example.com/sitemap.xml"})
    assert response.status_code == 202
    assert response.json()["items"] == []
    assert error in response.json()["failures"][0]["error"]
