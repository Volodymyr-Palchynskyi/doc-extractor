import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredDocument:
    id: str
    data: bytes
    pages: int
    expires_at: float


class DocumentStore:
    """
    Short-lived, in-memory store for uploaded PDFs, so the UI can render pages next to the extracted fields.

    Invoices are sensitive, so the design is deliberately conservative: memory only (a restart forgets
    everything), a TTL, hard caps on count and total size (oldest evicted first), unguessable ids because the
    page endpoint has no other access control, and an explicit delete. With several processes each would
    keep its own store, so a shared store (Redis with a TTL) is needed before scaling out.
    """

    def __init__(self, ttl_s: float, max_docs: int, max_bytes: int, clock=time.monotonic) -> None:
        self.ttl_s = ttl_s
        self.max_docs = max_docs
        self.max_bytes = max_bytes
        self._clock = clock
        self._docs: OrderedDict[str, StoredDocument] = OrderedDict()

    def add(self, data: bytes, pages: int) -> str:
        self._evict()
        doc_id = secrets.token_urlsafe(16)
        self._docs[doc_id] = StoredDocument(doc_id, data, pages, self._clock() + self.ttl_s)
        # Make room: drop the oldest documents until both caps hold again (the new one always stays).
        while len(self._docs) > 1 and (len(self._docs) > self.max_docs or self.total_bytes > self.max_bytes):
            self._docs.popitem(last=False)
        return doc_id

    def get(self, doc_id: str) -> StoredDocument | None:
        doc = self._docs.get(doc_id)
        if doc is None:
            return None
        if doc.expires_at <= self._clock():
            del self._docs[doc_id]
            return None
        return doc

    def delete(self, doc_id: str) -> bool:
        return self._docs.pop(doc_id, None) is not None

    @property
    def total_bytes(self) -> int:
        return sum(len(d.data) for d in self._docs.values())

    def __len__(self) -> int:
        return len(self._docs)

    def _evict(self) -> None:
        now = self._clock()
        for doc_id in [k for k, d in self._docs.items() if d.expires_at <= now]:
            del self._docs[doc_id]
