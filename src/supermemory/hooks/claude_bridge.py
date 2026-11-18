"""Dual-Harness Hook Bridge: Normalizes Claude Code & Antigravity hook stdin/stdout JSON."""

from __future__ import annotations

from typing import Any, Dict, Tuple


def is_claude_code_payload(payload: Dict[str, Any]) -> bool:
    """Detect whether the stdin hook payload originated from Claude Code CLI/IDE."""
    return bool(
        "hook_event_name" in payload
        or "session_id" in payload
        or "tool_name" in payload
        or "stop_hook_active" in payload
        or "transcript_path" in payload
    )


def normalize_hook_input(event_name: str, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool]:
    """Translate Claude Code snake_case hook payloads into canonical SuperMemory hook fields."""
    is_claude = is_claude_code_payload(payload)
    raw_ev = (event_name or payload.get("hookEventName") or payload.get("hook_event_name") or "").strip()
    norm_ev = "PreInvocation" if raw_ev == "UserPromptSubmit" else raw_ev
    if not is_claude:
        return norm_ev, payload, False

    norm: Dict[str, Any] = dict(payload)
    norm["hookEventName"] = norm_ev
    if payload.get("session_id") and not norm.get("conversationId"):
        norm["conversationId"] = str(payload["session_id"])
    if payload.get("transcript_path") and not norm.get("transcriptPath"):
        norm["transcriptPath"] = str(payload["transcript_path"])

    if norm_ev == "PreInvocation":
        prompt_txt = str(payload.get("prompt") or payload.get("user_prompt") or "")
        if prompt_txt and not norm.get("lastUserInput"):
            norm["lastUserInput"] = prompt_txt
        if raw_ev == "UserPromptSubmit":
            norm["_force_new_turn"] = True

    if norm_ev in ("PreToolUse", "PostToolUse") and not norm.get("toolCall"):
        t_name = str(payload.get("tool_name") or "")
        t_in = payload.get("tool_input")
        norm["toolCall"] = {
            "name": t_name,
            "args": t_in if isinstance(t_in, dict) else {},
        }
        t_out = payload.get("tool_response") or payload.get("tool_output")
        if isinstance(t_out, dict):
            if t_out.get("stdout") or t_out.get("output"):
                norm["output"] = str(t_out.get("stdout") or t_out.get("output"))
            if t_out.get("is_error") or (t_out.get("exit_code") not in (None, 0)):
                norm["error"] = str(t_out.get("stderr") or t_out.get("error") or f"exit_code={t_out.get('exit_code')}")
        elif isinstance(t_out, str) and t_out:
            norm["output"] = t_out

    if norm_ev == "Stop":
        norm["continuationActive"] = bool(payload.get("stop_hook_active"))
        norm.setdefault("terminationReason", "NO_TOOL_CALL")

    return norm_ev, norm, True


def format_hook_output(raw_event: str, out: Dict[str, Any], is_claude: bool) -> Dict[str, Any]:
    """Convert canonical SuperMemory hook response into Claude Code or Antigravity schema."""
    if not is_claude:
        return out

    ev_name = (raw_event or "").strip()
    if ev_name in ("SessionStart", "UserPromptSubmit", "PreInvocation", "PostToolUse"):
        steps = out.get("injectSteps") or []
        msgs = []
        for s in steps:
            if isinstance(s, dict):
                sm = s.get("systemMessage")
                if isinstance(sm, dict) and sm.get("systemMessage"):
                    msgs.append(str(sm["systemMessage"]))
        if not msgs:
            return {}
        hook_label = "UserPromptSubmit" if ev_name in ("UserPromptSubmit", "PreInvocation") else ev_name
        return {
            "hookSpecificOutput": {
                "hookEventName": hook_label,
                "additionalContext": "\n\n".join(msgs),
            }
        }

    if ev_name == "PreToolUse":
        if out.get("decision") == "deny":
            reason = str(out.get("reason") or "Blocked by SuperMemory CodeGate")
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
                "decision": "block",
                "reason": reason,
            }
        return {}

    if ev_name == "Stop":
        if out.get("decision") == "continue":
            return {
                "decision": "block",
                "reason": str(out.get("reason") or "SuperMemory commit required before stopping."),
            }
        return {}

    return {}
