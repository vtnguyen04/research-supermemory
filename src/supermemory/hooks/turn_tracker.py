"""Domain-Agnostic Structural Turn Tracker & Real-Time In-Flight AI Notification Bus."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Dict, List

from supermemory.lifecycle.validators import summarize_active_task_focus
from supermemory.models import NodeType
from supermemory.research.kanban_ops import extract_task_steps
from supermemory.research.orchestrator import list_tasks
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore

_READONLY_BINS = {
    "ls", "pwd", "which", "whoami", "cat", "head", "tail", "wc", "grep", "rg", "find",
    "stat", "file", "ps", "lsof", "echo", "true", "date", "uname", "env", "printenv", "rtk",
}
_READONLY_GIT_SUBCMDS = {"status", "diff", "log", "show", "branch", "rev-parse", "remote", "tag"}
_DEV_PLUMBING_PREFIXES = (
    "ruff ", "mypy ", "flake8 ", "black ", "prettier ", "eslint ", "git add", "git commit",
    "git push", "git tag", "agy plugin validate", "supermemory audit", "supermemory status",
    "supermemory recall", "supermemory workspaces", "supermemory gate list",
)
_SM_CLI_MUTATIONS = (
    "supermemory sync", "supermemory exp", "supermemory learn", "supermemory idea",
    "supermemory proposal", "supermemory gate add", "supermemory gate freeze",
    "supermemory checkpoint", "supermemory consolidate", "supermemory promote",
    "supermemory bottleneck diagnose", "supermemory bottleneck resolve",
    "supermemory scout", "supermemory orchestrate plan", "supermemory orchestrate complete",
)
_SM_MCP_ALWAYS_MUTATING = {
    "update_state", "log_experiment", "record_lesson", "link_knowledge", "manage_proposal",
    "propose_idea", "add_gate", "checkpoint", "consolidate", "record_audit",
}
_EXTERNAL_DOMAINS = ("arxiv.org", "semanticscholar.org", "openalex.org", "huggingface.co/papers")
_IGNORED_DIR_PARTS = {".supermemory", "memory", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _classify_shell_command(cmd: str) -> str:
    """Structurally classify a shell command without any domain-specific metric/filename hardcoding."""
    raw = (cmd or "").strip()
    if not raw:
        return "READONLY"
    if any(d in raw.lower() for d in _EXTERNAL_DOMAINS):
        return "EXTERNAL_RESEARCH"
    if any(m in raw for m in _SM_CLI_MUTATIONS):
        return "SM_MUTATION"

    # Split compound pipelines/chains (`&&`, `;`) and inspect each segment structurally
    segments = [seg.strip() for part in raw.split("&&") for seg in part.split(";") if seg.strip()]
    has_substantive = False
    for seg in segments:
        low = seg.removeprefix("uv run ").strip()
        if any(low.startswith(p) for p in _DEV_PLUMBING_PREFIXES):
            continue
        try:
            toks = shlex.split(low)
        except ValueError:
            toks = low.split()
        if not toks:
            continue
        prog = Path(toks[0]).name.lower()
        if prog == "rtk" and len(toks) > 1:
            toks = toks[1:]
            prog = Path(toks[0]).name.lower()
        if prog in _READONLY_BINS:
            continue
        if prog == "git" and (len(toks) < 2 or toks[1] in _READONLY_GIT_SUBCMDS):
            continue
        has_substantive = True
    return "SUBSTANTIVE_EXEC" if has_substantive else "READONLY"


def _is_sm_mcp_mutation(t_name: str, mcp_srv: str, norm_mcp: str, inner_args: Dict[str, Any]) -> tuple[bool, bool]:
    is_sm = "supermemory" in t_name or "supermemory" in mcp_srv or bool(norm_mcp)
    if not is_sm:
        return False, False
    tool_key = norm_mcp or t_name.split("__")[-1]
    if tool_key in _SM_MCP_ALWAYS_MUTATING or any(m in t_name for m in _SM_MCP_ALWAYS_MUTATING):
        return True, False
    if tool_key == "diagnose_bottleneck" or "diagnose_bottleneck" in t_name:
        return str(inner_args.get("action") or "diagnose").lower() not in ("rank", "score_occam"), False
    if tool_key == "scout_sota" or "scout_sota" in t_name:
        saved = str(inner_args.get("action") or "search").lower() == "register_card" or int(inner_args.get("save_top_k") or 0) > 0
        return saved, not saved
    if tool_key == "orchestrate" or "orchestrate" in t_name:
        return str(inner_args.get("action") or "status").lower() in ("plan_sprint", "enqueue", "move", "toggle_step", "add_step", "complete"), False
    return False, False


def _active_task_focus_line(store: GraphStore) -> str:
    props = [n.to_dict() for n in store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=10)]
    tasks = []
    for t in list_tasks(store):
        td = t.to_dict()
        td["steps"] = extract_task_steps(td)
        tasks.append(td)
    return summarize_active_task_focus(props, tasks)


def track_post_tool_use(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Track structural tool events & emit real-time in-flight AI notifications (`<5ms`)."""
    st = get_session_state(store, conv_id)
    tc = payload.get("toolCall") or {}
    t_name = str(tc.get("name") or "").lower()
    t_args = tc.get("args") or {}
    err = str(payload.get("error") or "")

    cmd = str(t_args.get("CommandLine") or t_args.get("command") or "")
    mcp_srv = str(t_args.get("ServerName") or "").lower()
    mcp_tool = str(t_args.get("ToolName") or "").lower()
    norm_mcp = mcp_tool[12:] if mcp_tool.startswith("supermemory_") else (mcp_tool if "supermemory" in mcp_srv else "")
    raw_inner = t_args.get("Arguments")
    inner_args: Dict[str, Any] = raw_inner if isinstance(raw_inner, dict) else t_args
    notifications: List[str] = []

    if not err and (
        "supermemory learn" in cmd
        or "supermemory gate" in cmd
        or (("supermemory" in t_name or "supermemory" in mcp_srv) and ("record_lesson" in t_name or "add_gate" in t_name or norm_mcp in ("record_lesson", "add_gate")))
    ):
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True

    sm_mutated, scout_readonly = _is_sm_mcp_mutation(t_name, mcp_srv, norm_mcp, inner_args)
    cmd_kind = _classify_shell_command(cmd) if t_name in ("run_command", "bash") else "NONE"

    if not err and (sm_mutated or cmd_kind == "SM_MUTATION"):
        st["turn_memory_handled"] = True
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""
    elif not err and cmd_kind == "SUBSTANTIVE_EXEC":
        st["pending_sync_reason"] = f"Substantive execution `{cmd[:55]}` completed"
        st["turn_memory_handled"] = False
        if not st.get("notified_exec"):
            st["notified_exec"] = True
            focus = _active_task_focus_line(store)
            focus_hint = f" Active Task: {focus}." if focus else ""
            notifications.append(
                f"🔔 [SuperMemory Save Notification] Execution `{cmd[:45]}` finished.{focus_hint} "
                "Semantic self-triage: quantitative result -> `log_experiment`; error slice -> `diagnose_bottleneck`; "
                "technical insight -> `checkpoint(insights=[...])`; verified task step -> `checkpoint(task_updates=[...])`; "
                "purely diagnostic check -> `checkpoint(status='CLEAN')`."
            )
    elif not err and (
        cmd_kind == "EXTERNAL_RESEARCH"
        or scout_readonly
        or (t_name in ("search_web", "read_url_content", "websearch", "webfetch") and st.get("research_campaign_active"))
    ):
        st["pending_sync_reason"] = "Research/literature lookup executed without saving distilled findings to SuperMemory Vault"
        st["turn_memory_handled"] = False
        if not st.get("notified_research"):
            st["notified_research"] = True
            notifications.append(
                "🔔 [SuperMemory Research Notification] Literature/web lookup observed. Distill concrete mechanisms into "
                "`07_METHOD_VAULT/` (`scout_sota`), `08_BOTTLENECKS/` (`diagnose_bottleneck`), or `checkpoint(insights=[...])`."
            )

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
                    if not st.get("notified_edit"):
                        st["notified_edit"] = True
                        focus = _active_task_focus_line(store)
                        if focus:
                            notifications.append(
                                f"🔔 [SuperMemory Task-List Notification] Editing `{rel}` — Active spec: {focus}. "
                                "Execute steps in order, and sync completed steps + concrete insights via `checkpoint(task_updates=[...], insights=[...])` before finishing."
                            )
                        else:
                            notifications.append(
                                f"🔔 [SuperMemory Spec Notification] Editing `{rel}` without an active Proposal/Kanban task. "
                                "For non-trivial features, register a structured Proposal (`manage_proposal` with `why`, `what_changes`, `tasks`) or `checkpoint(new_task={...})` and sync insights before finishing."
                            )

    if err:
        store.log_event("TOOL_ERROR_OBSERVED", t_name, f"Tool {t_name} errored: {err[:140]}")
    save_session_state(store, st)
    if notifications:
        return {"injectSteps": [{"systemMessage": {"systemMessage": "\n".join(notifications)}}]}
    return {}


