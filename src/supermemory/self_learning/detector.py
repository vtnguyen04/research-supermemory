"""Bilingual (Vietnamese & English) user correction, scolding, rule, and directive detector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

_HYPOTHETICAL_GUARD = re.compile(
    r"(?:ví dụ\s+như|giả sử\s+như|thì sao\s*\?|what if\b|suppose\b|for example if\b)",
    flags=re.IGNORECASE | re.UNICODE,
)

# Turn-local conversational clarifications ("who said you could edit yet?", "wait don't run yet")
# must NEVER be misclassified as permanent repo Laws or Lessons!
_TURN_CLARIFICATION_GUARD = re.compile(
    r"(?:cho mày edit đâu|bảo mày edit đâu|chưa cho edit|chưa bảo sửa|khoan hãy sửa|khoan edit|chỉ hỏi thôi|đừng sửa vội|did i ask you to edit|don't edit yet)",
    flags=re.IGNORECASE | re.UNICODE,
)

_CORRECTION_PATTERNS: List[Tuple[str, str, int]] = [
    (
        "NEW_USER_RULE",
        r"(?:thêm rule|thêm luật|lưu vào lesson|lưu và lesson|ghi vào lesson|quy tắc mới|luật mới|từ giờ trở đi|từ nay trở đi|từ giờ cấm|cấm dùng|cấm xài|tuyệt đối cấm|tuyệt đối không được|nhớ kỹ rule|add a rule|add rule|new rule|save to lesson|from now on\b.*?\bnever\b)",
        94,
    ),
    (
        "HARDCODING_LEAKAGE",
        r"\b(?:hardcode|hard-code|trá hình|leakage|rò rỉ|vá lỗi tập test|sửa trực tiếp trên tập test|overfit)\b",
        95,
    ),
    (
        "CLEAN_CODE_BLOAT",
        r"\b(?:code rác|rác rưởi|file nháp|chạy 1 lần|over-engineer|vượt trần dòng)\b",
        88,
    ),
    (
        "COST_CACHE_WASTE",
        r"\b(?:đốt tiền|hết sạch credit|no_cache|chạy lại mấy câu đã đúng|api waste|prompt caching)\b",
        92,
    ),
    (
        "STALE_MEMORY",
        r"\b(?:không save vào memory|quên ghi vào memory|forgot to save|không làm theo agent\.md|stale memory|lặp lại lỗi|sai đi sai lại|tái phạm)\b",
        96,
    ),
    (
        "COMPUTE_PLACEMENT",
        r"\b(?:nóng máy|sập máy|chạy trên máy tao|đưa server cho mày chi|tự ý kill)\b",
        90,
    ),
    (
        "ARTIFACT_CONTAMINATION",
        r"\b(?:phí lượt nộp|mất lượt nộp|copy từ gold|ghi đè submission)\b",
        94,
    ),
    (
        "GENERAL_SCOLDING",
        r"(?:tại sao mày lại|sao mày cứ|tao đã bảo cấm|tao đã dặn|nhắc bao nhiêu lần|mày ngu|ngu vậy|ngu thế|óc chó|sai bét|ảo giác|bịa đặt|phá code|làm ăn kiểu gì|i told you not to|wrong again|hallucinat)",
        86,
    ),
]

_DIRECTIVE_PATTERNS: List[Tuple[str, str]] = [
    ("STRATEGIC_TARGET", r"(?:tao muốn\s*[><=]|target\s*[><=]|phải đạt\s*[><=])"),
    ("ARCHITECTURE_SPEC", r"(?:thiết kế hệ thống theo kiến trúc|vòng đời proposal rõ ràng)"),
]

_EXPLAIN_ONLY_GUARD = re.compile(
    r"^(?:tại sao lại dùng|vì sao lại dùng|giải thích giúp|explain how|why does this use)\b",
    flags=re.IGNORECASE | re.UNICODE,
)

_RESEARCH_INTENT_RE = re.compile(
    r"(?:\b(?:research|literature\s+review|paper\s+search|arxiv|semantic\s*scholar|openalex|sota\s+(?:method|paper|approach|idea)s?|scout\s+sota|diagnose\s+bottleneck|find\s+bottleneck|error\s+slice)\b"
    r"|(?:nghiên\s+cứu|tìm\s+paper|săn\s+paper|bài\s+báo\s+(?:sota|mới|khoa\s+học)|điểm\s+nghẽn|chẩn\s+đoán\s+lỗi|tìm\s+bottleneck|đề\s+xuất\s+(?:phương\s+pháp|hướng|ý\s+tưởng|thuật\s+toán)|tìm\s+hướng\s+cải\s+tiến))",
    flags=re.IGNORECASE | re.UNICODE,
)

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
    """High-precision detector for explicit rules & real technical post-mortems (zero chat false-positives)."""

    @classmethod
    def analyze(cls, user_input: str) -> UserSignal:
        text = (user_input or "").strip()
        if len(text) < 10:
            return UserSignal(False, False, "NONE", "", 0, "", "")

        excerpt = text[:280].replace("\n", " ").strip()
        if _HYPOTHETICAL_GUARD.search(text) or _TURN_CLARIFICATION_GUARD.search(text):
            return UserSignal(False, False, "NONE", "", 0, excerpt, "")

        best_cat = "NONE"
        best_conf = 0
        for cat, pat, weight in _CORRECTION_PATTERNS:
            if re.search(pat, text, flags=re.IGNORECASE | re.UNICODE):
                if weight > best_conf:
                    best_cat = cat
                    best_conf = weight

        if best_conf >= 80:
            law_id = _CATEGORY_TO_DEFAULT_LAW.get(best_cat, "LAW-08")
            guidance = (
                f"🛡️ SELF-LEARNING TRIGGERED ({best_cat} -> {law_id}): "
                f"Explicit user rule or technical correction detected. Before ending this turn, record the "
                f"root-cause lesson via `supermemory learn` or MCP `record_lesson` (and bind a "
                f"`CodeGate` if mechanically checkable)."
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
                    f"Persist updated project targets/architecture via MCP `update_state` if scope changed."
                )
                return UserSignal(False, True, d_cat, "LAW-07", 75, excerpt, guidance)

        if len(text) >= 18 and not _EXPLAIN_ONLY_GUARD.search(text) and _RESEARCH_INTENT_RE.search(text):
            guidance = (
                "🔬 SUPERMEMORY RESEARCH AUTO-ROUTING ACTIVE (ZERO-AMNESIA VAULT PROTOCOL):\n"
                "1. Recall First: Query MCP `recall` (`include_siblings=True`) so prior wins & dead-ends are never repeated.\n"
                "2. Persist Every Finding to Its Canonical Vault Before Ending Turn:\n"
                "   • Error Slices & Falsifiable RQs -> `diagnose_bottleneck` (`memory/08_BOTTLENECKS/BNK-XXX.md` + `RQ-XXX`)\n"
                "   • Papers & SOTA Mechanisms -> `scout_sota` (`memory/07_METHOD_VAULT/METH-XXX.md`, `save_top_k>=1` or `action='register_card'`)\n"
                "   • Candidate Ideas / Dead-Ends / Specs -> `propose_idea` or `manage_proposal` (`memory/05_IDEAS_AND_ALGORITHMS/` & `memory/04_PROPOSALS/`)"
            )
            return UserSignal(False, True, "RESEARCH_CAMPAIGN", "LAW-06", 84, excerpt, guidance)

        return UserSignal(False, False, "NONE", "", 0, excerpt, "")
