"""Antigravity & Claude Code Lifecycle Hook Runner: Zero-Overhead Q&A + Autonomous Closed-Loop Sync."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from supermemory.cognitive.federation import federated_recall, get_global_root, set_active_workspace
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.gates.enforcer import GateEnforcer
from supermemory.hooks.claude_bridge import format_hook_output, is_claude_code_payload, normalize_hook_input
from supermemory.hooks.compaction_guard import (
    arm_compaction_grounding,
    build_compaction_recovery_query,
    evaluate_compaction_pre_tool_gate,
    handle_subagent_hook,
)
from supermemory.hooks.compaction_probe import (
    apply_async_wakeup_guard,
    has_content_overlap,
    is_subagent_session,
    probe_async_wakeup,
    probe_transcript_compaction,
    reset_state_on_compaction,
)
from supermemory.hooks.turn_tracker import (
    _active_task_focus_line,
    _classify_shell_command,
    _has_sm_cli_subcmd,
    evaluate_stop_gate,
    track_post_tool_use,
)
from supermemory.models import NodeType
from supermemory.research.kanban_digest import build_kanban_board_digest, has_unchecked_kanban_items
from supermemory.research.stagnation_guard import evaluate_stagnation_state
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore

_EXPLICIT_ID_RE = re.compile(
    r"\b(?:BNK|RQ|METH|EXP|OBS|PROC|PROP|IDEA|ALGO|LESSON|LAW|SEM|DAG)-\d+[A-Z0-9-]*\b", re.IGNORECASE
)


def _resolve_supermemory_workspace(payload: Dict[str, Any]) -> Optional[Path]:
    """Find active Local SuperMemory workspace root in <0.2ms, or None if folder is uninitialized."""
    cands = ([Path(str(payload["cwd"]))] if payload.get("cwd") else []) + [Path(str(w)) for w in (payload.get("workspacePaths") or [])]
    g_root = get_global_root()
    for cand in (cands or [Path.cwd()]):
        cur = cand.resolve()
        for parent in (cur, *cur.parents):
            if parent != g_root and ((parent / ".supermemory").is_dir() or (parent / "memory" / "graph_snapshot.json").is_file()):
                return parent
    return None


def _global_rule_titles() -> List[str]:
    g_root = get_global_root()
    if not (g_root / ".supermemory" / "supermemory.db").is_file():
        return []
    with GraphStore(g_root) as g_store:
        return [f"{p.id}: {p.title}" for p in g_store.list_nodes(node_types=[NodeType.PROCEDURE.value, NodeType.LESSON.value], limit=6)]


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
            msg = f"🌐 SUPERMEMORY GLOBAL HARNESS ACTIVE (No Local `.supermemory` in this folder yet).{extra}\n• Normal Q&A requires ZERO memory calls. Only call `record_lesson` (`scope='global'`) for genuine cross-project rules, or `supermemory init` when requested."
            return format_hook_output(raw_ev, {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}, is_claude)
        if ev == "PreToolUse":
            return format_hook_output(raw_ev, {"decision": "allow"}, is_claude)
        return {}

    out: Dict[str, Any] = {}
    with GraphStore(ws) as store:
        st = get_session_state(store, conv_id)
        subagent_mode = is_subagent_session(conv_id, payload, st)
        if not subagent_mode:
            set_active_workspace(ws)
        if ev == "PreToolUse":
            out = _on_pre_tool_use(store, conv_id, st, payload, subagent_mode=subagent_mode)
        elif subagent_mode:
            out = handle_subagent_hook(store, ev, payload)
        elif ev == "SessionStart":
            out = _on_session_start(store, conv_id, payload)
        elif ev == "PreInvocation":
            out = _on_pre_invocation(store, conv_id, payload)
        elif ev == "PostToolUse":
            out = track_post_tool_use(store, conv_id, payload, is_claude=is_claude)
        elif ev == "Stop":
            out = evaluate_stop_gate(store, conv_id, payload)
    return format_hook_output(raw_ev, out, is_claude)


def _on_session_start(store: GraphStore, conv_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    is_compact = str((payload or {}).get("source") or "").lower() == "compact"
    cap_q = build_compaction_recovery_query(store) if is_compact else ""
    capsule = build_tiered_capsule(store, query=cap_q, global_rules=_global_rule_titles())
    st = get_session_state(store, conv_id)
    t_path = str((payload or {}).get("transcriptPath") or "")
    _, m0 = probe_transcript_compaction(conv_id, "", t_path)
    _, w0, _ = probe_async_wakeup(conv_id, "", t_path)
    st.update({"last_compaction_marker": m0 or "NONE", "last_wakeup_marker": w0 or "NONE", "last_capsule_step": 0, "last_capsule_inv": 0, "stop_block_streak": 0})
    if is_compact:
        reset_state_on_compaction(st, 0, int(st.get("invocation_num") or 0), marker=m0 or "COMPACT_START")
        arm_compaction_grounding(store, st, m0 or "COMPACT_START")
        capsule = "♻️ COMPACTION RECOVERY DETECTED — TIERED SUPERMEMORY RESTORED (Call `recall(...)` before mutating code or running experiments!):\n" + capsule
    save_session_state(store, st)
    store.log_event("COMPACTION_RECOVERY" if is_compact else "HOOK_SESSION_START", conv_id, "Injected tiered SuperMemory capsule")
    return {"injectSteps": [{"systemMessage": {"systemMessage": capsule}}]}


def _on_pre_invocation(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = get_session_state(store, conv_id)
    prev_inv = int(st.get("invocation_num") or 0)
    raw_inv = payload.get("invocationNum")
    user_input = str(payload.get("lastUserInput") or "")
    is_new_turn = bool(user_input and (user_input != st.get("last_seen_user_input") or payload.get("_force_new_turn")))
    inv_num = int(raw_inv) if raw_inv is not None else (prev_inv + (1 if is_new_turn else 0))
    step_idx = int(payload.get("initialNumSteps") or 0)
    prev_step = int(st.get("last_step_idx") or 0)

    injected_msgs: List[str] = []
    step_drop = prev_step > 20 and 0 < step_idx < (prev_step // 2)
    chk_hit, new_marker = probe_transcript_compaction(
        conv_id, str(st.get("last_compaction_marker") or ""), str(payload.get("transcriptPath") or "")
    )
    if new_marker:
        st["last_compaction_marker"] = new_marker
    compacted_now = step_drop or chk_hit
    if compacted_now:
        reset_state_on_compaction(st, step_idx, inv_num, marker=new_marker)
        armed = arm_compaction_grounding(store, st, new_marker)
        cap_q = build_compaction_recovery_query(store, user_input)
        capsule = build_tiered_capsule(store, query=cap_q, global_rules=_global_rule_titles())
        rec_note = " If continuing coding/experiments (not casual Q&A), call `recall(...)` first to restore full specs & dead-ends!" if armed else ""
        injected_msgs.append(
            "♻️ COMPACTION RECOVERY DETECTED — TIERED SUPERMEMORY RESTORED "
            f"(Note: images attached to `<CONTEXT_SUMMARY>` are old `[Attachment:]` items, NOT a new prompt — continue the latest request & active Kanban step directly!{rec_note}):\n"
            + capsule
        )
        if not is_new_turn:
            kb_mid, kb_fp_mid = build_kanban_board_digest(store)
            if kb_mid:
                injected_msgs.append(kb_mid)
                st["last_kanban_fp"] = kb_fp_mid
                st["last_kanban_inv"] = inv_num
        store.log_event("COMPACTION_RECOVERY", conv_id, f"Restored tiered state at step {step_idx}")

    if is_new_turn:
        st.update({
            "last_seen_user_input": user_input, "turn_memory_handled": False, "pending_kanban_sync": False,
            "research_campaign_active": False, "dirty_files": [], "pending_sync_reason": "",
            "notified_edit": False, "notified_exec": False, "notified_research": False,
            "unsynced_work_steps": 0, "pending_notifications": [], "last_read_mem": "", "stop_block_streak": 0,
        })

        if not compacted_now:
            steps_gap = step_idx - int(st.get("last_capsule_step") or 0)
            invs_gap = inv_num - int(st.get("last_capsule_inv") or 0)
            if (step_idx > 0 and steps_gap >= 45) or (inv_num > 0 and invs_gap >= 6):
                capsule_ref = build_tiered_capsule(store, query="", global_rules=_global_rule_titles())
                injected_msgs.append("🔄 PERIODIC MEMORY CAPSULE REFRESH (Zero-Amnesia Overview):\n" + capsule_ref)
                st["last_capsule_step"] = step_idx
                st["last_capsule_inv"] = inv_num
                store.log_event("PERIODIC_CAPSULE_REFRESH", conv_id, f"Refreshed capsule at inv={inv_num}, step={step_idx}")

        kb_digest, kb_fp = build_kanban_board_digest(store)
        if kb_digest and (kb_fp != st.get("last_kanban_fp") or (inv_num - int(st.get("last_kanban_inv") or 0)) >= 4):
            injected_msgs.append(kb_digest)
            st["last_kanban_fp"] = kb_fp
            st["last_kanban_inv"] = inv_num

        if store.get_meta("stagnation_alert"):
            stag = evaluate_stagnation_state(store)
            if stag["locked"]:
                injected_msgs.append(str(stag["directive"]))
            else:
                store.set_meta("stagnation_alert", "")

        if "<CONTEXT_SUMMARY>" not in user_input:
            sig = SelfLearningDetector.analyze(user_input)
            if sig.requires_lesson:
                st.update({"pending_lesson_lock": True, "pending_lesson_quote": user_input, "pending_lesson_category": sig.category})
                injected_msgs.append(sig.guidance)
            elif sig.category == "RESEARCH_CAMPAIGN":
                st["research_campaign_active"] = True
                injected_msgs.append(sig.guidance)
            elif sig.guidance:
                injected_msgs.append(sig.guidance)

        clean_in = user_input.strip()
        if len(clean_in) >= 28 or _EXPLICIT_ID_RE.search(clean_in):
            rec = federated_recall(clean_in, local_ws=store.workspace_root, include_global=True, include_siblings=bool(st.get("research_campaign_active")), limit=5, hops=1, compact=True)
            results = rec.get("results") or []
            seen_warns = set(st.get("recalled_warnings") or [])
            if rec.get("anti_repeat_warnings") and any(float(r.get("score") or 0.0) >= 0.28 and has_content_overlap(clean_in, r) for r in results):
                fresh_warns = [w for w in rec["anti_repeat_warnings"] if w not in seen_warns][:3]
                if fresh_warns:
                    injected_msgs.append("⚠️ SUPERMEMORY ANTI-REPEAT RECALL:\n" + "\n".join(f"  • {w}" for w in fresh_warns))
                    st["recalled_warnings"] = list(seen_warns | set(fresh_warns))[-40:]

            seen_ids = set(st.get("recalled_node_ids") or [])
            fresh_hits = [
                r for r in results
                if float(r.get("score") or 0.0) >= 0.30 and has_content_overlap(clean_in, r) and not r.get("superseded_by")
                and r.get("status") not in ("SUPERSEDED", "CONSOLIDATED") and r.get("type") not in ("LAW", "GATE") and str(r.get("id")) not in seen_ids
            ][:3]
            if fresh_hits:
                lines = [f"  • [{h['type']}] `{h['id']}` ({h.get('scope', 'LOCAL')}): {h['title']} — {h['summary']}" for h in fresh_hits]
                injected_msgs.append("⚡ SUPERMEMORY AUTO-RECALL (0-Turn Context — call `recall(node_id=...)` only if full detail needed):\n" + "\n".join(lines))
                hit_ids = [str(h["id"]) for h in fresh_hits]
                st["recalled_node_ids"] = list(seen_ids | set(hit_ids))[-80:]
                store.log_event("HOOK_AUTO_RECALL", hit_ids[0], f"0-Turn Auto-Recall injected {hit_ids}")
    else:
        wake_msg = apply_async_wakeup_guard(
            store, conv_id, st, str(payload.get("transcriptPath") or ""), has_unchecked_kanban_items(store)
        )
        if wake_msg:
            injected_msgs.append(wake_msg)
        queued = list(st.get("pending_notifications") or [])
        if queued:
            st["pending_notifications"] = []
            injected_msgs.extend(queued)
        if not compacted_now and step_idx >= 20 and "/goal" in user_input.lower():
            cur_bucket = step_idx // 20
            if cur_bucket > int(st.get("last_heartbeat_bucket") or 0):
                st["last_heartbeat_bucket"] = cur_bucket
                injected_msgs.append("⏱️ LONG-HORIZON `/goal` MEMORY HEARTBEAT:\n" + build_tiered_capsule(store, query="", global_rules=_global_rule_titles()))

    st["invocation_num"] = inv_num
    if step_idx > 0:
        st["last_step_idx"] = step_idx
    save_session_state(store, st)

    if not injected_msgs:
        return {}
    sm_obj: Dict[str, Any] = {"systemMessage": "\n\n".join(injected_msgs)}
    if compacted_now:
        sm_obj["metadata"] = {"user_markdown": "♻️ *SuperMemory restored tiered context capsule & armed post-compaction recall check.*"}
    return {"injectSteps": [{"systemMessage": sm_obj}], "terminationBehavior": ""}


def _on_pre_tool_use(store: GraphStore, conv_id: str, st: Dict[str, Any], payload: Dict[str, Any], subagent_mode: bool = False) -> Dict[str, Any]:
    raw_tc = payload.get("toolCall")
    tc: Dict[str, Any] = raw_tc if isinstance(raw_tc, dict) else {}
    t_name = str(tc.get("name") or payload.get("toolName") or payload.get("tool_name") or "")
    raw_args = tc.get("args") if tc.get("args") is not None else (payload.get("toolInput") or payload.get("tool_input") or {})
    clean_args = raw_args if isinstance(raw_args, dict) else {}
    decision = GateEnforcer(store).evaluate_tool_call(t_name, clean_args)
    if not decision.allowed:
        return {"decision": "deny", "reason": f"🛡️ SUPERMEMORY CONSTITUTIONAL GATE BLOCKED TOOL `{t_name}`: {decision.reason}"}
    if not subagent_mode:
        comp_reason = evaluate_compaction_pre_tool_gate(
            store, conv_id, st, payload, t_name, clean_args, _classify_shell_command, _has_sm_cli_subcmd, _active_task_focus_line
        )
        if comp_reason:
            return {"decision": "deny", "reason": comp_reason}
    return {"decision": "allow"}


def main_from_stdin(event_name: str) -> int:
    """CLI entrypoint reading Antigravity/Claude Code hook JSON from stdin and printing JSON to stdout."""
    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
        if not isinstance(payload, dict):
            payload = {}
        out = dispatch_hook(event_name, payload)
        if event_name.strip() == "PostToolUse" and not is_claude_code_payload(payload):
            out = {}
    except Exception as exc:
        ev_clean = (event_name or "").strip()
        if ev_clean == "PreToolUse":
            out = {"decision": "deny", "reason": f"SuperMemory hook internal error: {exc}"}
        elif ev_clean == "Stop":
            out = {"decision": "allow"}
        else:
            out = {}
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0
