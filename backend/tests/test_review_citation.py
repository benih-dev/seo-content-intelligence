from seoci.pipeline.quality import check_article


def test_citation_bullet_does_not_hide_claims():
    evidence = [{"url": "https://source.example/guide", "claim": "Use draining containers"}]
    def numeric(body):
        return [f for f in check_article(body, {}, evidence, [], "guide")["findings"] if f["finding"] == "Unsupported numeric claim"]
    assert numeric("- [Source](https://source.example/guide) proves a 90% improvement")
    assert numeric("- [Source](https://source.example/guide) — yields improve 90%; retrieved 2026-01-01")
    assert not numeric("- [Guide 2025](https://source.example/guide) — Publisher; retrieved 2026-01-01")
    assert not numeric("Use draining containers [source](https://source.example/guide)")
