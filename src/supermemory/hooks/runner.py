"""Antigravity Lifecycle Hook Runner (SessionStart, PreInvocation, PreToolUse, PostToolUse, Stop)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from supermemory.gates.enforcer import GateEnforcer
from supermemory.graph.query_engine import QueryEngine
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore


def _resolve_supermemory_workspace(payload: Dict[str, Any]) -> Optional[Path]:
    """Find active SuperMemory workspace root from hook payload, or None if not initialized."""
    candidates = []
    if payload.get("cwd"):
        candidates.append(Path(str(payload["cwd"])))
    for wp in payload.get("workspacePaths") or []:
        candidates.append(Path(str(wp)))
    if not candidates:
        candidates.append(Path.cwd())

    for cand in candidates:
        cur = cand.resolve()
        for parent in [cur, *cur.parents]:
            if (parent / ".supermemory").is_dir() or (parent / "memory" / "graph_snapshot.json").is_file():
                return parent
    return None


def dispatch_hook(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the matching Antigravity hook contract and return stdout JSON dict."""
    ev = (event_name or payload.get("hookEventName") or "").strip()
    ws = _resolve_supermemory_workspace(payload)

    if ws is None:
        if ev == "SessionStart":
            return {
                "injectSteps": [
                    {
                        "systemMessage": {
                            "systemMessage": (
                                "SuperMemory Extension is installed. Run `supermemory init` (or invoke skill "
                                "`supermemory-init`) if you want to enable the Persistent Knowledge Graph & "
                                "Anti-Regression Gates in this workspace."
                            )
                        }
                    }
                ]
            }
        if ev == "PreToolUse":
            return {"decision": "allow"}
        return {}

    conv_id = str(payload.get("conversationId") or "default-session")
    with GraphStore(ws) as store:
        if ev == "SessionStart":
            return _on_session_start(store, conv_id)
        if ev == "PreInvocation":
            return _on_pre_invocation(store, conv_id, payload)
        if ev == "PreToolUse":
            return _on_pre_tool_use(store, payload)
        if ev == "PostToolUse":
            return _on_post_tool_use(store, conv_id, payload)
        if ev == "Stop":
            return _on_stop(store, conv_id, payload)
    return {}


def _on_session_start(store: GraphStore, conv_id: str) -> Dict[str, Any]:
    qe = QueryEngine(store)
    capsule = qe.build_session_capsule()
    st = get_session_state(store, conv_id)
    save_session_state(store, st)
    store.log_event("HOOK_SESSION_START", conv_id, "Injected SuperMemory startup capsule")
    return {"injectSteps": [{"systemMessage": {"systemMessage": capsule}}]}


