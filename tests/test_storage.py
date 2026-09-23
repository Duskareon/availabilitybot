import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import Storage  # noqa: E402

G = 1


@pytest.fixture
def store():
    s = Storage(":memory:")
    yield s
    s.close()


def test_ranked_least_busy_first(store):
    store.set_status(G, 10, 4, now=100)
    store.set_status(G, 11, 1, now=100)
    store.set_status(G, 12, 3, now=100)
    assert [s.user_id for s in store.ranked(G)] == [11, 12, 10]


def test_ties_broken_by_most_recent(store):
    store.set_status(G, 10, 2, now=100)
    store.set_status(G, 11, 2, now=200)
    assert [s.user_id for s in store.ranked(G)] == [11, 10]


def test_set_status_upserts(store):
    store.set_status(G, 10, 5, "swamped", now=100)
    store.set_status(G, 10, 1, "free now", now=200)
    [s] = store.ranked(G)
    assert (s.busyness, s.note, s.updated_at) == (1, "free now", 200)


def test_update_busyness_keeps_note(store):
    assert store.update_busyness(G, 10, 3) is None
    store.set_status(G, 10, 1, "after 6pm", now=100)
    s = store.update_busyness(G, 10, 4, now=200)
    assert (s.busyness, s.note, s.updated_at) == (4, "after 6pm", 200)


def test_clear_status(store):
    store.set_status(G, 10, 2)
    assert store.clear_status(G, 10) is True
    assert store.clear_status(G, 10) is False
    assert store.get_status(G, 10) is None


def test_scoped_per_guild(store):
    store.set_status(1, 10, 2)
    store.set_status(2, 11, 2)
    assert [s.user_id for s in store.ranked(1)] == [10]


def test_rejects_invalid_busyness(store):
    with pytest.raises(ValueError):
        store.set_status(G, 10, 0)
    with pytest.raises(ValueError):
        store.set_status(G, 10, 6)
