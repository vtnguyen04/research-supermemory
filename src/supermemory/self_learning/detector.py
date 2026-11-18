"""High-precision explicit user rule & critique detector (zero chat/question false-positives)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

_HYPOTHETICAL_GUARD = re.compile(
    r"(?:ví dụ\s+như|giả sử\s+như|thì sao\s*\?|what if\b|suppose\b|for example if\b)",
    flags=re.IGNORECASE | re.UNICODE,
)
_TURN_CLARIFICATION_GUARD = re.compile(
    r"(?:cho mày edit đâu|bảo mày edit đâu|chưa cho edit|chưa bảo sửa|khoan hãy sửa|khoan edit|chỉ hỏi thôi|đừng sửa vội|did i ask you to edit|don't edit yet)",
    flags=re.IGNORECASE | re.UNICODE,
)
_EXPLICIT_RULE_CMD_RE = re.compile(
    r"(?:thêm rule|thêm luật|lưu vào lesson|lưu và lesson|ghi vào lesson|quy tắc mới|luật mới|từ giờ trở đi|từ nay trở đi|từ giờ cấm|nhớ kỹ rule|add a rule|add rule|new rule|save to lesson|from now on\b.*?\bnever\b)",
    flags=re.IGNORECASE | re.UNICODE,
)
_DIAGNOSTIC_QUESTION_GUARD = re.compile(
    r"(?:(?:\bcó\b.{1,45}\b(?:không|khong|ko|chưa)\b)|(?:\bphải\s+không\b|\bđúng\s+không\b|\bis\s+there\s+any\b|\bdoes\s+it\b|\bdid\s+it\b))",
    flags=re.IGNORECASE | re.UNICODE,
)
_DIRECT_ACCUSATION_RE = re.compile(
    r"(?:\bmày\s+(?:lại|chạy|làm|sửa|code|viết|quên|cứ)\b|\byou\s+(?:hardcoded|leaked|broke|forgot)\b)",
    flags=re.IGNORECASE | re.UNICODE,
)
_EXPLAIN_ONLY_GUARD = re.compile(
    r"(?:^(?:tại sao|vì sao|sao lại|giải thích|cho hỏi|explain|why does|how does|what is|can i)\b|\b(?:sài được không|dùng được không|là gì\s*\?))",
    flags=re.IGNORECASE | re.UNICODE,
)

_CORRECTION_PATTERNS: List[Tuple[str, str, int, bool]] = [
    ("NEW_USER_RULE", _EXPLICIT_RULE_CMD_RE.pattern, 96, False),
    ("HARDCODING_LEAKAGE", r"\b(?:trá hình|vá lỗi tập test|sửa trực tiếp trên tập test)\b", 95, False),
    ("HARDCODING_LEAKAGE", r"\b(?:hardcode|hard-code|leakage|rò rỉ|overfit)\b", 92, True),
    ("CLEAN_CODE_BLOAT", r"\b(?:code rác|rác rưởi|file nháp|vượt trần dòng)\b", 88, False),
    ("CLEAN_CODE_BLOAT", r"\b(?:over-engineer)\b", 86, True),
    ("COST_CACHE_WASTE", r"\b(?:đốt tiền|hết sạch credit|chạy lại mấy câu đã đúng|api waste)\b", 92, False),
    ("COST_CACHE_WASTE", r"\b(?:no_cache)\b", 88, True),
    ("STALE_MEMORY", r"\b(?:không save vào memory|quên ghi vào memory|forgot to save|không làm theo agent\.md|lặp lại lỗi|sai đi sai lại|tái phạm)\b", 96, False),
    ("COMPUTE_PLACEMENT", r"\b(?:nóng máy|sập máy|chạy trên máy tao|đưa server cho mày chi|tự ý kill)\b", 90, False),
    ("ARTIFACT_CONTAMINATION", r"\b(?:phí lượt nộp|mất lượt nộp|copy từ gold|ghi đè submission)\b", 94, False),
    ("GENERAL_SCOLDING", r"(?:tao đã bảo cấm|tao đã dặn|nhắc bao nhiêu lần|sai bét|ảo giác|bịa đặt|phá code|làm ăn kiểu gì|i told you not to|wrong again)", 88, False),
    ("GENERAL_SCOLDING", r"\bhallucinat", 84, True),
]

_DIRECTIVE_PATTERNS: List[Tuple[str, str]] = [
    ("STRATEGIC_TARGET", r"(?:tao muốn\s*[><=]|target\s*[><=]|phải đạt\s*[><=])"),
    ("ARCHITECTURE_SPEC", r"(?:thiết kế hệ thống theo kiến trúc|vòng đời proposal rõ ràng)"),
]

_RESEARCH_INTENT_RE = re.compile(
    r"(?:\b(?:literature\s+review|paper\s+search|arxiv|semantic\s*scholar|openalex|sota\s+papers?|scout\s+sota)\b"
    r"|(?:tìm\s+paper|săn\s+paper|bài\s+báo\s+(?:sota|mới|khoa\s+học)|tìm\s+tài\s+liệu\s+khoa\s+học))",
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
    """Detected explicit rule or research routing signal from user message."""

    requires_lesson: bool
    requires_state_sync: bool
    category: str
    suggested_law_id: str
    confidence: int
    excerpt: str
    guidance: str


class SelfLearningDetector:
    """Detects explicit durable user rules & research campaigns without question false-positives."""

    @classmethod
    def analyze(cls, user_input: str) -> UserSignal:
        text = (user_input or "").strip()
        if len(text) < 10:
            return UserSignal(False, False, "NONE", "", 0, "", "")

        excerpt = text[:280].replace("\n", " ").strip()
        if _HYPOTHETICAL_GUARD.search(text) or _TURN_CLARIFICATION_GUARD.search(text):
            return UserSignal(False, False, "NONE", "", 0, excerpt, "")

        has_explicit_rule_cmd = bool(_EXPLICIT_RULE_CMD_RE.search(text))
        has_accusation = bool(_DIRECT_ACCUSATION_RE.search(text))
        is_diagnostic_question = bool(_DIAGNOSTIC_QUESTION_GUARD.search(text)) and not has_explicit_rule_cmd and not has_accusation

        if not is_diagnostic_question:
            best_cat, best_conf = "NONE", 0
            for cat, pat, weight, needs_intent in _CORRECTION_PATTERNS:
                if needs_intent and not (has_explicit_rule_cmd or has_accusation):
                    continue
                if re.search(pat, text, flags=re.IGNORECASE | re.UNICODE) and weight > best_conf:
                    best_cat, best_conf = cat, weight

            if best_conf >= 80:
                law_id = _CATEGORY_TO_DEFAULT_LAW.get(best_cat, "LAW-08")
                guidance = (
                    f"🛡️ SELF-LEARNING TRIGGERED ({best_cat} -> {law_id}): "
                    "Explicit user rule or technical correction detected. Before ending this turn, record the "
                    "root-cause lesson via MCP `record_lesson` (`supermemory learn`) and bind a `CodeGate` if checkable."
                )
                return UserSignal(True, True, best_cat, law_id, best_conf, excerpt, guidance)

        for d_cat, d_pat in _DIRECTIVE_PATTERNS:
            if re.search(d_pat, text, flags=re.IGNORECASE | re.UNICODE) and len(text) >= 40:
                guidance = (
                    f"🧭 STRATEGIC DIRECTIVE DETECTED ({d_cat}): "
                    "Persist updated project targets/architecture via MCP `update_state` if scope changed."
                )
                return UserSignal(False, True, d_cat, "LAW-07", 75, excerpt, guidance)

        if len(text) >= 18 and not _EXPLAIN_ONLY_GUARD.search(text) and not is_diagnostic_question and _RESEARCH_INTENT_RE.search(text):
            guidance = (
                "🔬 SUPERMEMORY RESEARCH AUTO-ROUTING ACTIVE (ZERO-AMNESIA VAULT PROTOCOL):\n"
                "1. Recall First: Query MCP `recall` (`include_siblings=True`) so prior wins & dead-ends are never repeated.\n"
                "2. Persist Every Finding to Its Canonical Vault Before Ending Turn:\n"
                "   • Error Slices & Falsifiable RQs -> `diagnose_bottleneck` (`08_BOTTLENECKS/BNK-XXX.md`)\n"
                "   • Papers & SOTA Mechanisms -> `scout_sota` (`07_METHOD_VAULT/METH-XXX.md`, `save_top_k>=1` or `register_card`)\n"
                "   • Candidate Ideas / Specs -> `propose_idea` or `manage_proposal` (with concrete `why`, `what_changes`, and `tasks`)"
            )
            return UserSignal(False, True, "RESEARCH_CAMPAIGN", "LAW-06", 84, excerpt, guidance)

        return UserSignal(False, False, "NONE", "", 0, excerpt, "")