def evaluate_stop_gate(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Final backstop when the AI ignores in-flight notifications (0 overhead on Q&A)."""
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

    focus = _active_task_focus_line(store)
    focus_suffix = f" (Active Task List: {focus})" if focus else ""

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
                    f"🔬 SUPERMEMORY RESEARCH VAULT COMMIT REQUIRED (LAW-06 / LAW-07): {reason_txt}.{focus_suffix} "
                    "Save distilled findings via `diagnose_bottleneck`, `scout_sota(save_top_k>=1)`, `propose_idea`, or `checkpoint(insights=[...])` before replying."
                ),
            }
        return {
            "decision": "continue",
            "reason": (
                f"🧪 SUPERMEMORY RESULT & INSIGHT SYNC REQUIRED: {reason_txt} without updating memory.{focus_suffix} "
                "Triage and sync now: quantitative metric -> `log_experiment`; error slice -> `diagnose_bottleneck`; "
                "technical insight / task step -> `checkpoint(insights=[...], task_updates=[...])`; or diagnostic-only -> `checkpoint(status='CLEAN')`."
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
                f"⚡ SUPERMEMORY AUTO-SYNC REQUIRED (LAW-07): Workspace files modified (`{shown}`) without updating memory/tasks.{focus_suffix} "
                "Call MCP `checkpoint` in 1 atomic call (`insights=[...]`, `task_updates=[...]`, `new_task={...}`, `next_actions='...'`) "
                "or `log_experiment` / `manage_proposal` (pass `status='CLEAN'` only if purely cosmetic)."
            ),
        }
    return {"decision": "allow"}
