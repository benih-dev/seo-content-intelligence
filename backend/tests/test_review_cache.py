from seoci.providers.network import cached


def test_cache_insert_race(client):
    def competing_fetch():
        return cached("race", "same", "id-ID", "desktop", lambda: {"winner": True})
    assert cached("race", "same", "id-ID", "desktop", competing_fetch) == {"winner": True}
    assert cached("race", "same", "id-ID", "desktop", lambda: 1) == {"winner": True}
