"""Antigravity Lifecycle Hook Runner: Federated Global/Local + Agent-Native Semantic Self-Triage."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from supermemory.cognitive.federation import ensure_global_memory, federated_recall
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.gates.enforcer import GateEnforcer
from supermemory.models import NodeType
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore

_BENCHMARK_CMD_RE = re.compile(
    r"\b(?:python3?|uv\s+run|bash|sh)\b.*\b(?:train|eval|evaluate|benchmark|ablation|run_submission|run_exp)\w*",
    flags=re.IGNORECASE,
)


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


def dispatch_hook(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Antigravity hook contract across Local + Global Federated SuperMemory."""
    ev = (event_name or payload.get("hookEventName") or "").strip()
    ws = _resolve_supermemory_workspace(payload)
    conv_id = str(payload.get("conversationId") or "default-session")

    # Uninitialized project mode: use Global SuperMemory cleanly without polluting the folder!
    if ws is None:
        if ev == "SessionStart":
            g_titles = _global_rule_titles()
            extra = ("\n• Global Learned Rules: " + " | ".join(g_titles[:4])) if g_titles else ""
            msg = (
                "🌐 SUPERMEMORY GLOBAL HARNESS ACTIVE (No Local `.supermemory` in this folder yet)."
                f"{extra}\n• Save cross-project preferences with `scope='global'`, or run `supermemory init` "
                "(MCP `supermemory_init`) to create an isolated Local SuperMemory for this project."
            )
            return {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}
        if ev == "PreInvocation":
            u_in = str(payload.get("lastUserInput") or "").strip()
            if len(u_in) >= 8:
                rec = federated_recall(u_in, local_ws=None, include_global=True, limit=3)
                if rec["anti_repeat_warnings"]:
                    w_txt = "⚠️ GLOBAL SUPERMEMORY RECALL:\n" + "\n".join(f"  • {w}" for w in rec["anti_repeat_warnings"][:3])
                    return {"injectSteps": [{"systemMessage": {"systemMessage": w_txt}}]}
            return {}
        if ev == "PreToolUse":
            return {"decision": "allow"}
        return {}

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
    capsule = build_tiered_capsule(store, global_rules=_global_rule_titles())
    st = get_session_state(store, conv_id)
    save_session_state(store, st)
    store.log_event("HOOK_SESSION_START", conv_id, "Injected tiered SuperMemory capsule")
    return {"injectSteps": [{"systemMessage": {"systemMessage": capsule}}]}


