"""ACID SQLite Property Graph, FTS5 search, and immutable event ledger."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from supermemory.models import CodeGate, ExperimentRecord, MemoryEdge, MemoryNode, utc_now_iso
from supermemory.storage.ledger_ops import (
    delete_gate_row,
    increment_gate_block_row,
    list_experiment_rows,
    list_gate_rows,
    set_gate_enabled_row,
    upsert_experiment_row,
    upsert_gate_row,
)
from supermemory.storage.schema import apply_schema

MAX_EVENT_LOG_ROWS = 2000


def _safe_fts_query(raw: str) -> str:
    """Sanitize arbitrary natural language input into a safe FTS5 OR query."""
    tokens = [t for t in re.findall(r"[\w]+", raw.lower(), flags=re.UNICODE) if len(t) >= 2]
    if not tokens:
        return ""
    deduped = list(dict.fromkeys(tokens))[:16]
    return " OR ".join(f'"{tok}"*' for tok in deduped)


class GraphStore:
    """Transactional SQLite-backed property graph and telemetry store."""

    def __init__(self, workspace_root: Path | str, db_path: Optional[Path] = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.dot_dir = self.workspace_root / ".supermemory"
        self.mem_dir = self.workspace_root / "memory"
        self.db_path = db_path or (self.dot_dir / "supermemory.db")
        self.snapshot_path = self.mem_dir / "graph_snapshot.json"
        self.dot_dir.mkdir(parents=True, exist_ok=True)
        was_missing = not self.db_path.exists()
        self.conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn)
        if was_missing and self.snapshot_path.exists():
            from supermemory.storage.snapshot_io import import_snapshot

            import_snapshot(self, self.snapshot_path)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> GraphStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def set_meta(self, key: str, value: Any) -> None:
        val_str = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self.conn.execute(
            "INSERT INTO project_meta(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, val_str, utc_now_iso()),
        )
        self.conn.commit()

    def get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM project_meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def get_all_meta(self) -> Dict[str, str]:
        rows = self.conn.execute("SELECT key, value FROM project_meta ORDER BY key").fetchall()
        return {str(r["key"]): str(r["value"]) for r in rows}

    def upsert_node(self, node: MemoryNode, log_event: bool = True) -> MemoryNode:
        node.updated_at = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO nodes(id, node_type, title, status, summary, content, metadata_json,
                              file_path, tags_json, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                node_type=excluded.node_type, title=excluded.title, status=excluded.status,
                summary=excluded.summary, content=excluded.content, metadata_json=excluded.metadata_json,
                file_path=excluded.file_path, tags_json=excluded.tags_json,
                priority=excluded.priority, updated_at=excluded.updated_at
            """,
            (
                node.id,
                node.node_type,
                node.title,
                node.status,
                node.summary,
                node.content,
                json.dumps(node.metadata, ensure_ascii=False),
                node.file_path,
                json.dumps(node.tags, ensure_ascii=False),
                node.priority,
                node.created_at,
                node.updated_at,
            ),
        )
        if log_event:
            self._append_event("NODE_UPSERT", node.id, f"[{node.node_type}] {node.id}: {node.title}")
        self.conn.commit()
        return node

    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        row = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return self._row_to_node(row) if row else None

    def delete_node(self, node_id: str) -> bool:
        self.conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
        self.conn.execute("DELETE FROM experiments WHERE exp_id = ?", (node_id,))
        cur = self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        if cur.rowcount > 0:
            self._append_event("NODE_DELETED", node_id, f"Deleted node {node_id}")
        self.conn.commit()
        return cur.rowcount > 0

    def list_nodes(
        self,
        node_types: Optional[Sequence[str]] = None,
        status: Optional[str] = None,
        limit: int = 500,
    ) -> List[MemoryNode]:
        clauses: List[str] = []
        params: List[Any] = []
        if node_types:
            placeholders = ",".join("?" for _ in node_types)
            clauses.append(f"node_type IN ({placeholders})")
            params.extend(node_types)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM nodes {where_sql} ORDER BY priority DESC, id ASC LIMIT ?"
        params.append(limit)
        return [self._row_to_node(r) for r in self.conn.execute(sql, params).fetchall()]

    def add_edge(self, edge: MemoryEdge) -> None:
        self.conn.execute(
            """
            INSERT INTO edges(source_id, target_id, relation, weight, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                weight=excluded.weight, metadata_json=excluded.metadata_json
            """,
            (
                edge.source_id,
                edge.target_id,
                edge.relation,
                edge.weight,
                json.dumps(edge.metadata, ensure_ascii=False),
                edge.created_at,
            ),
        )
        self.conn.commit()

    def delete_edge(self, source_id: str, target_id: str, relation: str = "") -> bool:
        if relation:
            cur = self.conn.execute(
                "DELETE FROM edges WHERE source_id = ? AND target_id = ? AND relation = ?",
                (source_id, target_id, relation),
            )
        else:
            cur = self.conn.execute("DELETE FROM edges WHERE source_id = ? AND target_id = ?", (source_id, target_id))
        self.conn.commit()
        if cur.rowcount > 0:
            self.log_event("EDGE_DELETED", source_id, f"Unlinked {source_id} -[{relation or '*'}]-> {target_id}")
        return cur.rowcount > 0

    def list_edges(self, node_id: Optional[str] = None) -> List[MemoryEdge]:
        if node_id:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE source_id = ? OR target_id = ? ORDER BY created_at ASC",
                (node_id, node_id),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM edges ORDER BY source_id, target_id").fetchall()
        return [
            MemoryEdge(
                source_id=str(r["source_id"]),
                target_id=str(r["target_id"]),
                relation=str(r["relation"]),
                weight=float(r["weight"]),
                metadata=json.loads(r["metadata_json"] or "{}"),
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]

    def search_fts(self, query: str, limit: int = 12) -> List[Tuple[MemoryNode, float]]:
        fts_q = _safe_fts_query(query)
        if not fts_q:
            return []
        rows = self.conn.execute(
            """
            SELECT n.*, bm25(nodes_fts, 0.0, 2.0, 6.0, 4.0, 1.5, 3.0) AS rank_score
            FROM nodes_fts
            JOIN nodes n ON n.rowid = nodes_fts.rowid
            WHERE nodes_fts MATCH ?
            ORDER BY rank_score ASC, n.priority DESC
            LIMIT ?
            """,
            (fts_q, limit),
        ).fetchall()
        return [(self._row_to_node(r), abs(float(r["rank_score"]))) for r in rows]

    def upsert_gate(self, gate: CodeGate) -> CodeGate:
        return upsert_gate_row(self.conn, gate)

    def list_gates(self, enabled_only: bool = False) -> List[CodeGate]:
        return list_gate_rows(self.conn, enabled_only=enabled_only)

    def set_gate_enabled(self, gate_id: str, enabled: bool) -> bool:
        ok = set_gate_enabled_row(self.conn, gate_id, enabled)
        if ok:
            self.log_event("GATE_TOGGLED", gate_id, f"Gate {gate_id} -> enabled={enabled}")
        return ok

    def delete_gate(self, gate_id: str) -> bool:
        ok = delete_gate_row(self.conn, gate_id)
        if ok:
            self.log_event("GATE_DELETED", gate_id, f"Deleted gate {gate_id}")
        return ok

    def record_gate_block(self, gate_id: str, detail: str) -> None:
        increment_gate_block_row(self.conn, gate_id)
        self._append_event("GATE_BLOCKED", gate_id, detail)
        self.conn.commit()

    def upsert_experiment(self, exp: ExperimentRecord) -> ExperimentRecord:
        return upsert_experiment_row(self.conn, exp)

    def list_experiments(self, track: Optional[str] = None) -> List[ExperimentRecord]:
        return list_experiment_rows(self.conn, track=track)

    def log_event(self, event_type: str, entity_id: str, summary: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._append_event(event_type, entity_id, summary, payload)
        self.conn.commit()

    def list_events(self, limit: int = 80) -> List[Dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def prune_events(self, max_events: int = MAX_EVENT_LOG_ROWS) -> int:
        """Ring-buffer prune: retain only the most recent `max_events` telemetry rows."""
        cur = self.conn.execute(
            "DELETE FROM events WHERE seq <= (SELECT COALESCE(MAX(seq), 0) - ? FROM events)",
            (max(1, max_events),),
        )
        self.conn.commit()
        return int(cur.rowcount or 0)

    def _append_event(self, event_type: str, entity_id: str, summary: str, payload: Optional[Dict[str, Any]] = None) -> None:
        cur = self.conn.execute(
            "INSERT INTO events(event_type, actor, entity_id, summary, payload_json, created_at) VALUES (?, 'supermemory', ?, ?, ?, ?)",
            (event_type, entity_id, summary, json.dumps(payload or {}, ensure_ascii=False), utc_now_iso()),
        )
        if cur.lastrowid and cur.lastrowid % 100 == 0:
            self.conn.execute(
                "DELETE FROM events WHERE seq <= (SELECT COALESCE(MAX(seq), 0) - ? FROM events)",
                (MAX_EVENT_LOG_ROWS,),
            )

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> MemoryNode:
        return MemoryNode(
            id=str(row["id"]),
            node_type=str(row["node_type"]),
            title=str(row["title"]),
            status=str(row["status"]),
            summary=str(row["summary"]),
            content=str(row["content"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            file_path=str(row["file_path"]),
            tags=json.loads(row["tags_json"] or "[]"),
            priority=int(row["priority"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
