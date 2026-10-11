from app.services.document_store import DocumentStore


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make(**kwargs) -> tuple[DocumentStore, Clock]:
    clock = Clock()
    defaults = dict(ttl_s=60, max_docs=3, max_bytes=1000)
    return DocumentStore(**{**defaults, **kwargs}, clock=clock), clock


def test_stores_and_returns_a_document():
    store, _ = make()
    doc_id = store.add(b"%PDF-data", pages=2)

    doc = store.get(doc_id)
    assert doc.data == b"%PDF-data" and doc.pages == 2


def test_document_expires_after_ttl():
    store, clock = make(ttl_s=60)
    doc_id = store.add(b"x", pages=1)

    clock.now = 59
    assert store.get(doc_id) is not None
    clock.now = 60
    assert store.get(doc_id) is None
    assert len(store) == 0, "an expired document must be removed, not just hidden"


def test_oldest_documents_are_evicted_when_the_count_cap_is_hit():
    store, _ = make(max_docs=2)
    first, second, third = store.add(b"1", 1), store.add(b"2", 1), store.add(b"3", 1)

    assert store.get(first) is None
    assert store.get(second) is not None and store.get(third) is not None


def test_oldest_documents_are_evicted_when_the_size_cap_is_hit():
    store, _ = make(max_docs=10, max_bytes=100)
    first, second = store.add(b"a" * 60, 1), store.add(b"b" * 60, 1)

    assert store.get(first) is None and store.get(second) is not None
    assert store.total_bytes <= 100


def test_the_newest_document_is_kept_even_if_it_alone_exceeds_the_size_cap():
    store, _ = make(max_bytes=10)
    doc_id = store.add(b"x" * 500, 1)

    assert store.get(doc_id) is not None


def test_delete_is_idempotent():
    store, _ = make()
    doc_id = store.add(b"x", 1)

    assert store.delete(doc_id) is True
    assert store.delete(doc_id) is False
    assert store.get(doc_id) is None


def test_ids_are_unguessable_and_unique():
    store, _ = make(max_docs=1000, max_bytes=10**9)
    ids = {store.add(b"x", 1) for _ in range(200)}

    assert len(ids) == 200
    assert all(len(i) >= 20 for i in ids), "ids are the only access control, they must be long"


def test_expired_documents_are_swept_when_new_ones_arrive():
    store, clock = make(ttl_s=10, max_docs=100)
    store.add(b"old", 1)
    clock.now = 11
    store.add(b"new", 1)

    assert len(store) == 1
