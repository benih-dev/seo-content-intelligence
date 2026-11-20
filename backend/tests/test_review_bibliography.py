import pytest

from seoci.pipeline.quality import check_article


@pytest.mark.parametrize("publisher", ["www.w3.org", "4-H Extension", "Institute 2025"])
def test_bibliography_metadata_is_not_numeric_claim(publisher):
    body = f"- [Guide](https://source.example/guide) — {publisher}; retrieved 2026-01-01"
    result = check_article(body, {}, [{"url": "https://source.example/guide", "claim": "Source summary", "publisher": publisher}], [], "guide")
    assert not any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])


def test_claim_after_bibliography_still_checked():
    body = "- [Guide](https://source.example/guide) — www.w3.org; retrieved 2026-01-01. Raises yields by 90%."
    result = check_article(body, {}, [{"url": "https://source.example/guide", "claim": "Source summary"}], [], "guide")
    assert any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])


@pytest.mark.parametrize("claim", ["Plants mature in 14 days", "Plants Mature in 14 Days", "Plants Mature 14 Days", "Produces 90 million plants"])
def test_numeric_prose_is_not_a_publisher(claim):
    body = f"- [Guide](https://source.example/guide) — {claim}; retrieved 2026-01-01"
    result = check_article(body, {}, [{"url": "https://source.example/guide", "claim": "Source summary"}], [], "guide")
    assert any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])


def test_recorded_publisher_can_have_a_long_name():
    publisher = "University of California Agriculture and Natural Resources"
    body = f"- [Guide](https://source.example/guide) — {publisher}; retrieved 2026-01-01"
    evidence = [{"url": "https://source.example/guide", "claim": "Source summary", "publisher": publisher}]
    result = check_article(body, {}, evidence, [], "guide")
    assert not any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])


@pytest.mark.parametrize("publisher", ["www.w3.org", "Publisher", "4-H Extension", "Royal Horticultural Society"])
def test_host_or_short_proper_name_without_publisher_record(publisher):
    body = f"- [Guide](https://source.example/guide) — {publisher}; retrieved 2026-01-01"
    result = check_article(body, {}, [{"url": "https://source.example/guide", "claim": "Source summary"}], [], "guide")
    assert not any(f["finding"] == "Unsupported numeric claim" for f in result["findings"])
