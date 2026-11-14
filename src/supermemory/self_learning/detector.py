"""Bilingual (Vietnamese & English) user correction, scolding, rule, and directive detector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

_HYPOTHETICAL_GUARD = re.compile(
    r"(?:ví dụ\s+như|giả sử\s+như|thì sao\s*\?|what if\b|suppose\b|for example if\b)",
    flags=re.IGNORECASE | re.UNICODE,
)

_CORRECTION_PATTERNS: List[Tuple[str, str, int]] = [
    (
        "NEW_USER_RULE",
        r"(?:thêm rule|thêm luật|quy tắc mới|luật mới|từ giờ trở đi|từ nay trở đi|từ giờ cấm|bắt buộc phải|cấm dùng|cấm xài|tuyệt đối cấm|tuyệt đối không được|luôn phải nhớ|nhớ kỹ rule|add a rule|add rule|new rule|from now on|never use\b|always enforce\b)",
        94,
    ),
    (
        "HARDCODING_LEAKAGE",
        r"\b(?:hardcode|hard-code|trá hình|leakage|rò rỉ|vá lỗi tập test|sửa trực tiếp trên tập test|overfit|generalize|tổng quát hóa)\b",
        95,
    ),
    (
        "CLEAN_CODE_BLOAT",
        r"\b(?:clean code|code rác|rác rưởi|hack não|phình to|file nháp|chạy 1 lần|over-engineer|quá dài|vượt trần dòng)\b",
        88,
    ),
    (
        "COST_CACHE_WASTE",
        r"\b(?:đốt tiền|hết sạch credit|tốn tiền|no_cache|chạy lại mấy câu đã đúng|api waste|prompt caching)\b",
        92,
    ),
    (
        "STALE_MEMORY",
        r"\b(?:không save|khong save|không lưu|quên ghi|quên mất|không làm theo agent\.md|stale memory|lặp lại lỗi|sai đi sai lại|tái phạm)\b",
        96,
    ),
    (
        "COMPUTE_PLACEMENT",
        r"\b(?:nóng máy|sập máy|chạy trên máy tao|đưa server cho mày chi|kill background|tự ý kill)\b",
        90,
    ),
    (
        "ARTIFACT_CONTAMINATION",
        r"\b(?:phí lượt nộp|mất lượt nộp|copy từ gold|ghi đè submission|làm hỏng file)\b",
        94,
    ),
    (
        "GENERAL_SCOLDING",
        r"(?:tại sao lại|tao đã bảo|tao đã nói|đã dặn|nhắc bao nhiêu lần|đã cấm|cấm tuyệt đối|sao cứ|mày ngu|ngu vậy|ngu thế|ngu vãi|óc chó|điên à|sai rồi|sai bét|làm sai|bậy rồi|tào lao|vớ vẩn|ảo giác|bịa đặt|phá code|hỏng hết|làm ăn kiểu gì|stop doing|never do that|why did you|you forgot to|i told you not to|you broke|wrong again|hallucinat|stupid)",
        86,
    ),
]

_DIRECTIVE_PATTERNS: List[Tuple[str, str]] = [
    ("STRATEGIC_TARGET", r"(?:mục tiêu|tao muốn\s*[><=]|target\s*[><=]|phải đạt\s*[><=]|không cần fine-?tune)"),
    ("ARCHITECTURE_SPEC", r"(?:kiến trúc|lộ trình|layer [a-z]|pillar \d|proposal|thiết kế hệ thống|vòng đời)"),
]

_CATEGORY_TO_DEFAULT_LAW: Dict[str, str] = {
    "NEW_USER_RULE": "LAW-08",
    "HARDCODING_LEAKAGE": "LAW-01",
    "CLEAN_CODE_BLOAT": "LAW-02",
    "COST_CACHE_WASTE": "LAW-04",
    "COMPUTE_PLACEMENT": "LAW-04",
    "ARTIFACT_CONTAMINATION": "LAW-05",
    "STALE_MEMORY": "LAW-07",
    "GENERAL_SCOLDING": "LAW-08",
}


@dataclass
class UserSignal:
    """Detected learning, new-rule, or strategic signal from user message."""

    requires_lesson: bool
    requires_state_sync: bool
    category: str
    suggested_law_id: str
    confidence: int
    excerpt: str
    guidance: str


class SelfLearningDetector:
    """Classifies user messages to trigger mandatory self-learning & rule-commit hooks."""

    @classmethod
    def analyze(cls, user_input: str) -> UserSignal:
        text = (user_input or "").strip()
        if len(text) < 6:
            return UserSignal(False, False, "NONE", "", 0, "", "")

        excerpt = text[:280].replace("\n", " ").strip()
        if _HYPOTHETICAL_GUARD.search(text):
            return UserSignal(False, False, "HYPOTHETICAL", "", 0, excerpt, "")

        best_cat = "NONE"
        best_conf = 0
        for cat, pat, weight in _CORRECTION_PATTERNS:
            if re.search(pat, text, flags=re.IGNORECASE | re.UNICODE):
                if weight > best_conf:
                    best_cat = cat
                    best_conf = weight

        if best_conf >= 80:
            law_id = _CATEGORY_TO_DEFAULT_LAW.get(best_cat, "LAW-08")
            if best_cat == "NEW_USER_RULE":
                guidance = (
                    "🛡️ NEW USER RULE DETECTED (MANDATORY COMMIT LOCK ACTIVE): "
                    "The user defined a new rule/constraint. Before ending this turn, you MUST persist it via "
                    "`supermemory learn` / `supermemory gate add` (or MCP `supermemory_record_lesson` / "
                    "`supermemory_add_gate`) so `02_CONSTITUTION_AND_LESSONS.md`, `AGENTS.md`, and `PreToolUse` "
                    "CodeGates enforce it permanently. The Stop hook WILL block turn completion until saved."
                )
            else:
                guidance = (
                    f"🛡️ SELF-LEARNING TRIGGERED ({best_cat} -> {law_id}): "
                    f"User issued a behavioral/technical correction. Before ending this turn, you MUST: "
                    f"(1) record the root-cause lesson via `supermemory learn` or MCP `supermemory_record_lesson`, "
                    f"(2) attach/update an executable CodeGate (`forbid_regex` / `forbid_cmd_regex` / `freeze_path`) "
                    f"if mechanically checkable, and (3) sync memory. The Stop hook WILL block stopping until committed."
                )
            return UserSignal(
                requires_lesson=True,
                requires_state_sync=True,
                category=best_cat,
                suggested_law_id=law_id,
                confidence=best_conf,
                excerpt=excerpt,
                guidance=guidance,
            )

        for d_cat, d_pat in _DIRECTIVE_PATTERNS:
            if re.search(d_pat, text, flags=re.IGNORECASE | re.UNICODE) and len(text) >= 40:
                guidance = (
                    f"🧭 STRATEGIC DIRECTIVE DETECTED ({d_cat}): "
                    f"Persist full user targets/architecture into SuperMemory (`supermemory_update_state` / "
                    f"`supermemory_manage_proposal`) in THIS turn so context compaction never loses any layer."
                )
                return UserSignal(
                    requires_lesson=False,
                    requires_state_sync=True,
                    category=d_cat,
                    suggested_law_id="LAW-07",
                    confidence=75,
                    excerpt=excerpt,
                    guidance=guidance,
                )

        return UserSignal(False, False, "NONE", "", 0, excerpt, "")
