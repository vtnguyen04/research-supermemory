"""SQLite WAL DDL schema and FTS5 triggers for SuperMemory."""

from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    summary TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    file_path TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    priority INTEGER NOT NULL DEFAULT 50,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    id UNINDEXED,
    node_type,
    title,
    summary,
    content,
    tags_text,
    tokenize = 'unicode61'
);

CREATE TRIGGER IF NOT EXISTS trg_nodes_ai AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, id, node_type, title, summary, content, tags_text)
    VALUES (new.rowid, new.id, new.node_type, new.title, new.summary, new.content, new.tags_json);
END;

CREATE TRIGGER IF NOT EXISTS trg_nodes_ad AFTER DELETE ON nodes BEGIN
    DELETE FROM nodes_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_nodes_au AFTER UPDATE ON nodes BEGIN
    DELETE FROM nodes_fts WHERE rowid = old.rowid;
    INSERT INTO nodes_fts(rowid, id, node_type, title, summary, content, tags_text)
    VALUES (new.rowid, new.id, new.node_type, new.title, new.summary, new.content, new.tags_json);
END;

CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, relation)
);

CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relation);

CREATE TABLE IF NOT EXISTS gates (
    id TEXT PRIMARY KEY,
    gate_type TEXT NOT NULL,
    name TEXT NOT NULL,
    law_id TEXT NOT NULL DEFAULT '',
    lesson_id TEXT NOT NULL DEFAULT '',
    target_glob TEXT NOT NULL DEFAULT '**/*',
    pattern TEXT NOT NULL DEFAULT '',
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    last_blocked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    exp_id TEXT PRIMARY KEY,
    track TEXT NOT NULL,
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    single_var_diff TEXT NOT NULL,
    model_stack TEXT NOT NULL DEFAULT '',
    baseline_id TEXT NOT NULL DEFAULT '',
    proposal_id TEXT NOT NULL DEFAULT '',
    cv_score REAL,
    cv_summary TEXT NOT NULL DEFAULT '',
    test_score REAL,
    test_summary TEXT NOT NULL DEFAULT '',
    delta_vs_baseline REAL,
    runtime_summary TEXT NOT NULL DEFAULT '',
    verdict TEXT NOT NULL DEFAULT 'PENDING',
    leakage_audit TEXT NOT NULL DEFAULT 'CLEAN',
    post_mortem TEXT NOT NULL DEFAULT '',
    log_path TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exp_track ON experiments(track);
CREATE INDEX IF NOT EXISTS idx_exp_verdict ON experiments(verdict);

CREATE TABLE IF NOT EXISTS session_state (
    conversation_id TEXT PRIMARY KEY,
    invocation_num INTEGER NOT NULL DEFAULT 0,
    last_step_idx INTEGER NOT NULL DEFAULT 0,
    pending_lesson_lock INTEGER NOT NULL DEFAULT 0,
    pending_lesson_quote TEXT NOT NULL DEFAULT '',
    pending_lesson_category TEXT NOT NULL DEFAULT '',
    dirty_files_json TEXT NOT NULL DEFAULT '[]',
    unlogged_exp_cmds_json TEXT NOT NULL DEFAULT '[]',
    compaction_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'agent',
    entity_id TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

CREATE TABLE IF NOT EXISTS http_cache (
    cache_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    task_id TEXT PRIMARY KEY,
    wave INTEGER NOT NULL DEFAULT 1,
    role TEXT NOT NULL,
    title TEXT NOT NULL,
    brief TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'QUEUED',
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    locked_globs_json TEXT NOT NULL DEFAULT '[]',
    target_id TEXT NOT NULL DEFAULT '',
    claimed_by TEXT NOT NULL DEFAULT '',
    smoke_gate TEXT NOT NULL DEFAULT '',
    receipt_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_wave ON agent_tasks(wave);
"""


def apply_schema(conn: sqlite3.Connection) -> None:
    """Initialize all SQLite tables, indexes, and FTS5 triggers idempotently."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
