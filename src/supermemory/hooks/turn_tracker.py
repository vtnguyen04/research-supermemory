"""Closed-Loop Turn Tracker: Auto-detects code edits, empirical metrics, research & task sync."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore

_BENCHMARK_CMD_RE = re.compile(
    r"(?:\b(?:python3?|uv\s+run|bash|sh)\b.*\b(?:train|eval|evaluate|benchmark|ablation|smoke|backtest|rollout|simulate|run_submission|run_exp|calibrate|profile_slice)\w*"
    r"|\bkaggle\s+competitions\s+submit\b)",
    flags=re.IGNORECASE,
)
_RESEARCH_CMD_RE = re.compile(
    r"\b(?:export\.arxiv\.org|arxiv\.org|semanticscholar\.org|api\.openalex\.org|huggingface\.co/papers)\b",
    flags=re.IGNORECASE,
)
_METRIC_OUT_RE = re.compile(
    r"\b(?:val_score|cv_score|test_score|leaderboard_score|mse|rmse|mae|regret|f1_score|auroc|hota|map|error_share|pareto_priority)\s*[:=]\s*[-+]?\d+\.\d+",
    flags=re.IGNORECASE,
)
_SM_CLI_MUTATIONS = (
    "supermemory sync",
    "supermemory exp",
    "supermemory learn",
    "supermemory idea",
    "supermemory proposal",
    "supermemory gate add",
    "supermemory gate freeze",
    "supermemory checkpoint",
    "supermemory consolidate",
    "supermemory promote",
    "supermemory bottleneck diagnose",
    "supermemory bottleneck resolve",
    "supermemory scout",
    "supermemory orchestrate plan",
    "supermemory orchestrate complete",
)
_SM_MCP_ALWAYS_MUTATING = {
    "update_state",
    "log_experiment",
    "record_lesson",
    "link_knowledge",
    "manage_proposal",
    "propose_idea",
    "add_gate",
    "checkpoint",
    "consolidate",
    "record_audit",
}
_IGNORED_DIR_PARTS = {".supermemory", "memory", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _is_sm_mcp_mutation(t_name: str, mcp_srv: str, norm_mcp: str, inner_args: Dict[str, Any]) -> tuple[bool, bool]:
    """Return `(is_mutation, is_readonly_scout)` for an MCP call."""
    is_sm = "supermemory" in t_name or "supermemory" in mcp_srv or bool(norm_mcp)
    if not is_sm:
        return False, False
    tool_key = norm_mcp or t_name.split("__")[-1]
    if tool_key in _SM_MCP_ALWAYS_MUTATING or any(m in t_name for m in _SM_MCP_ALWAYS_MUTATING):
        return True, False
    if tool_key == "diagnose_bottleneck" or "diagnose_bottleneck" in t_name:
        act = str(inner_args.get("action") or "diagnose").lower()
        return act not in ("rank", "score_occam"), False
    if tool_key == "scout_sota" or "scout_sota" in t_name:
        saved = str(inner_args.get("action") or "search").lower() == "register_card" or int(inner_args.get("save_top_k") or 0) > 0
        return saved, not saved
    if tool_key == "orchestrate" or "orchestrate" in t_name:
        act = str(inner_args.get("action") or "status").lower()
        return act in ("plan_sprint", "enqueue", "move", "toggle_step", "add_step", "complete"), False
    return False, False


def track_post_tool_use(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Track unlogged code edits, benchmark/metric runs, and research lookups in `<5ms`."""
    st = get_session_state(store, conv_id)
    tc = payload.get("toolCall") or {}
    t_name = str(tc.get("name") or "").lower()
    t_args = tc.get("args") or {}
    err = str(payload.get("error") or "")
    out_txt = str(payload.get("output") or payload.get("result") or "")

    cmd = str(t_args.get("CommandLine") or t_args.get("command") or "")
    mcp_srv = str(t_args.get("ServerName") or "").lower()
    mcp_tool = str(t_args.get("ToolName") or "").lower()
    norm_mcp = mcp_tool[12:] if mcp_tool.startswith("supermemory_") else (mcp_tool if "supermemory" in mcp_srv else "")
    raw_inner = t_args.get("Arguments")
    inner_args: Dict[str, Any] = raw_inner if isinstance(raw_inner, dict) else t_args

    if not err and (
        "supermemory learn" in cmd
        or "supermemory gate" in cmd
        or (("supermemory" in t_name or "supermemory" in mcp_srv) and ("record_lesson" in t_name or "add_gate" in t_name or norm_mcp in ("record_lesson", "add_gate")))
    ):
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True

    sm_mutated, scout_readonly = _is_sm_mcp_mutation(t_name, mcp_srv, norm_mcp, inner_args)
    if not err and (sm_mutated or any(m in cmd for m in _SM_CLI_MUTATIONS)):
        st["turn_memory_handled"] = True
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""
    elif not err and t_name in ("run_command", "bash"):
        if _BENCHMARK_CMD_RE.search(cmd):
            st["pending_sync_reason"] = f"Benchmark/experiment executed (`{cmd[:60]}`)"
            st["turn_memory_handled"] = False
        elif re.search(r"\b(?:python3?|uv\s+run)\b", cmd) and _METRIC_OUT_RE.search(out_txt):
            st["pending_sync_reason"] = f"Empirical metric output observed in `{cmd[:55]}`"
            st["turn_memory_handled"] = False
        elif _RESEARCH_CMD_RE.search(cmd) and not st.get("turn_memory_handled"):
            st["pending_sync_reason"] = "Research/literature lookup executed without saving distilled findings to SuperMemory Vault"
            st["turn_memory_handled"] = False
    elif not err and (scout_readonly or (t_name in ("search_web", "read_url_content", "websearch", "webfetch") and st.get("research_campaign_active"))):
        st["pending_sync_reason"] = "Research/literature lookup executed without saving distilled findings to SuperMemory Vault"
        st["turn_memory_handled"] = False

    if not err and t_name in ("write_file", "edit_file", "write", "edit", "multiedit", "replace_file_content", "multi_replace_file_content"):
        raw_p = str(t_args.get("Path") or t_args.get("TargetFile") or t_args.get("file_path") or "")
        if "02_CONSTITUTION_AND_LESSONS.md" in raw_p:
            st["pending_lesson_lock"] = False
            st["turn_memory_handled"] = True
        elif raw_p:
            abs_p = (Path(raw_p) if Path(raw_p).is_absolute() else (store.workspace_root / raw_p)).resolve()
            if abs_p.is_relative_to(store.workspace_root):
                rel_parts = abs_p.relative_to(store.workspace_root).parts
                if not any(p in _IGNORED_DIR_PARTS for p in rel_parts):
                    rel = "/".join(rel_parts)
                    dirty = list(st.get("dirty_files") or [])
                    if rel not in dirty:
                        dirty.append(rel)
                    st["dirty_files"] = dirty
                    st["turn_memory_handled"] = False

    if err:
        store.log_event("TOOL_ERROR_OBSERVED", t_name, f"Tool {t_name} errored: {err[:140]}")
    save_session_state(store, st)
    return {}


