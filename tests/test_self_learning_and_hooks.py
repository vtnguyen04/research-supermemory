"""Tests for Bilingual Self-Learning Detector, Lesson-to-Gate Consolidator, and Antigravity Hooks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from supermemory.bootstrap import init_workspace
from supermemory.gates.enforcer import GateEnforcer
from supermemory.hooks.runner import dispatch_hook
from supermemory.self_learning.consolidator import LessonConsolidator
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.sqlite_store import GraphStore

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bilingual_self_learning_detector() -> None:
    s1 = SelfLearningDetector.analyze("Tại sao mày lại hardcode sửa trực tiếp trên tập test hả?!")
    assert s1.requires_lesson is True
    assert s1.category == "HARDCODING_LEAKAGE"
    assert s1.suggested_law_id == "LAW-01"

    s2 = SelfLearningDetector.analyze("Mày chạy kiểu gì đốt tiền API quá, quên bật prompt caching à?")
    assert s2.requires_lesson is True
    assert s2.category == "COST_CACHE_WASTE"
    assert s2.suggested_law_id == "LAW-04"

    s3 = SelfLearningDetector.analyze("Why did you repeat that bug? You forgot to save into memory!")
    assert s3.requires_lesson is True

    s4 = SelfLearningDetector.analyze(
        "Thiết kế hệ thống theo kiến trúc 3 tầng và vòng đời proposal rõ ràng cho toàn bộ dự án này."
    )
    assert s4.requires_lesson is False
    assert s4.requires_state_sync is True
    assert s4.category == "ARCHITECTURE_SPEC"


def test_pre_tool_use_gates_and_frozen_sha256(tmp_path: Path) -> None:
    init_workspace(tmp_path, project_name="GateTest", max_lines=300)
    eval_script = tmp_path / "src" / "evaluator.py"
    eval_script.parent.mkdir(parents=True, exist_ok=True)
    eval_script.write_text("def score(pred, gold):\n    return int(pred == gold)\n", encoding="utf-8")

    with GraphStore(tmp_path) as store:
        GateEnforcer(store).freeze_file("src/evaluator.py", law_id="LAW-05")
        LessonConsolidator(store).record_lesson(
            title="Ban hardcoded test IDs",
            mistake="Matched test_id_042 directly in solver",
            root_cause="Shortcut symptom patch instead of general parser",
            prevention_rule="Never branch on specific benchmark question IDs",
            law_id="LAW-01",
            forbid_regex=r"test_id_\d+",
            target_glob="src/**/*.py",
        )

    # 1. Block >= 300 line write_file
    bloated = "\n".join(f"x_{i} = {i}" for i in range(305))
    r_bloat = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(tmp_path)],
            "toolCall": {"name": "write_file", "args": {"Path": str(tmp_path / "src" / "big.py"), "Content": bloated}},
        },
    )
    assert r_bloat["decision"] == "deny"
    assert "305 lines" in r_bloat["reason"]

    # 2. Block throwaway debug_*.py filename
    r_tmp = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(tmp_path)],
            "toolCall": {"name": "write_file", "args": {"Path": str(tmp_path / "debug_quick.py"), "Content": "a = 1\n"}},
        },
    )
    assert r_tmp["decision"] == "deny"

    # 3. Block mutation of SHA-256 frozen evaluator
    r_sha = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(tmp_path)],
            "toolCall": {
                "name": "edit_file",
                "args": {"Path": str(eval_script), "Target": "pred == gold", "Replacement": "True"},
            },
        },
    )
    assert r_sha["decision"] == "deny"
    assert "FROZEN FILE VIOLATION" in r_sha["reason"]

    # 4. Block self-learned forbidden regex
    r_reg = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(tmp_path)],
            "toolCall": {
                "name": "write_file",
                "args": {"Path": str(tmp_path / "src" / "solver.py"), "Content": "if q == 'test_id_042':\n    pass\n"},
            },
        },
    )
    assert r_reg["decision"] == "deny"
    assert "Ban hardcoded test IDs" in r_reg["reason"]

    # 5. Block Python SyntaxError before touching disk
    r_syn = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(tmp_path)],
            "toolCall": {
                "name": "write_file",
                "args": {"Path": str(tmp_path / "src" / "broken.py"), "Content": "def oops(:\n    pass\n"},
            },
        },
    )
    assert r_syn["decision"] == "deny"
    assert "SyntaxError" in r_syn["reason"]

    # 6. Allow clean modular Python file
    r_ok = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(tmp_path)],
            "toolCall": {
                "name": "write_file",
                "args": {"Path": str(tmp_path / "src" / "clean.py"), "Content": "def add(a: int, b: int) -> int:\n    return a + b\n"},
            },
        },
    )
    assert r_ok["decision"] == "allow"


def test_hook_compaction_recovery_and_stop_lesson_lock(tmp_path: Path) -> None:
    init_workspace(tmp_path, project_name="HookLifecycle")
    conv = "conv-test-001"

    # SessionStart via actual plugin hook_entry.py subprocess
    hook_script = REPO_ROOT / "plugin" / "scripts" / "hook_entry.py"
    p_start = subprocess.run(
        [sys.executable, str(hook_script), "SessionStart"],
        input=json.dumps({"conversationId": conv, "workspacePaths": [str(tmp_path)]}),
        capture_output=True,
        text=True,
        check=True,
    )
    start_out = json.loads(p_start.stdout)
    assert "SUPERMEMORY CONSTITUTIONAL HARNESS ACTIVE" in start_out["injectSteps"][0]["systemMessage"]["systemMessage"]

    # High step count invocation -> followed by dropped step count (compaction!) + user scolding
    dispatch_hook(
        "PreInvocation",
        {"conversationId": conv, "workspacePaths": [str(tmp_path)], "invocationNum": 1, "initialNumSteps": 64, "lastUserInput": "status"},
    )
    pre_compact = dispatch_hook(
        "PreInvocation",
        {
            "conversationId": conv,
            "workspacePaths": [str(tmp_path)],
            "invocationNum": 2,
            "initialNumSteps": 8,
            "lastUserInput": "Sao cứ lặp lại lỗi không lưu vào memory thế hả?!",
        },
    )
    injected = pre_compact["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "COMPACTION RECOVERY DETECTED" in injected
    assert "SELF-LEARNING TRIGGERED" in injected

    # If agent tries to Stop without recording the lesson, Stop hook forces continuation!
    stop_1 = dispatch_hook(
        "Stop",
        {
            "conversationId": conv,
            "workspacePaths": [str(tmp_path)],
            "continuationActive": False,
            "terminationReason": "NO_TOOL_CALL",
        },
    )
    assert stop_1["decision"] == "continue"
    assert "SELF-LEARNING COMMIT REQUIRED" in stop_1["reason"]

    # Re-trigger lock, then clear it properly via PostToolUse (supermemory_record_lesson)
    dispatch_hook(
        "PreInvocation",
        {
            "conversationId": conv,
            "workspacePaths": [str(tmp_path)],
            "invocationNum": 3,
            "initialNumSteps": 12,
            "lastUserInput": "Tao đã bảo cấm code rác vượt trần dòng!",
        },
    )
    dispatch_hook(
        "PostToolUse",
        {
            "conversationId": conv,
            "workspacePaths": [str(tmp_path)],
            "toolCall": {"name": "mcp_supermemory_supermemory_record_lesson", "args": {}},
        },
    )
    stop_2 = dispatch_hook(
        "Stop",
        {
            "conversationId": conv,
            "workspacePaths": [str(tmp_path)],
            "continuationActive": False,
            "terminationReason": "NO_TOOL_CALL",
        },
    )
    assert stop_2["decision"] == "allow"