def _on_pre_invocation(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = get_session_state(store, conv_id)
    inv_num = int(payload.get("invocationNum") or 0)
    step_idx = int(payload.get("initialNumSteps") or 0)
    user_input = str(payload.get("lastUserInput") or "")

    injected_msgs: List[str] = []
    if st["last_step_idx"] > 20 and 0 < step_idx < (st["last_step_idx"] // 2):
        st["compaction_count"] = st.get("compaction_count", 0) + 1
        capsule = build_tiered_capsule(store, query=user_input, global_rules=_global_rule_titles())
        injected_msgs.append("♻️ COMPACTION RECOVERY DETECTED — TIERED SUPERMEMORY RESTORED:\n" + capsule)
        store.log_event("COMPACTION_RECOVERY", conv_id, f"Restored tiered state at step {step_idx}")

    if user_input and user_input != st.get("last_seen_user_input"):
        st["last_seen_user_input"] = user_input
        st["turn_memory_handled"] = False
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""

        # Optional fast hint (advisory — LLM semantic triage covers 100% of phrasings!)
        sig = SelfLearningDetector.analyze(user_input)
        if sig.requires_lesson:
            st["pending_lesson_lock"] = True
            st["pending_lesson_quote"] = user_input
            st["pending_lesson_category"] = sig.category
            injected_msgs.append(sig.guidance)
        else:
            injected_msgs.append(
                "🧠 SEMANTIC MEMORY TRIAGE ACTIVE: Autonomously evaluate user intent & tool outcomes this turn — "
                "persist any implicit/explicit critique (`supermemory_record_lesson`), new rule/procedure "
                "(`supermemory_record_lesson` / `supermemory_add_gate`, local or `scope='global'`), experiment/bug "
                "insight (`supermemory_log_experiment` / `supermemory_link_knowledge`), or state update "
                "(`supermemory_update_state`); if pure read-only Q&A, call `supermemory_checkpoint`."
            )

        rec = federated_recall(user_input, local_ws=store.workspace_root, include_global=True, limit=4, hops=1)
        if rec["anti_repeat_warnings"]:
            warn_block = "⚠️ SUPERMEMORY ANTI-REPEAT RECALL (LOCAL + GLOBAL):\n" + "\n".join(
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

    cmd = str(t_args.get("CommandLine") or t_args.get("command") or "")
    mcp_tool = str(t_args.get("ToolName") or "").lower()
    combined = f"{t_name} {mcp_tool}"

    if (
        "supermemory learn" in cmd
        or "supermemory gate" in cmd
        or "supermemory_record_lesson" in combined
        or "supermemory_add_gate" in combined
    ) and not err:
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True

    sm_cli = ("supermemory sync", "supermemory exp", "supermemory learn", "supermemory idea", "supermemory proposal", "supermemory gate", "supermemory checkpoint", "supermemory consolidate", "supermemory promote")
    sm_mcp = ("supermemory_update_state", "supermemory_log_experiment", "supermemory_record_lesson", "supermemory_link_knowledge", "supermemory_manage_proposal", "supermemory_propose_idea", "supermemory_add_gate", "supermemory_checkpoint", "supermemory_consolidate")

    if (any(m in cmd for m in sm_cli) or any(m in combined for m in sm_mcp)) and not err:
        st["turn_memory_handled"] = True
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""
    elif t_name in ("run_command", "bash") and _BENCHMARK_CMD_RE.search(cmd):
        st["pending_sync_reason"] = f"Benchmark/experiment executed (`{cmd[:60]}`)"

    if t_name in ("write_file", "edit_file", "replace_file_content", "multi_replace_file_content") and not err:
        raw_p = str(t_args.get("Path") or t_args.get("TargetFile") or "")
        if raw_p and "memory/" not in raw_p and "/brain/" not in raw_p and not raw_p.endswith(("AGENTS.md", "GEMINI.md", "CLAUDE.md")):
            dirty = list(st.get("dirty_files") or [])
            if raw_p not in dirty:
                dirty.append(raw_p)
            st["dirty_files"] = dirty[-20:]
        elif "02_CONSTITUTION_AND_LESSONS.md" in raw_p:
            st["pending_lesson_lock"] = False
            st["turn_memory_handled"] = True

    if err:
        store.log_event("TOOL_ERROR_OBSERVED", t_name, f"Tool {t_name} errored: {err[:140]}")

    save_session_state(store, st)
    return {}


def _on_stop(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("continuationActive"):
        return {"decision": "allow"}
    if str(payload.get("terminationReason") or "") != "NO_TOOL_CALL":
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
                "Persist the lesson/rule + CodeGate via `supermemory learn` / `supermemory_record_lesson` "
                "(or `supermemory_add_gate`) before finishing your response."
            ),
        }

    has_unhandled_work = bool(st.get("pending_sync_reason") or st.get("dirty_files") or len(str(st.get("last_seen_user_input") or "")) >= 15)
    if not st.get("turn_memory_handled") and has_unhandled_work:
        st["turn_memory_handled"] = True
        st["pending_sync_reason"] = ""
        st["dirty_files"] = []
        save_session_state(store, st)
        return {
            "decision": "continue",
            "reason": (
                "🧠 SUPERMEMORY SEMANTIC TURN-ATTESTATION REQUIRED: "
                "Use your semantic understanding (not regexes) to audit this turn before stopping: "
                "(1) Any subtle/explicit user critique or mistake? -> `supermemory_record_lesson`. "
                "(2) Any new user rule, convention, or procedure? -> `supermemory_record_lesson` / `supermemory_add_gate` (local or `scope='global'`). "
                "(3) Any failed experiment, bug root-cause, or insight? -> `supermemory_log_experiment` / `supermemory_link_knowledge`. "
                "(4) Code/project state changed? -> `supermemory_update_state`. "
                "(5) Pure read-only Q&A with zero memory delta? -> `supermemory_checkpoint(status='CLEAN')`."
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
