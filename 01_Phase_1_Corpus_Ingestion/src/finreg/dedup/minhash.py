from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from datasketch import MinHash, MinHashLSH

NUM_PERM = 128
LSH_THRESHOLD = 0.85
SHINGLE_SIZE = 5

_TEXT_SOURCE_RANK = {"pdf_layer": 0, "html": 0, "pdftotext": 1, "ocr": 2}


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    words = text.split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def compute_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    for shingle in shingles(text):
        m.update(shingle.encode("utf8"))
    return m


@dataclass(frozen=True)
class DocForDedup:
    doc_id: str
    text: str
    text_source: str
    char_count: int
    issue_date: str | None


def _canonical_sort_key(doc: DocForDedup) -> tuple[int, int, str, str]:
    return (
        _TEXT_SOURCE_RANK.get(doc.text_source, 3),
        -doc.char_count,
        doc.issue_date or "9999-99-99",
        doc.doc_id,
    )


def find_clusters(docs: list[DocForDedup]) -> list[list[str]]:
    """Groups documents into near-duplicate clusters via MinHash LSH.
    Returns a list of clusters, each a list of doc_ids (size >= 2)."""
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
    minhashes: dict[str, MinHash] = {}

    for doc in docs:
        mh = compute_minhash(doc.text)
        minhashes[doc.doc_id] = mh
        lsh.insert(doc.doc_id, mh)

    visited: set[str] = set()
    clusters: list[list[str]] = []

    for doc in docs:
        if doc.doc_id in visited:
            continue
        matches = set(lsh.query(minhashes[doc.doc_id]))
        matches.discard(doc.doc_id)
        if not matches:
            visited.add(doc.doc_id)
            continue
        cluster = {doc.doc_id} | matches
        visited |= cluster
        clusters.append(sorted(cluster))

    return clusters


def select_canonical(docs_in_cluster: list[DocForDedup]) -> str:
    ranked = sorted(docs_in_cluster, key=_canonical_sort_key)
    return ranked[0].doc_id


def cluster_similarity(doc_a: DocForDedup, doc_b: DocForDedup) -> float:
    mh_a = compute_minhash(doc_a.text)
    mh_b = compute_minhash(doc_b.text)
    return mh_a.jaccard(mh_b)


def run_dedup(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT d.doc_id, t.body, t.text_source, t.char_count, d.issue_date
        FROM documents d
        JOIN texts t ON t.doc_id = d.doc_id
        """
    ).fetchall()

    docs = [
        DocForDedup(
            doc_id=r["doc_id"], text=r["body"], text_source=r["text_source"],
            char_count=r["char_count"], issue_date=r["issue_date"],
        )
        for r in rows
    ]
    docs_by_id = {d.doc_id: d for d in docs}

    clusters = find_clusters(docs)

    conn.execute("DELETE FROM duplicates")
    for cluster_id, doc_ids in enumerate(clusters, start=1):
        cluster_docs = [docs_by_id[doc_id] for doc_id in doc_ids]
        canonical_id = select_canonical(cluster_docs)
        for doc in cluster_docs:
            similarity = 1.0 if doc.doc_id == canonical_id else cluster_similarity(
                docs_by_id[canonical_id], doc
            )
            conn.execute(
                "INSERT INTO duplicates (cluster_id, doc_id, is_canonical, similarity) VALUES (?, ?, ?, ?)",
                (cluster_id, doc.doc_id, 1 if doc.doc_id == canonical_id else 0, similarity),
            )
    conn.commit()
    return len(clusters)
