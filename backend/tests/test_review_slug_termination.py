import subprocess
import sys

import pytest

from seoci.pipeline.quality import available_slug


def test_fragment_slug_terminates():
    result = subprocess.run([sys.executable, "-c", "from seoci.pipeline.quality import available_slug; print(available_slug('guide#overview', 'https://example.com', ['https://example.com/guide']))"], capture_output=True, text=True, timeout=2, check=True)
    assert result.stdout.strip() == "guide-2"


@pytest.mark.parametrize("slug, expected", [("Guide?source=test#overview", "guide"), ("#overview", "article"), ("", "article"), ("Practical Guide!", "practical-guide")])
def test_slug_is_normalized(slug, expected):
    assert available_slug(slug, "https://example.com", []) == expected


def test_bounded_search_handles_many_collisions():
    inventory = ["https://example.com/guide"] + [f"https://example.com/guide-{i}" for i in range(2, 122)]
    assert available_slug("guide", "https://example.com", inventory) == "guide-122"


def test_bounded_fallback_if_url_resolution_cannot_advance(monkeypatch):
    from seoci.pipeline import quality
    monkeypatch.setattr(quality, "proposed_url", lambda *args: "https://example.com/guide")
    with pytest.raises(RuntimeError, match="unique article slug"):
        available_slug("guide", "https://example.com", ["https://example.com/guide"])
