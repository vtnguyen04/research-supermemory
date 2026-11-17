"""O(1) Tail Transcript Compaction Probe, Content-Overlap Guard & Memory-Read Telemetry."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_WORD4_RE = re.compile(r"[0-9a-zA-Z_\u00C0-\u1EF9]{4,}")
_FUNC_WORDS = {
    "this", "that", "with", "from", "have", "what", "when", "where", "which", "there", "their", "about",
    "những", "được", "không", "trong", "đang", "phải", "nhiều", "nhưng", "chưa", "xem", "hiện",
}


def has_content_overlap(query: str, hit: Dict[str, Any]) -> bool:
    """Require at least 1 shared content word (`len >= 4`, non-stopword) or explicit ID match."""
    hid = str(hit.get("id") or "").upper()
    if hid and hid in query.upper():
        return True
    q_words = {w.lower() for w in _WORD4_RE.findall(query)} - _FUNC_WORDS
    if not q_words:
        return False
    d_txt = f"{hit.get('title', '')} {hit.get('summary', '')}"
    d_words = {w.lower() for w in _WORD4_RE.findall(d_txt)} - _FUNC_WORDS
    return bool(q_words & d_words)


def _resolve_transcript_file(conv_id: str, transcript_path: str = "") -> Optional[Path]:
    if transcript_path:
        cand = Path(transcript_path)
        if cand.is_file():
            return cand
    env_brain = os.environ.get("SUPERMEMORY_BRAIN_DIR", "").strip()
    roots: List[Path] = []
    if env_brain:
        roots.append(Path(env_brain))
    home_gem = Path.home() / ".gemini"
    for prod in ("antigravity-cli", "antigravity", "antigravity-ide"):
        roots.append(home_gem / prod / "brain")
    for base in roots:
        p = base / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
        if p.is_file():
            return p
    return None


def probe_transcript_compaction(
    conv_id: str,
    prev_marker: str,
    transcript_path: str = "",
) -> Tuple[bool, str]:
    """Read last 64KB of `transcript.jsonl` (<1ms) to detect Antigravity & Claude Code compactions."""
    t_file = _resolve_transcript_file(conv_id, transcript_path)
    if t_file is None:
        return False, prev_marker or "NONE"
    try:
        size = t_file.stat().st_size
        offset = max(0, size - 65536)
        with t_file.open("rb") as fh:
            if offset > 0:
                fh.seek(offset)
            chunk = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return False, prev_marker or "NONE"

    lines = chunk.splitlines()
    if offset > 0 and lines:
        lines = lines[1:]

    for idx_from_end, raw_ln in enumerate(reversed(lines)):
        if "CHECKPOINT" not in raw_ln and "compact_boundary" not in raw_ln and '"summary"' not in raw_ln:
            continue
        try:
            obj = json.loads(raw_ln)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        otype = str(obj.get("type") or "")
        subtype = str(obj.get("subtype") or "")
        if otype != "CHECKPOINT" and subtype != "compact_boundary" and otype != "summary":
            continue
        marker = f"{obj.get('step_index', obj.get('uuid', len(lines) - idx_from_end))}:{obj.get('created_at', obj.get('timestamp', ''))}"
        if marker == prev_marker:
            return False, marker
        if not prev_marker:
            return (idx_from_end <= 10), marker
        return True, marker
    return False, prev_marker or "NONE"


def reset_state_on_compaction(st: Dict[str, Any], step_idx: int, inv_num: int, marker: str = "") -> None:
    """Reset session deduplication and notification gates after context compaction."""
    st["compaction_count"] = int(st.get("compaction_count") or 0) + 1
    if marker:
        st["last_compaction_marker"] = marker
    st["last_heartbeat_bucket"] = 0
    st["recalled_node_ids"] = []
    st["recalled_warnings"] = []
    st["last_kanban_fp"] = ""
    st["last_kanban_inv"] = 0
    st["notified_edit"] = False
    st["notified_exec"] = False
    st["notified_research"] = False
    st["last_capsule_step"] = step_idx
    st["last_capsule_inv"] = inv_num


def extract_memory_read_relpath(workspace_root: Path, tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Return workspace-relative `memory/...` path when `read_file` reads a SuperMemory artifact."""
    if tool_name not in ("read_file", "view_file", "read"):
        return ""
    raw_p = str(
        tool_args.get("Path")
        or tool_args.get("AbsolutePath")
        or tool_args.get("TargetFile")
        or tool_args.get("file_path")
        or tool_args.get("path")
        or ""
    ).strip()
    if not raw_p:
        return ""
    try:
        abs_p = (Path(raw_p) if Path(raw_p).is_absolute() else (workspace_root / raw_p)).resolve()
    except OSError:
        return ""
    if not abs_p.is_relative_to(workspace_root):
        return ""
    parts = abs_p.relative_to(workspace_root).parts
    if parts and parts[0] == "memory":
        return "/".join(parts)
    return ""
