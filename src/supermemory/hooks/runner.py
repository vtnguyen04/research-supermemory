"""Antigravity & Claude Code Lifecycle Hook Runner: Zero-Overhead Q&A + Autonomous Closed-Loop Sync."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from supermemory.cognitive.federation import ensure_global_memory, federated_recall, set_active_workspace
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.gates.enforcer import GateEnforcer
from supermemory.hooks.claude_bridge import format_hook_output, normalize_hook_input
from supermemory.hooks.turn_tracker import evaluate_stop_gate, track_post_tool_use
from supermemory.models import NodeType
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore


def _resolve_supermemory_workspace(payload: Dict[str, Any]) -> Optional[Path]:
    """Find active Local SuperMemory workspace root, or None if folder is uninitialized."""
    candidates = []
    if payload.get("cwd"):
        candidates.append(Path(str(payload["cwd"])))
    for wp in payload.get("workspacePaths") or []:
        candidates.append(Path(str(wp)))
    if not candidates:
        candidates.append(Path.cwd())

    g_root = ensure_global_memory()
    for cand in candidates:
        cur = cand.resolve()
        for parent in [cur, *cur.parents]:
            if parent == g_root:
                continue
            if (parent / ".supermemory").is_dir() or (parent / "memory" / "graph_snapshot.json").is_file():
                return parent
    return None


def _global_rule_titles() -> List[str]:
    g_root = ensure_global_memory()
    with GraphStore(g_root) as g_store:
        procs = g_store.list_nodes(node_types=[NodeType.PROCEDURE.value, NodeType.LESSON.value], limit=6)
        return [f"{p.id}: {p.title}" for p in procs]


def dispatch_hook(event_name: str, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Antigravity & Claude Code hook contracts across Local + Global SuperMemory."""
    raw_ev = (event_name or raw_payload.get("hookEventName") or raw_payload.get("hook_event_name") or "").strip()
    ev, payload, is_claude = normalize_hook_input(raw_ev, raw_payload)
    ws = _resolve_supermemory_workspace(payload)
    conv_id = str(payload.get("conversationId") or "default-session")

    if ws is None:
        if ev == "SessionStart":
            g_titles = _global_rule_titles()
            extra = ("\n• Global Learned Rules: " + " | ".join(g_titles[:4])) if g_titles else ""
            msg = (
                "🌐 SUPERMEMORY GLOBAL HARNESS ACTIVE (No Local `.supermemory` in this folder yet)."
                f"{extra}\n• Normal Q&A requires ZERO memory calls. Only call `record_lesson` "
                "(`scope='global'`) for genuine cross-project rules, or `supermemory init` when requested."
            )
            return format_hook_output(raw_ev, {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}, is_claude)
        if ev == "PreToolUse":
            return format_hook_output(raw_ev, {"decision": "allow"}, is_claude)
        return {}

    out: Dict[str, Any] = {}
    with GraphStore(ws) as store:
        set_active_workspace(ws)
        if ev == "SessionStart":
            out = _on_session_start(store, conv_id)
        elif ev == "PreInvocation":
            out = _on_pre_invocation(store, conv_id, payload)
        elif ev == "PreToolUse":
            out = _on_pre_tool_use(store, payload)
        elif ev == "PostToolUse":
            out = track_post_tool_use(store, conv_id, payload)
        elif ev == "Stop":
            out = evaluate_stop_gate(store, conv_id, payload)
    return format_hook_output(raw_ev, out, is_claude)


def _on_session_start(store: GraphStore, conv_id: str) -> Dict[str, Any]:
    capsule = build_tiered_capsule(store, global_rules=_global_rule_titles())
    st = get_session_state(store, conv_id)
    save_session_state(store, st)
    store.log_event("HOOK_SESSION_START", conv_id, "Injected tiered SuperMemory capsule")
    return {"injectSteps": [{"systemMessage": {"systemMessage": capsule}}]}


def _on_pre_invocation(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = get_session_state(store, conv_id)
    inv_num = int(payload.get("invocationNum") or 0)
    step_idx = int(payload.get("initialNumSteps") or 0)
    prev_step = int(st.get("last_step_idx") or 0)
    user_input = str(payload.get("lastUserInput") or "")

    injected_msgs: List[str] = []
    if prev_step > 20 and 0 < step_idx < (prev_step // 2):
        st["compaction_count"] = st.get("compaction_count", 0) + 1
        st["last_heartbeat_bucket"] = 0
        capsule = build_tiered_capsule(store, query=user_input, global_rules=_global_rule_titles())
        injected_msgs.append("♻️ COMPACTION RECOVERY DETECTED — TIERED SUPERMEMORY RESTORED:\n" + capsule)
        store.log_event("COMPACTION_RECOVERY", conv_id, f"Restored tiered state at step {step_idx}")

    if user_input and user_input != st.get("last_seen_user_input"):
        st["last_seen_user_input"] = user_input
        st["turn_memory_handled"] = False
        st["research_campaign_active"] = False
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""
        st["notified_edit"] = False
        st["notified_exec"] = False
        st["notified_research"] = False

        sig = SelfLearningDetector.analyze(user_input)
        if sig.requires_lesson:
            st["pending_lesson_lock"] = True
            st["pending_lesson_quote"] = user_input
            st["pending_lesson_category"] = sig.category
            injected_msgs.append(sig.guidance)
        elif sig.category == "RESEARCH_CAMPAIGN":
            st["research_campaign_active"] = True
            injected_msgs.append(sig.guidance)
        elif sig.guidance:
            injected_msgs.append(sig.guidance)

        if len(user_input.strip()) >= 28:
            rec = federated_recall(
                user_input,
                local_ws=store.workspace_root,
                include_global=True,
                include_siblings=bool(st.get("research_campaign_active")),
                limit=3,
                hops=1,
            )
            high_hit = any(float(r.get("score") or 0) >= 8.5 for r in rec.get("results") or [])
            if high_hit and rec["anti_repeat_warnings"]:
                warn_block = "⚠️ SUPERMEMORY ANTI-REPEAT RECALL:\n" + "\n".join(
                    f"  • {w}" for w in rec["anti_repeat_warnings"][:3]
                )
                injected_msgs.append(warn_block)
    elif step_idx >= 20 and "/goal" in user_input.lower():
        cur_bucket = step_idx // 20
        prev_bucket = int(st.get("last_heartbeat_bucket") or 0)
        if cur_bucket > prev_bucket:
            st["last_heartbeat_bucket"] = cur_bucket
            capsule = build_tiered_capsule(store, query=user_input, global_rules=_global_rule_titles())
            injected_msgs.append("⏱️ LONG-HORIZON `/goal` MEMORY HEARTBEAT (ANTI-DRIFT & ANTI-REPEAT):\n" + capsule)

    st["invocation_num"] = inv_num
    if step_idx > 0:
        st["last_step_idx"] = step_idx
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


def main_from_stdin(event_name: str) -> int:
    """CLI entrypoint reading Antigravity/Claude Code hook JSON from stdin and printing JSON to stdout."""
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {}
    out = dispatch_hook(event_name, payload)
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0
