import pytest

from seoci.pipeline.quality import check_article


@pytest.mark.parametrize("publisher", ["www.w3.org", "4-H Extension", "Institute 2025"])
def test_bibliography_metadata_is_not_numeric_claim(publisher):
    body = f"- [Guide](https://source.example/guide) — {publisher}; retrieved 2026-01-01"
    result = check_article(body, {}, [{"url": "https://source.example/guide", "claim": "Source summary"}], [], "guide")
    assert not any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])


def test_claim_after_bibliography_still_checked():
    body = "- [Guide](https://source.example/guide) — www.w3.org; retrieved 2026-01-01. Raises yields by 90%."
    result = check_article(body, {}, [{"url": "https://source.example/guide", "claim": "Source summary"}], [], "guide")
    assert any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])
