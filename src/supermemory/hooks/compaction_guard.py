"""Post-Compaction Active Recall Guard, Contextual Query Synthesis & Session Grounding."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from supermemory.gates.sim_helpers import extract_tool_file_path
from supermemory.hooks.compaction_probe import extract_memory_read_relpath, probe_transcript_compaction
from supermemory.models import NodeType
from supermemory.storage.snapshot_io import save_session_state
from supermemory.storage.sqlite_store import GraphStore

_HISTORY_NODE_TYPES = [
    NodeType.EXPERIMENT.value,
    NodeType.PROPOSAL.value,
    NodeType.BOTTLENECK.value,
    NodeType.LESSON.value,
    NodeType.OBSERVATION.value,
    NodeType.KNOWLEDGE_NODE.value,
    NodeType.METHOD_CARD.value,
]
_GROUNDING_CLI_SUBCMDS = {
    "recall", "status", "sync", "exp", "learn", "idea", "proposal",
    "checkpoint", "consolidate", "promote", "scout", "orchestrate", "bottleneck", "gate",
}
_EDIT_TOOLS = {
    "write_file", "edit_file", "write", "edit", "multiedit",
    "replace_file_content", "multi_replace_file_content", "notebookedit",
}
_EXEMPT_WORKSPACE_DIRS = {".supermemory", "memory", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_DEFAULT_BOILERPLATE_GOAL = "Maintain 100% constitutional compliance."


def handle_subagent_hook(store: GraphStore, ev: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep PreToolUse CodeGates 100% enforced inside subagents while avoiding orchestrator nags & Stop blocks."""
    if ev == "SessionStart":
        msg = f"🧠 SuperMemory Subagent Guard Active — Workspace: `{store.workspace_root}` (Constitutional Laws & PreToolUse CodeGates enforced)."
        return {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}
    if ev == "PostToolUse":
        tc = payload.get("toolCall") or {}
        mem_rel = extract_memory_read_relpath(store.workspace_root, str(tc.get("name") or "").lower(), tc.get("args") or {})
        if mem_rel:
            store.log_event("MEMORY_READ", Path(mem_rel).stem[:32], f"Subagent read `{mem_rel}`")
        return {}
    if ev == "Stop":
        return {"decision": "allow"}
    return {}


def workspace_has_memory_history(store: GraphStore) -> bool:
    """Return True in O(1) (`LIMIT 1`) if the workspace contains project knowledge worth recalling."""
    return bool(store.list_nodes(node_types=_HISTORY_NODE_TYPES, limit=1))


def build_compaction_recovery_query(store: GraphStore, user_input: str = "") -> str:
    """Synthesize a rich FTS recall query from active proposals, bottlenecks, goal, and user prompt."""
    parts: list[str] = []
    clean_u = (user_input or "").strip()
    if clean_u and "<CONTEXT_SUMMARY>" not in clean_u:
        parts.append(clean_u[:160])
    goal = (store.get_meta("active_goal") or "").strip()
    if goal and goal != _DEFAULT_BOILERPLATE_GOAL:
        parts.append(goal[:120])
    for p in store.list_nodes(
        node_types=[NodeType.PROPOSAL.value],
        exclude_statuses=["ARCHIVED", "REJECTED", "AUDITED", "CONSOLIDATED"],
        limit=2,
    ):
        parts.append(f"{p.id} {p.title[:80]}")
    for b in store.list_nodes(
        node_types=[NodeType.BOTTLENECK.value],
        exclude_statuses=["RESOLVED", "ARCHIVED", "CONSOLIDATED"],
        limit=2,
    ):
        parts.append(f"{b.id} {b.title[:80]}")
    return " ".join(parts).strip()


def arm_compaction_grounding(store: GraphStore, st: Dict[str, Any], marker: str) -> bool:
    """Arm post-compaction recall requirement unless this compaction marker was already grounded."""
    eff_m = marker if (marker and marker != "NONE") else f"STEPDROP:{int(st.get('compaction_count') or 1)}"
    if st.get("ground_next_tail_marker"):
        st["ground_next_tail_marker"] = False
        st["grounded_compaction_marker"] = eff_m
        st["strike_compaction_marker"] = eff_m
        st["compaction_recall_pending"] = False
        st["compaction_gate_strikes"] = 0
        return False
    if not workspace_has_memory_history(store):
        st["compaction_recall_pending"] = False
        st["compaction_gate_strikes"] = 0
        return False
    if eff_m == st.get("grounded_compaction_marker"):
        st["compaction_recall_pending"] = False
        return False
    st["compaction_recall_pending"] = True
    if eff_m != st.get("strike_compaction_marker"):
        st["compaction_gate_strikes"] = 0
    return True