def evaluate_stop_gate(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce autonomous lesson, research, experiment, and task/insight sync before stopping."""
    if payload.get("continuationActive") or str(payload.get("terminationReason") or "") != "NO_TOOL_CALL":
        return {"decision": "allow"}

    st = get_session_state(store, conv_id)
    if st.get("pending_lesson_lock"):
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True
        save_session_state(store, st)
        return {
            "decision": "continue",
            "reason": (
                "🛡️ SUPERMEMORY SELF-LEARNING COMMIT REQUIRED (LAW-08): "
                "Persist the explicit lesson/rule + CodeGate via MCP `record_lesson` (`supermemory learn`) before finishing."
            ),
        }

    if not st.get("turn_memory_handled") and st.get("pending_sync_reason"):
        reason_txt = str(st.get("pending_sync_reason"))
        st["turn_memory_handled"] = True
        st["pending_sync_reason"] = ""
        st["dirty_files"] = []
        save_session_state(store, st)
        if "Research/literature" in reason_txt:
            return {
                "decision": "continue",
                "reason": (
                    f"🔬 SUPERMEMORY RESEARCH VAULT COMMIT REQUIRED (LAW-06 / LAW-07): {reason_txt}. "
                    "Auto-save distilled findings via `diagnose_bottleneck`, `scout_sota(save_top_k>=1)`, `propose_idea`, or `checkpoint(insights=[...])` before replying."
                ),
            }
        return {
            "decision": "continue",
            "reason": (
                f"🧪 SUPERMEMORY RESULT & INSIGHT SYNC REQUIRED: {reason_txt} ran without updating memory. "
                "Auto-save the empirical result, insights & Kanban task progress via MCP `log_experiment`, `diagnose_bottleneck`, or `checkpoint(insights=[...], task_updates=[...])` before replying."
            ),
        }

    dirty = list(st.get("dirty_files") or [])
    if not st.get("turn_memory_handled") and dirty:
        shown = ", ".join(dirty[:4]) + (f" +{len(dirty) - 4} more" if len(dirty) > 4 else "")
        st["turn_memory_handled"] = True
        st["dirty_files"] = []
        save_session_state(store, st)
        return {
            "decision": "continue",
            "reason": (
                f"⚡ SUPERMEMORY AUTO-SYNC REQUIRED (LAW-07): Workspace files modified (`{shown}`) without updating memory/tasks. "
                "Call MCP `checkpoint` in 1 atomic call (`insights=[...]`, `task_updates=[...]`, `new_task={...}`, `next_actions='...'`) "
                "or `log_experiment` so Kanban progress, insights & state update automatically (use `status='CLEAN'` only if purely cosmetic)."
            ),
        }
    return {"decision": "allow"}
