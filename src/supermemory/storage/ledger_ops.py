"""SQLite repository helpers for CodeGates and Scientific Experiments."""

from __future__ import annotations

import json
import sqlite3
from typing import List, Optional

from supermemory.models import CodeGate, ExperimentRecord, utc_now_iso


def upsert_gate_row(conn: sqlite3.Connection, gate: CodeGate) -> CodeGate:
    conn.execute(
        """
        INSERT INTO gates(id, gate_type, name, law_id, lesson_id, target_glob, pattern,
                          config_json, enabled, blocked_count, last_blocked_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            gate_type=excluded.gate_type, name=excluded.name, law_id=excluded.law_id,
            lesson_id=excluded.lesson_id, target_glob=excluded.target_glob,
            pattern=excluded.pattern, config_json=excluded.config_json, enabled=excluded.enabled
        """,
        (
            gate.id,
            gate.gate_type,
            gate.name,
            gate.law_id,
            gate.lesson_id,
            gate.target_glob,
            gate.pattern,
            json.dumps(gate.config, ensure_ascii=False),
            int(gate.enabled),
            gate.blocked_count,
            gate.last_blocked_at,
            gate.created_at,
        ),
    )
    conn.commit()
    return gate


def list_gate_rows(conn: sqlite3.Connection, enabled_only: bool = False) -> List[CodeGate]:
    sql = "SELECT * FROM gates WHERE enabled = 1 ORDER BY id" if enabled_only else "SELECT * FROM gates ORDER BY id"
    return [
        CodeGate(
            id=str(r["id"]),
            gate_type=str(r["gate_type"]),
            name=str(r["name"]),
            law_id=str(r["law_id"]),
            lesson_id=str(r["lesson_id"]),
            target_glob=str(r["target_glob"]),
            pattern=str(r["pattern"]),
            config=json.loads(r["config_json"] or "{}"),
            enabled=bool(r["enabled"]),
            blocked_count=int(r["blocked_count"]),
            last_blocked_at=r["last_blocked_at"],
            created_at=str(r["created_at"]),
        )
        for r in conn.execute(sql).fetchall()
    ]


def increment_gate_block_row(conn: sqlite3.Connection, gate_id: str) -> None:
    conn.execute(
        "UPDATE gates SET blocked_count = blocked_count + 1, last_blocked_at = ? WHERE id = ?",
        (utc_now_iso(), gate_id),
    )


def set_gate_enabled_row(conn: sqlite3.Connection, gate_id: str, enabled: bool) -> bool:
    cur = conn.execute("UPDATE gates SET enabled = ? WHERE id = ?", (int(enabled), gate_id))
    conn.commit()
    return cur.rowcount > 0


def delete_gate_row(conn: sqlite3.Connection, gate_id: str) -> bool:
    cur = conn.execute("DELETE FROM gates WHERE id = ?", (gate_id,))
    conn.commit()
    return cur.rowcount > 0


def upsert_experiment_row(conn: sqlite3.Connection, exp: ExperimentRecord) -> ExperimentRecord:
    conn.execute(
        """
        INSERT INTO experiments(exp_id, track, title, hypothesis, single_var_diff, model_stack,
            baseline_id, proposal_id, cv_score, cv_summary, test_score, test_summary,
            delta_vs_baseline, runtime_summary, verdict, leakage_audit, post_mortem, log_path,
            metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exp_id) DO UPDATE SET
            track=excluded.track, title=excluded.title, hypothesis=excluded.hypothesis,
            single_var_diff=excluded.single_var_diff, model_stack=excluded.model_stack,
            baseline_id=excluded.baseline_id, proposal_id=excluded.proposal_id,
            cv_score=excluded.cv_score, cv_summary=excluded.cv_summary,
            test_score=excluded.test_score, test_summary=excluded.test_summary,
            delta_vs_baseline=excluded.delta_vs_baseline, runtime_summary=excluded.runtime_summary,
            verdict=excluded.verdict, leakage_audit=excluded.leakage_audit,
            post_mortem=excluded.post_mortem, log_path=excluded.log_path,
            metadata_json=excluded.metadata_json
        """,
        (
            exp.exp_id,
            exp.track,
            exp.title,
            exp.hypothesis,
            exp.single_var_diff,
            exp.model_stack,
            exp.baseline_id,
            exp.proposal_id,
            exp.cv_score,
            exp.cv_summary,
            exp.test_score,
            exp.test_summary,
            exp.delta_vs_baseline,
            exp.runtime_summary,
            exp.verdict,
            exp.leakage_audit,
            exp.post_mortem,
            exp.log_path,
            json.dumps(exp.metadata, ensure_ascii=False),
            exp.created_at,
        ),
    )
    conn.commit()
    return exp


def list_experiment_rows(conn: sqlite3.Connection, track: Optional[str] = None) -> List[ExperimentRecord]:
    rows = (
        conn.execute("SELECT * FROM experiments WHERE track = ? ORDER BY created_at DESC, exp_id DESC", (track,)).fetchall()
        if track
        else conn.execute("SELECT * FROM experiments ORDER BY created_at DESC, exp_id DESC").fetchall()
    )
    return [
        ExperimentRecord(
            exp_id=str(r["exp_id"]),
            track=str(r["track"]),
            title=str(r["title"]),
            hypothesis=str(r["hypothesis"]),
            single_var_diff=str(r["single_var_diff"]),
            model_stack=str(r["model_stack"]),
            baseline_id=str(r["baseline_id"]),
            proposal_id=str(r["proposal_id"]),
            cv_score=r["cv_score"],
            cv_summary=str(r["cv_summary"]),
            test_score=r["test_score"],
            test_summary=str(r["test_summary"]),
            delta_vs_baseline=r["delta_vs_baseline"],
            runtime_summary=str(r["runtime_summary"]),
            verdict=str(r["verdict"]),
            leakage_audit=str(r["leakage_audit"]),
            post_mortem=str(r["post_mortem"]),
            log_path=str(r["log_path"]),
            metadata=json.loads(r["metadata_json"] or "{}"),
            created_at=str(r["created_at"]),
        )
        for r in rows
    ]