def mark_session_compaction_grounded(
    store: GraphStore,
    st: Dict[str, Any],
    conv_id: str,
    transcript_path: str = "",
) -> None:
    """Clear post-compaction recall requirement after `recall`, `status`, `memory/` read, or MCP sync."""
    _, tail_m = probe_transcript_compaction(conv_id, "", transcript_path)
    eff_m = tail_m if (tail_m and tail_m != "NONE") else str(st.get("last_compaction_marker") or "")
    st["compaction_recall_pending"] = False
    st["compaction_gate_strikes"] = 0
    st["ground_next_tail_marker"] = False
    if eff_m and eff_m != "NONE":
        st["grounded_compaction_marker"] = eff_m
        st["strike_compaction_marker"] = eff_m


def evaluate_compaction_pre_tool_gate(
    store: GraphStore,
    conv_id: str,
    st: Dict[str, Any],
    payload: Dict[str, Any],
    t_name: str,
    raw_args: Dict[str, Any],
    classify_shell_fn: Callable[[str], str],
    has_sm_subcmd_fn: Callable[[str, set[str]], bool],
    active_focus_fn: Callable[[GraphStore], str],
) -> Optional[str]:
    """Catch ungrounded post-compaction edits/substantive execs (including pre-PreInvocation CHECKPOINTs; 1-strike max)."""
    tn = (t_name or "").lower()
    t_path = str(payload.get("transcriptPath") or "")

    if tn in ("run_command", "bash"):
        cmd = str(raw_args.get("CommandLine") or raw_args.get("command") or "")
        if has_sm_subcmd_fn(cmd, _GROUNDING_CLI_SUBCMDS):
            mark_session_compaction_grounded(store, st, conv_id, t_path)
            save_session_state(store, st)
            return None
        if classify_shell_fn(cmd) not in ("SUBSTANTIVE_EXEC", "EXTERNAL_RESEARCH"):
            return None
    elif tn in _EDIT_TOOLS:
        raw_p = extract_tool_file_path(raw_args)
        if not raw_p:
            return None
        try:
            abs_p = (Path(raw_p) if Path(raw_p).is_absolute() else (store.workspace_root / raw_p)).resolve()
        except OSError:
            return None
        if not abs_p.is_relative_to(store.workspace_root):
            return None
        if any(p in _EXEMPT_WORKSPACE_DIRS for p in abs_p.relative_to(store.workspace_root).parts):
            return None
    else:
        return None

    chk_hit, tail_m = probe_transcript_compaction(conv_id, str(st.get("last_compaction_marker") or ""), t_path)
    eff_m = tail_m if (tail_m and tail_m != "NONE") else str(st.get("last_compaction_marker") or "")
    if st.get("ground_next_tail_marker"):
        st["ground_next_tail_marker"] = False
        st["compaction_recall_pending"] = False
        st["compaction_gate_strikes"] = 0
        if eff_m and eff_m != "NONE":
            st["grounded_compaction_marker"] = eff_m
            st["strike_compaction_marker"] = eff_m
        save_session_state(store, st)
        return None

    ungrounded_tail = bool(chk_hit and eff_m and eff_m != st.get("grounded_compaction_marker"))
    pending_flag = bool(st.get("compaction_recall_pending"))
    if not ungrounded_tail and not pending_flag:
        return None
    if not workspace_has_memory_history(store):
        if pending_flag:
            st["compaction_recall_pending"] = False
            save_session_state(store, st)
        return None

    strikes = int(st.get("compaction_gate_strikes") or 0)
    same_strike_m = bool(eff_m and eff_m == st.get("strike_compaction_marker"))
    if strikes >= 1 and (same_strike_m or not chk_hit):
        st["compaction_recall_pending"] = False
        st["compaction_gate_strikes"] = 0
        if eff_m and eff_m != "NONE":
            st["grounded_compaction_marker"] = eff_m
        save_session_state(store, st)
        return None

    st["compaction_recall_pending"] = True
    st["compaction_gate_strikes"] = 1
    if eff_m:
        st["strike_compaction_marker"] = eff_m
    save_session_state(store, st)
    focus = active_focus_fn(store)
    focus_hint = f" Active spec: {focus}." if focus else ""
    store.log_event(
        "COMPACTION_RECALL_REQUIRED",
        tn[:32],
        "Blocked ungrounded post-compaction edit/exec until MCP recall() or memory read",
    )
    return (
        f"♻️ SUPERMEMORY POST-COMPACTION GROUNDING REQUIRED (LAW-07): Context just compacted "
        f"(`<CONTEXT_SUMMARY>` omits exact metrics, checklists & dead-ends).{focus_hint} "
        f"Call MCP `recall(query='...', workspace='{store.workspace_root}')` (or `status` / read "
        f"`memory/01_ACTIVE_STATE.md`) once to ground exact graph state before editing files or running experiments."
    )