def _on_pre_invocation(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = get_session_state(store, conv_id)
    inv_num = int(payload.get("invocationNum") or 0)
    step_idx = int(payload.get("initialNumSteps") or 0)
    user_input = str(payload.get("lastUserInput") or "")

    injected_msgs = []
    # Detect context compaction (step count dropped significantly between invocations)
    if st["last_step_idx"] > 20 and 0 < step_idx < (st["last_step_idx"] // 2):
        st["compaction_count"] = st.get("compaction_count", 0) + 1
        capsule = QueryEngine(store).build_session_capsule(user_input)
        injected_msgs.append(
            "♻️ COMPACTION RECOVERY DETECTED — FULL SUPERMEMORY STATE RESTORED:\n" + capsule
        )
        store.log_event("COMPACTION_RECOVERY", conv_id, f"Restored state at step {step_idx}")

    # Self-learning signal & anti-repeat recall on first invocation of a new user turn
    if user_input and user_input != st.get("pending_lesson_quote"):
        sig = SelfLearningDetector.analyze(user_input)
        if sig.requires_lesson:
            st["pending_lesson_lock"] = True
            st["pending_lesson_quote"] = user_input
            st["pending_lesson_category"] = sig.category
            injected_msgs.append(sig.guidance)
        elif sig.requires_state_sync:
            injected_msgs.append(sig.guidance)

        rec = QueryEngine(store).recall(user_input, limit=4, hops=1)
        if rec["anti_repeat_warnings"]:
            warn_block = "⚠️ SUPERMEMORY ANTI-REPEAT RECALL (DO NOT REPEAT PAST FAILURES):\n" + "\n".join(
                f"  • {w}" for w in rec["anti_repeat_warnings"][:4]
            )
            injected_msgs.append(warn_block)

    st["invocation_num"] = inv_num
    st["last_step_idx"] = max(step_idx, st["last_step_idx"]) if step_idx >= st["last_step_idx"] else step_idx
    save_session_state(store, st)

    if not injected_msgs:
        return {}
    return {
        "injectSteps": [{"systemMessage": {"systemMessage": "\n\n".join(injected_msgs)}}],
        "terminationBehavior": "",
    }


def _on_pre_tool_use(store: GraphStore, payload: Dict[str, Any]) -> Dict[str, Any]:
    tc = payload.get("toolCall") or {}
    t_name = str(tc.get("name") or "")
    t_args = tc.get("args") or {}
    decision = GateEnforcer(store).evaluate_tool_call(t_name, t_args)
    if not decision.allowed:
        return {
            "decision": "deny",
            "reason": f"🛡️ SUPERMEMORY CONSTITUTIONAL GATE BLOCKED TOOL `{t_name}`: {decision.reason}",
        }
    return {"decision": "allow"}


def _on_post_tool_use(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = get_session_state(store, conv_id)
    tc = payload.get("toolCall") or {}
    t_name = str(tc.get("name") or "").lower()
    t_args = tc.get("args") or {}
    err = str(payload.get("error") or "")

    # Detect when agent records a lesson or syncs memory via CLI or MCP
    cmd = str(t_args.get("CommandLine") or "")
    mcp_tool = str(t_args.get("ToolName") or "")
    if (
        "supermemory learn" in cmd
        or "supermemory_record_lesson" in t_name
        or "supermemory_record_lesson" in mcp_tool
    ) and not err:
        st["pending_lesson_lock"] = False

    if (
        "supermemory sync" in cmd
        or "supermemory exp" in cmd
        or "supermemory_update_state" in t_name
        or "supermemory_update_state" in mcp_tool
        or "supermemory_log_experiment" in t_name
        or "supermemory_log_experiment" in mcp_tool
    ) and not err:
        st["dirty_files"] = []

    if t_name in ("write_file", "edit_file") and not err:
        raw_p = str(t_args.get("Path") or "")
        if raw_p and "memory/" not in raw_p and not raw_p.endswith(("AGENTS.md", "GEMINI.md", "CLAUDE.md")):
            dirty = list(st.get("dirty_files") or [])
            if raw_p not in dirty:
                dirty.append(raw_p)
            st["dirty_files"] = dirty[-20:]
        elif "02_CONSTITUTION_AND_LESSONS.md" in raw_p:
            st["pending_lesson_lock"] = False

    if err:
        store.log_event("TOOL_ERROR_OBSERVED", t_name, f"Tool {t_name} errored: {err[:140]}")

    save_session_state(store, st)
    return {}


def _on_stop(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Respect continuationActive so we never loop more than once per turn
    if payload.get("continuationActive"):
        return {"decision": "allow"}
    if str(payload.get("terminationReason") or "") != "NO_TOOL_CALL":
        return {"decision": "allow"}

    st = get_session_state(store, conv_id)
    if st.get("pending_lesson_lock"):
        st["pending_lesson_lock"] = False
        save_session_state(store, st)
        return {
            "decision": "continue",
            "reason": (
                "🛡️ SUPERMEMORY SELF-LEARNING COMMIT REQUIRED (LAW-08): "
                "The user issued a correction/critique in this turn, and no structured LESSON + CodeGate "
                "was committed yet. Call `supermemory learn` (or MCP `supermemory_record_lesson`) and "
                "`supermemory sync` now before finishing your response."
            ),
        }
    return {"decision": "allow"}


def main_from_stdin(event_name: str) -> int:
    """CLI entrypoint reading Antigravity hook JSON from stdin and printing JSON to stdout."""
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {}
    out = dispatch_hook(event_name, payload)
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0
