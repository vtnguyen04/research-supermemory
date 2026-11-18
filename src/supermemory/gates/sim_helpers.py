"""File-Edit Simulation, Quote-Aware Shell Splitting & Shell Frozen-File Guards."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from supermemory.models import CodeGate, GateType

_HASH_COMMENT_EXTS = (".py", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml", ".rb", ".r")
_SLASH_COMMENT_EXTS = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".scss", ".c", ".cpp", ".h", ".go", ".rs", ".java")
_BENIGN_REDIR_RE = re.compile(r"(?:\b\d*>&\d+\b|(?:1|2|&)?>>?\s*/dev/null\b)")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_SHELL_MUTATE_VERBS = {"tee", "cp", "mv", "rm", "dd", "truncate", "patch"}
_INLINE_WRITE_RE = re.compile(
    r"(?:\bsed\s+-[a-zA-Z]*i|\bperl\s+-[a-zA-Z]*i|\.write_text\(|\.write_bytes\(|\.unlink\(|\bos\.(?:remove|replace|unlink)\(|\bshutil\.|open\([^)]*['\"][wa+])"
)


def validate_regex_pattern(pattern: str, label: str = "pattern") -> str:
    """Compile-validate a regex pattern before persisting it into SQLite CodeGates."""
    clean = (pattern or "").strip()
    if not clean:
        raise ValueError(f"CodeGate `{label}` cannot be empty.")
    try:
        re.compile(clean)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression in `{label}` (`{clean[:80]}`): {exc}") from exc
    return clean


def extract_tool_file_path(tool_args: Dict[str, Any]) -> str:
    """Extract target file path across Antigravity and Claude Code file-mutation tools."""
    return str(
        tool_args.get("Path")
        or tool_args.get("AbsolutePath")
        or tool_args.get("TargetFile")
        or tool_args.get("file_path")
        or tool_args.get("notebook_path")
        or tool_args.get("path")
        or ""
    ).strip()


def split_shell_commands(raw: str) -> List[Tuple[List[str], bool]]:
    """Quote-aware shell segment splitter returning `(argv, has_file_redirect)` per command."""
    if not raw or not raw.strip():
        return []
    cleaned = _BENIGN_REDIR_RE.sub(" ", raw.replace("\n", " ; "))
    try:
        lex = shlex.shlex(cleaned, posix=True, punctuation_chars=";&|><")
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = list(lex)
    except ValueError:
        tokens = cleaned.split()

    out: List[Tuple[List[str], bool]] = []
    cur: List[str] = []
    has_redir = False

    def _flush() -> None:
        nonlocal cur, has_redir
        while cur and _ENV_ASSIGN_RE.match(cur[0]):
            cur = cur[1:]
        if len(cur) >= 2 and Path(cur[0]).name.lower() == "uv" and cur[1] == "run":
            cur = cur[2:]
        if len(cur) >= 2 and Path(cur[0]).name.lower() == "rtk":
            cur = cur[1:]
        if cur or has_redir:
            out.append((cur, has_redir))
        cur = []
        has_redir = False

    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            cur.append(tok)
            continue
        if set(tok) <= set(";&|") and tok:
            _flush()
            continue
        if any(r in tok for r in (">", ">>", "<<")) and set(tok) <= set("012><"):
            has_redir = ">" in tok
            skip_next = True
            continue
        cur.append(tok)
    _flush()
    return out


def _is_comment_line(rel: str, stripped_line: str) -> bool:
    low = rel.lower()
    if low.endswith(".md"):
        return False
    if low.endswith(_HASH_COMMENT_EXTS) and stripped_line.startswith("#"):
        return True
    if low.endswith(_SLASH_COMMENT_EXTS) and (stripped_line.startswith("//") or stripped_line.startswith("/*") or stripped_line.startswith("*")):
        return True
    return stripped_line.startswith("#") and "." not in Path(low).name


def simulate_file_text(tool_low: str, abs_p: Path, args: Dict[str, Any]) -> str:
    """Simulate candidate file contents for write/edit/replace/multiedit/notebookedit tools."""
    existing = ""
    if abs_p.is_file():
        try:
            existing = abs_p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            existing = ""

    if tool_low in ("write_file", "write"):
        content = str(args.get("Content") if args.get("Content") is not None else (args.get("content") or ""))
        return (existing + content) if args.get("Append") else content
    if tool_low == "notebookedit":
        return existing + "\n" + str(args.get("new_source") or "")
    if tool_low in ("edit_file", "edit", "replace_file_content"):
        target = str(
            args.get("Target")
            if args.get("Target") is not None
            else (args.get("TargetContent") if args.get("TargetContent") is not None else (args.get("old_string") or ""))
        )
        repl = str(
            args.get("Replacement")
            if args.get("Replacement") is not None
            else (args.get("ReplacementContent") if args.get("ReplacementContent") is not None else (args.get("new_string") or ""))
        )
        if not target or target not in existing:
            return existing
        allow_multi = bool(args.get("AllowMultiple", False)) if tool_low == "replace_file_content" else (bool(args.get("replace_all", False)) if tool_low == "edit" else True)
        return existing.replace(target, repl) if allow_multi else existing.replace(target, repl, 1)

    if tool_low in ("multiedit", "multi_replace_file_content"):
        cur = existing
        chunks = args.get("ReplacementChunks") or args.get("edits") or []
        if isinstance(chunks, list):
            for ch in chunks:
                if not isinstance(ch, dict):
                    continue
                t = str(ch.get("TargetContent") if ch.get("TargetContent") is not None else (ch.get("old_string") or ""))
                r = str(ch.get("ReplacementContent") if ch.get("ReplacementContent") is not None else (ch.get("new_string") or ""))
                if t and t in cur:
                    allow_m = bool(ch.get("AllowMultiple", False)) if "TargetContent" in ch else bool(ch.get("replace_all", False))
                    cur = cur.replace(t, r) if allow_m else cur.replace(t, r, 1)
        return cur
    return existing


def match_forbidden_regex(
    rel: str,
    text: str,
    pattern: str,
    ignore_comments: bool = True,
    force_multiline: bool = False,
) -> Optional[Tuple[int, str]]:
    """Evaluate single-line and multiline FORBIDDEN_REGEX safely without crashing on bad patterns."""
    try:
        rx = re.compile(pattern, re.MULTILINE)
    except re.error:
        return None

    kept_lines: List[str] = []
    for idx, ln in enumerate(text.splitlines(), 1):
        stripped = ln.lstrip()
        if ignore_comments and _is_comment_line(rel, stripped):
            kept_lines.append("")
            continue
        kept_lines.append(ln)
        if rx.search(ln):
            return idx, ln.strip()[:90]

    if force_multiline or any(tok in pattern for tok in ("\\n", "[\\s\\S]", "[^}]", "\\s*")):
        joined = "\n".join(kept_lines)
        m = rx.search(joined)
        if m:
            return joined[: m.start()].count("\n") + 1, " ".join(m.group(0).split())[:90]
    return None


def check_shell_frozen_write_bypass(cmd: str, gates: List[CodeGate]) -> List[Tuple[str, str]]:
    """Block shell commands attempting to overwrite, redirect into, or delete FROZEN_SHA256 files."""
    if not cmd:
        return []
    mut_segs: List[str] = []
    for argv, has_redir in split_shell_commands(cmd):
        joined = " ".join(argv)
        prog = Path(argv[0]).name.lower() if argv else ""
        is_git_reset = prog == "git" and len(argv) >= 2 and argv[1] in ("checkout", "restore", "rm")
        if has_redir or prog in _SHELL_MUTATE_VERBS or is_git_reset or _INLINE_WRITE_RE.search(joined):
            mut_segs.append(joined)
    if not mut_segs:
        return []

    hits: List[Tuple[str, str]] = []
    for g in gates:
        if g.gate_type != GateType.FROZEN_SHA256.value:
            continue
        rel = str(g.config.get("file") or g.target_glob or "").strip().replace("\\", "/")
        if not rel:
            continue
        bname = Path(rel).name
        for seg in mut_segs:
            if rel in seg or (len(bname) >= 4 and re.search(rf"(?<![\w.-]){re.escape(bname)}(?![\w.-])", seg)):
                hits.append((g.id, f"[{g.id}/{g.law_id or 'LAW-05'}] FROZEN FILE SHELL GUARD: command mutates SHA-256 locked `{rel}`"))
                break
    return hits
