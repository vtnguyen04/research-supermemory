"""Antigravity Lifecycle Hook Runner: Zero-Overhead Normal Turns + Event-Driven Gates."""

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

    if ws is None:
        if ev == "SessionStart":
            g_titles = _global_rule_titles()
            extra = ("\n• Global Learned Rules: " + " | ".join(g_titles[:4])) if g_titles else ""
            msg = (
                "🌐 SUPERMEMORY GLOBAL HARNESS ACTIVE (No Local `.supermemory` in this folder yet)."
                f"{extra}\n• Normal Q&A requires ZERO memory calls. Only call `record_lesson` "
                "(`scope='global'`) for genuine cross-project rules, or `supermemory init` when requested."
            )
            return {"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}
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
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""

        sig = SelfLearningDetector.analyze(user_input)
        if sig.requires_lesson:
            st["pending_lesson_lock"] = True
            st["pending_lesson_quote"] = user_input
            st["pending_lesson_category"] = sig.category
            injected_msgs.append(sig.guidance)

        # Only inject anti-repeat recall if query is substantial and hits a concrete high-BM25 warning
        if len(user_input.strip()) >= 28:
            rec = federated_recall(user_input, local_ws=store.workspace_root, include_global=True, limit=3, hops=1)
            high_hit = any(float(r.get("score") or 0) >= 8.5 for r in rec.get("results") or [])
            if high_hit and rec["anti_repeat_warnings"]:
                warn_block = "⚠️ SUPERMEMORY ANTI-REPEAT RECALL:\n" + "\n".join(
                    f"  • {w}" for w in rec["anti_repeat_warnings"][:3]
                )
                injected_msgs.append(warn_block)
    elif step_idx >= 20 and "/goal" in user_input.lower():
        # Long-horizon `/goal` heartbeat ONLY for `/goal` campaigns, once per 20-step bucket (never on step_idx=0!)
        cur_bucket = step_idx // 20
        prev_bucket = int(st.get("last_heartbeat_bucket") or 0)
        if cur_bucket > prev_bucket:
            st["last_heartbeat_bucket"] = cur_bucket
            capsule = build_tiered_capsule(store, query=user_input, global_rules=_global_rule_titles())
            injected_msgs.append("⏱️ LONG-HORIZON `/goal` MEMORY HEARTBEAT (ANTI-DRIFT & ANTI-REPEAT):\n" + capsule)

    st["invocation_num"] = inv_num
    # CRITICAL FIX: Never reset last_step_idx to 0 when intra-turn tool steps omit initialNumSteps!
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


def _on_post_tool_use(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = get_session_state(store, conv_id)
    tc = payload.get("toolCall") or {}
    t_name = str(tc.get("name") or "").lower()
    t_args = tc.get("args") or {}
    err = str(payload.get("error") or "")

    cmd = str(t_args.get("CommandLine") or t_args.get("command") or "")
    mcp_srv = str(t_args.get("ServerName") or "").lower()
    mcp_tool = str(t_args.get("ToolName") or "").lower()
    is_sm_mcp = "supermemory" in t_name or "supermemory" in mcp_srv or mcp_tool.startswith("supermemory_")
    norm_mcp = mcp_tool[12:] if mcp_tool.startswith("supermemory_") else mcp_tool

    if (
        "supermemory learn" in cmd
        or "supermemory gate" in cmd
        or (is_sm_mcp and (norm_mcp in ("record_lesson", "add_gate") or "record_lesson" in t_name or "add_gate" in t_name))
    ) and not err:
        st["pending_lesson_lock"] = False
        st["turn_memory_handled"] = True

    sm_cli = ("supermemory sync", "supermemory exp", "supermemory learn", "supermemory idea", "supermemory proposal", "supermemory gate", "supermemory checkpoint", "supermemory consolidate", "supermemory promote", "supermemory bottleneck", "supermemory scout", "supermemory orchestrate")
    sm_mcp = ("update_state", "log_experiment", "record_lesson", "link_knowledge", "manage_proposal", "propose_idea", "add_gate", "checkpoint", "consolidate", "diagnose_bottleneck", "scout_sota", "orchestrate")

    if (any(m in cmd for m in sm_cli) or (is_sm_mcp and (norm_mcp in sm_mcp or any(m in t_name for m in sm_mcp)))) and not err:
        st["turn_memory_handled"] = True
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""
    elif t_name in ("run_command", "bash") and _BENCHMARK_CMD_RE.search(cmd):
        st["pending_sync_reason"] = f"Benchmark/experiment executed (`{cmd[:60]}`)"
        st["turn_memory_handled"] = False

    if t_name in ("write_file", "edit_file", "replace_file_content", "multi_replace_file_content") and not err:
        raw_p = str(t_args.get("Path") or t_args.get("TargetFile") or "")
        if "02_CONSTITUTION_AND_LESSONS.md" in raw_p:
            st["pending_lesson_lock"] = False
            st["turn_memory_handled"] = True

    if err:
        store.log_event("TOOL_ERROR_OBSERVED", t_name, f"Tool {t_name} errored: {err[:140]}")

    save_session_state(store, st)
    return {}


def _on_stop(store: GraphStore, conv_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Zero-overhead Stop gate: NEVER block normal Q&A/chat! Only enforce pending explicit lessons or unlogged benchmarks."""
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
                "Persist the explicit lesson/rule + CodeGate via `supermemory learn` or MCP `record_lesson` "
                "before finishing your response."
            ),
        }

    if not st.get("turn_memory_handled") and st.get("pending_sync_reason"):
        reason_txt = str(st.get("pending_sync_reason"))
        st["turn_memory_handled"] = True
        st["pending_sync_reason"] = ""
        save_session_state(store, st)
        return {
            "decision": "continue",
            "reason": (
                f"🧪 SUPERMEMORY EXPERIMENT LOG REQUIRED: {reason_txt} ran this turn without logging. "
                "Record the experiment result & insights via MCP `log_experiment` (`supermemory exp`) before stopping."
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
