from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class SupersessionEdge:
    source_doc_id: str
    target_doc_id: str
    relation: str


def build_edges_from_citations(conn: sqlite3.Connection) -> list[SupersessionEdge]:
    rows = conn.execute(
        """
        SELECT doc_id, target_doc_id, relation FROM citations
        WHERE relation IN ('supersedes', 'withdraws') AND target_doc_id IS NOT NULL
        """
    ).fetchall()
    return [
        SupersessionEdge(source_doc_id=r["doc_id"], target_doc_id=r["target_doc_id"], relation=r["relation"])
        for r in rows
    ]


def detect_cycles(edges: list[SupersessionEdge]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_doc_id, []).append(edge.target_doc_id)

    cycles: list[list[str]] = []
    visited: set[str] = set()
    in_stack: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> None:
        visited.add(node)
        in_stack.add(node)
        path.append(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in in_stack:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])

        path.pop()
        in_stack.remove(node)

    for node in list(adjacency.keys()):
        if node not in visited:
            dfs(node)

    return cycles
