"""Domain-Agnostic Structural Turn Tracker & Real-Time In-Flight AI Notification Bus."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from supermemory.cognitive.curator_engine import check_curation_pressure
from supermemory.gates.sim_helpers import extract_tool_file_path, split_shell_commands
from supermemory.hooks.compaction_probe import extract_memory_read_relpath, recall_module_dead_ends
from supermemory.kernel import classify_mcp_call
from supermemory.lifecycle.validators import summarize_active_task_focus
from supermemory.models import NodeType
from supermemory.research.kanban_digest import has_unchecked_kanban_items
from supermemory.research.kanban_ops import extract_task_steps
from supermemory.research.orchestrator import list_tasks
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore

_READONLY_BINS = {
    "ls", "pwd", "which", "whoami", "cat", "head", "tail", "wc", "grep", "rg", "find", "stat", "file",
    "ps", "lsof", "echo", "true", "date", "uname", "env", "printenv", "rtk", "jq", "awk", "cut", "sort",
    "uniq", "tr", "df", "du", "free", "uptime", "nvidia-smi", "gpustat", "pytest",
}
_READONLY_GIT_SUBCMDS = {"status", "diff", "log", "show", "branch", "rev-parse", "remote", "tag"}
_DEV_PLUMBING_PREFIXES = (
    "ruff ", "mypy ", "flake8 ", "black ", "prettier ", "eslint ", "pytest", "git add", "git commit",
    "git push", "git tag", "agy plugin validate", "supermemory audit", "supermemory status",
    "supermemory recall", "supermemory workspaces", "supermemory gate list", "supermemory install-plugin",
)
_SM_MUTATION_SUBCMDS = {
    "sync", "exp", "learn", "idea", "proposal", "checkpoint",
    "consolidate", "promote", "scout", "orchestrate", "bottleneck", "gate",
}
_EXTERNAL_FETCH_BINS = {"curl", "wget"}
_EXTERNAL_DOMAINS = ("arxiv.org", "semanticscholar.org", "openalex.org", "huggingface.co/papers")
_IGNORED_DIR_PARTS = {".supermemory", "memory", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _has_sm_cli_subcmd(cmd: str, subcmds: set[str]) -> bool:
    for argv, _ in split_shell_commands(cmd):
        if not argv:
            continue
        prog = Path(argv[0]).name.lower()
        if prog in ("supermemory", "research-supermemory") and len(argv) >= 2 and argv[1] in subcmds:
            if argv[1] == "gate" and len(argv) >= 3 and argv[2] == "list":
                continue
            return True
    return False


def _classify_shell_command(cmd: str) -> str:
    """Quote-aware structural shell classification (`0` false triggers on `grep 'a|b'`, `2>&1`, or `pytest`)."""
    raw = (cmd or "").strip()
    if not raw:
        return "READONLY"
    if _has_sm_cli_subcmd(raw, _SM_MUTATION_SUBCMDS):
        return "SM_MUTATION"

    has_substantive = False
    for argv, has_redir in split_shell_commands(raw):
        if not argv:
            if has_redir:
                has_substantive = True
            continue
        joined = " ".join(argv)
        prog = Path(argv[0]).name.lower()
        if prog in _EXTERNAL_FETCH_BINS and any(d in joined.lower() for d in _EXTERNAL_DOMAINS):
            return "EXTERNAL_RESEARCH"
        if has_redir:
            has_substantive = True
            continue
        if any(joined == p.strip() or joined.startswith(p) for p in _DEV_PLUMBING_PREFIXES):
            continue
        if prog == "sed" and not any(a.startswith("-i") for a in argv[1:]):
            continue
        if prog in _READONLY_BINS:
            continue
        if prog == "git" and (len(argv) < 2 or argv[1] in _READONLY_GIT_SUBCMDS):
            continue
        has_substantive = True
    return "SUBSTANTIVE_EXEC" if has_substantive else "READONLY"


def _active_task_focus_line(store: GraphStore) -> str:
    props = [n.to_dict() for n in store.list_nodes(node_types=[NodeType.PROPOSAL.value], exclude_statuses=["ARCHIVED", "AUDITED", "REJECTED", "CONSOLIDATED"], limit=40)]
    tasks = [{**t.to_dict(), "steps": extract_task_steps(t.to_dict())} for t in list_tasks(store)]
    return summarize_active_task_focus(props, tasks)


def _resolve_norm_mcp(t_name: str, mcp_srv: str, mcp_tool: str) -> str:
    if mcp_tool.startswith("supermemory_"):
        return mcp_tool[12:]
    if "supermemory" in mcp_srv and mcp_tool:
        return mcp_tool
    if "__" in t_name and "supermemory" in t_name:
        tail = t_name.split("__")[-1]
        return tail[12:] if tail.startswith("supermemory_") else tail
    return ""


def _is_kanban_sync_action(t_name: str, norm_mcp: str, inner_args: Dict[str, Any], cmd: str) -> bool:
    """Return True if this tool call updated Kanban tasks/subtasks, ticked `done_steps`, or attested CLEAN/WAIT."""
    done_tools = ("orchestrate", "manage_proposal", "consolidate", "diagnose_bottleneck", "scout_sota", "record_audit")
    if norm_mcp in done_tools or any(t_name.endswith(s) for s in done_tools):
        return True
    if norm_mcp == "log_experiment" or t_name.endswith("log_experiment"):
        return bool(inner_args.get("done_steps"))
    if norm_mcp == "checkpoint" or t_name.endswith("checkpoint"):
        if inner_args.get("task_updates") or inner_args.get("new_task"):
            return True
        if str(inner_args.get("status") or "").upper() in ("CLEAN", "IN_FLIGHT_WAIT") and not inner_args.get("insights") and not inner_args.get("insight_title"):
            return True
    if _has_sm_cli_subcmd(cmd, {"orchestrate", "proposal", "consolidate", "bottleneck", "scout"}):
        return True
    return _has_sm_cli_subcmd(cmd, {"checkpoint"}) and "--status" in cmd and ("CLEAN" in cmd or "IN_FLIGHT_WAIT" in cmd)


def track_post_tool_use(store: GraphStore, conv_id: str, payload: Dict[str, Any], is_claude: bool = False) -> Dict[str, Any]:
    """Track structural tool events & emit real-time in-flight AI notifications (`<5ms`)."""
    st = get_session_state(store, conv_id)
    tc = payload.get("toolCall") or {}
    t_name = str(tc.get("name") or "").lower()
    t_args = tc.get("args") or {}
    err = str(payload.get("error") or "")
    out_txt = str(payload.get("output") or payload.get("result") or "")

    cmd = str(t_args.get("CommandLine") or t_args.get("command") or "")
    mcp_srv = str(t_args.get("ServerName") or "").lower()
    mcp_tool = str(t_args.get("ToolName") or "").lower()
    norm_mcp = _resolve_norm_mcp(t_name, mcp_srv, mcp_tool)
    raw_inner = t_args.get("Arguments")
    inner_args: Dict[str, Any] = raw_inner if isinstance(raw_inner, dict) else t_args
    notifications: List[str] = []

    mem_rel = extract_memory_read_relpath(store.workspace_root, t_name, t_args)
    if not err and mem_rel and mem_rel != st.get("last_read_mem"):
        st["last_read_mem"] = mem_rel
        store.log_event("MEMORY_READ", Path(mem_rel).stem[:32], f"Agent read `{mem_rel}`")

    if not err and (
        (t_name in ("run_command", "bash") and _has_sm_cli_subcmd(cmd, {"learn", "gate"}))
        or (("supermemory" in t_name or "supermemory" in mcp_srv) and ("record_lesson" in t_name or "add_gate" in t_name or norm_mcp in ("record_lesson", "add_gate")))
    ):
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True

    sm_mutated, scout_readonly = classify_mcp_call(t_name, mcp_srv, norm_mcp, inner_args)
    cmd_kind = _classify_shell_command(cmd) if t_name in ("run_command", "bash") else "NONE"
    is_bg_launch = "running as a background task" in out_txt.lower() or bool(t_args.get("IsDaemon"))
    work_bumped = False

    if not err and (sm_mutated or cmd_kind == "SM_MUTATION"):
        st["turn_memory_handled"] = True
        st["stop_block_streak"] = 0
        if norm_mcp != "consolidate" and str(inner_args.get("status") or "").upper() != "IN_FLIGHT_WAIT":
            st["dirty_files"] = []
        st["pending_sync_reason"] = ""
        st["unsynced_work_steps"] = 0
        st["pending_notifications"] = []
        if _is_kanban_sync_action(t_name, norm_mcp, inner_args, cmd) or not has_unchecked_kanban_items(store):
            st["pending_kanban_sync"] = False
        elif st.get("pending_kanban_sync"):
            focus = _active_task_focus_line(store)
            notifications.append(
                f"📋 [SuperMemory Kanban Sync] Memory saved, while active Kanban subtasks remain unticked ({focus}). "
                "Tick completed step(s) via `checkpoint(task_updates=[{'id': '...', 'done_steps': [...]}])` "
                "(or pass `checkpoint(status='CLEAN')` if current step is still midway)."
            )
        if norm_mcp != "consolidate":
            cur = check_curation_pressure(store, mark_prompted=True)
            if cur["needs_curation"]:
                notifications.append(
                    f"🧹 [SuperMemory Subagent Curation Trigger] Vault reached curation threshold ({', '.join(cur['reasons'])}). "
                    f"Spawn `memory-curator` in background (`invoke_subagent(TypeName='memory-curator', Role='Semantic Memory Curator', Prompt=...)`) -> {cur['subagent_prompt']}"
                )
    elif not err and cmd_kind == "SUBSTANTIVE_EXEC" and not is_bg_launch:
        desc = f"Substantive execution `{cmd[:55]}`"
        st["pending_sync_reason"] = f"{desc} completed"
        st["turn_memory_handled"] = False
        work_bumped = True
        if has_unchecked_kanban_items(store):
            st["pending_kanban_sync"] = True
        if not st.get("notified_exec"):
            st["notified_exec"] = True
            focus = _active_task_focus_line(store)
            focus_hint = f" Active Task: {focus}." if focus else ""
            notifications.append(
                f"🔔 [SuperMemory Save Notification] {desc} finished.{focus_hint} "
                "Semantic self-triage: quantitative result (KEEP or DISCARD) -> `log_experiment`; error slice -> `diagnose_bottleneck`; "
                "technical insight -> `checkpoint(insights=[...])`; verified task step -> `checkpoint(task_updates=[...])`; "
                "diagnostic/poll -> `checkpoint(status='CLEAN' | 'IN_FLIGHT_WAIT')`."
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

    if not err and t_name in ("write_file", "edit_file", "write", "edit", "multiedit", "replace_file_content", "multi_replace_file_content", "notebookedit"):
        raw_p = extract_tool_file_path(t_args)
        if raw_p:
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
                    work_bumped = True
                    if has_unchecked_kanban_items(store):
                        st["pending_kanban_sync"] = True
                    if not st.get("notified_edit"):
                        st["notified_edit"] = True
                        focus = _active_task_focus_line(store)
                        mod_warns = recall_module_dead_ends(store, rel)
                        warn_sfx = (" ⚠️ Past Dead-Ends on module: " + " | ".join(mod_warns)) if mod_warns else ""
                        if focus:
                            notifications.append(f"🔔 [SuperMemory Task-List Notification] Editing `{rel}` — Active spec: {focus}.{warn_sfx} Execute steps in order, and sync completed steps + concrete insights via `checkpoint(task_updates=[...], insights=[...])` before finishing.")
                        else:
                            notifications.append(f"🔔 [SuperMemory Spec Notification] Editing `{rel}` without an active Proposal/Kanban task.{warn_sfx} For non-trivial features, register a structured Proposal (`manage_proposal` with `why`, `what_changes`, `tasks`) or `checkpoint(new_task={{...}})` and sync insights before finishing.")

    if work_bumped:
        cnt = int(st.get("unsynced_work_steps") or 0) + 1
        st["unsynced_work_steps"] = cnt
        if cnt >= 12 and cnt % 12 == 0:
            focus = _active_task_focus_line(store)
            notifications.append(f"⏱️ [SuperMemory Incremental Sync — {cnt} Unsynced Steps]{f' ({focus})' if focus else ''} Flush intermediate findings/metrics via `checkpoint(insights=[...], task_updates=[...])` or `log_experiment` before context compacts.")
            store.log_event("INCREMENTAL_SYNC_PULSE", conv_id, f"Emitted checkpoint pulse at {cnt} unsynced steps")
    if err:
        store.log_event("TOOL_ERROR_OBSERVED", t_name, f"Tool {t_name} errored: {err[:140]}")
    if notifications and not is_claude:
        st["pending_notifications"] = (list(st.get("pending_notifications") or []) + notifications)[-6:]
    save_session_state(store, st)
    return {"injectSteps": [{"systemMessage": {"systemMessage": "\n".join(notifications)}}]} if notifications else {}


def evaluate_stop_gate(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Final backstop when the AI ignores in-flight notifications (strict 1-block max — never deadlocks!)."""
    if payload.get("continuationActive") or str(payload.get("terminationReason") or "") != "NO_TOOL_CALL":
        return {"decision": "allow"}

    st = get_session_state(store, conv_id)
    if int(st.get("stop_block_streak") or 0) >= 1:
        st["stop_block_streak"] = 0
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True
        st["pending_sync_reason"] = ""
        st["pending_kanban_sync"] = False
        st["dirty_files"] = []
        save_session_state(store, st)
        return {"decision": "allow"}

    if st.get("pending_lesson_lock"):
        st["stop_block_streak"] = 1
        save_session_state(store, st)
        store.log_event("STOP_GATE_ENFORCED", "LAW-08", "Stop hook required autonomous self-learning lesson + CodeGate commit")
        return {"decision": "continue", "reason": "🛡️ SUPERMEMORY SELF-LEARNING COMMIT REQUIRED (LAW-08): Persist the explicit lesson/rule + CodeGate via MCP `record_lesson` (`supermemory learn`) before finishing."}

    focus = _active_task_focus_line(store)
    focus_suffix = f" (Active Task List: {focus})" if focus else ""

    if not st.get("turn_memory_handled") and st.get("pending_sync_reason"):
        reason_txt = str(st.get("pending_sync_reason"))
        st["stop_block_streak"] = 1
        save_session_state(store, st)
        store.log_event("STOP_GATE_ENFORCED", "LAW-07", f"Stop hook required result/research sync: {reason_txt[:95]}")
        if "Research/literature" in reason_txt:
            return {"decision": "continue", "reason": f"🔬 SUPERMEMORY RESEARCH VAULT COMMIT REQUIRED (LAW-06 / LAW-07): {reason_txt}.{focus_suffix} Save distilled findings via `diagnose_bottleneck`, `scout_sota(save_top_k>=1)`, `propose_idea`, or `checkpoint(insights=[...])` before replying."}
        return {"decision": "continue", "reason": f"🧪 SUPERMEMORY RESULT & INSIGHT SYNC REQUIRED: {reason_txt} without updating memory.{focus_suffix} Triage and sync now: quantitative metric (KEEP or DISCARD) -> `log_experiment`; error slice -> `diagnose_bottleneck`; technical insight / task step -> `checkpoint(insights=[...], task_updates=[...])`; or diagnostic/poll -> `checkpoint(status='CLEAN' | 'IN_FLIGHT_WAIT')`."}

    dirty = list(st.get("dirty_files") or [])
    if not st.get("turn_memory_handled") and dirty:
        shown = ", ".join(dirty[:4]) + (f" +{len(dirty) - 4} more" if len(dirty) > 4 else "")
        st["stop_block_streak"] = 1
        save_session_state(store, st)
        store.log_event("STOP_GATE_ENFORCED", "LAW-07", f"Stop hook intercepted unsynced workspace edits ({shown[:95]})")
        return {"decision": "continue", "reason": f"⚡ SUPERMEMORY AUTO-SYNC REQUIRED (LAW-07): Workspace files modified (`{shown}`) without updating memory/tasks.{focus_suffix} Call MCP `checkpoint` with concrete `insights=[...]` / `task_updates=[...]` (or `status='IN_FLIGHT_WAIT'` if waiting on async run) or `log_experiment`."}

    if st.get("pending_kanban_sync") and has_unchecked_kanban_items(store):
        st["stop_block_streak"] = 1
        save_session_state(store, st)
        store.log_event("STOP_GATE_ENFORCED", "LAW-07", "Stop hook required Kanban subtask sync after work execution")
        return {"decision": "continue", "reason": f"📋 SUPERMEMORY KANBAN SUBTASK SYNC REQUIRED (LAW-07): Work executed without syncing active Kanban steps ({focus}). Tick completed step(s) via `checkpoint(task_updates=[{{'id': '...', 'done_steps': [...]}}])` (or attest `checkpoint(status='CLEAN')` if no checklist step completed yet)."}
    return {"decision": "allow"}
