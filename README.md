# 🧠 SuperMemory Harness

**Zero-Amnesia Knowledge Graph, Self-Learning Constitutional Harness, PreToolUse CodeGates, Scientific Experiment Registry, OpenSpec Lifecycle Manager, and Interactive Web Observatory — Built as a Native Antigravity Extension & Standalone Python CLI/SDK.**

---

## Why SuperMemory?

Standard coding agent harnesses suffer from **Context Compaction Amnesia**, **Agent-Switch Drift**, and **Repeated Mistake Loops**:
1. When `/compact` runs or a task moves between agents (Antigravity, Claude Code, Gemini CLI, Codex), critical architectural invariants, failed hypotheses, and user corrections vanish.
2. Text-only lessons in `.md` files bloat over time or get ignored under token pressure.
3. Unverified experiments mix multiple variables, accidentally touch evaluation scripts, or repeat previously rejected dead-ends.

**SuperMemory** solves all three permanently with **zero external runtime dependencies** (pure Python 3.10+ stdlib + SQLite WAL + FTS5 BM25):

- **Hybrid Dual-Persistence Memory:** Every entity (`LAW`, `LESSON`, `GATE`, `IDEA`, `ALGORITHM`, `PROPOSAL`, `EXPERIMENT`, `KNOWLEDGE_NODE`, `AGENT_RUN`) lives in both ACID SQLite FTS5 (`.supermemory/supermemory.db`) AND Git-versioned JSON/Markdown (`memory/graph_snapshot.json`, `00_MEMORY_GRAPH.md`, `01_ACTIVE_STATE.md` `< 150`L, `02_CONSTITUTION_AND_LESSONS.md` `< 200`L, `03_EXPERIMENTS_REGISTRY.md`). Deleting `.db` on a fresh `git clone` auto-hydrates 100% of the graph from `graph_snapshot.json`.
- **Self-Learning Toolkit Plugged into Antigravity Hooks (`hooks.json`):**
  - `SessionStart`: Injects Constitutional Capsule + Active State + Pending Proposals.
  - `PreInvocation`: Detects context compaction (`step_idx` drop), detects bilingual (Vietnamese + English) user scoldings/corrections & strategic directives, engages `pending_lesson_lock`, and surfaces Hybrid BM25 + 2-hop **Anti-Repeat Dead-End Warnings**.
  - `PreToolUse` (`< 20ms`): Hard-blocks (`"decision": "deny"`) `MAX_LINES >= 300`, throwaway filenames (`debug_*`, `tmp_*`, `*_v2.py`), `FROZEN_SHA256` evaluator edits, forbidden code regexes, broken Python AST syntax, and destructive shell commands.
  - `PostToolUse` & `Stop`: Prevents turn completion (`"decision": "continue"`) when a user correction has not yet been consolidated into a `LAW` + `CodeGate` via `supermemory learn` / `supermemory_record_lesson`.
- **Native Stdio MCP Server (`mcp_config.json`):** Exposes 12 `supermemory_*` tools, 4 `supermemory://` resources, and boot prompts directly inside Antigravity, Claude Code, or Cursor.
- **Interactive Knowledge Graph Web Observatory (`supermemory ui`):** Zero-CDN dark engineering dashboard with HTML5 Canvas Force-Directed Graph, BM25 + 2-hop search, 1-hop lineage inspector, Gate Shield telemetry, SVG Metric Progression curves, and OpenSpec Proposal Kanban.

---

## Quick Install

```bash
# 1. Install CLI globally (zero external dependencies)
uv tool install --editable /home/quynhthu/Documents/AI-project/supermemory

# 2. Validate (--strict) & install the global Antigravity Plugin
supermemory install-plugin

# 3. Bootstrap SuperMemory inside any project
cd /path/to/your-project
supermemory init . --name "MyProject" --max-lines 300 --goal "Ship verified SOTA pipeline"
```

---

## CLI Quick Reference

| Command | Purpose |
| :--- | :--- |
| `supermemory init [dir]` | Initialize Knowledge Graph, Universal Laws (`LAW-01..08`), default `CodeGate`s, and `AGENTS.md` / `GEMINI.md` / `CLAUDE.md` |
| `supermemory status` | Print compact Constitutional + Active State capsule & graph telemetry |
| `supermemory recall "<query>"` | Hybrid SQLite FTS5 BM25 + 2-hop graph retrieval + Anti-Repeat warnings |
| `supermemory learn ...` | Consolidate a mistake/user correction into a `LAW` and bind an executable `CodeGate` |
| `supermemory gate list\|add\|freeze` | List active `PreToolUse` gates, add regex/command guards, or SHA-256 lock an evaluator |
| `supermemory idea ...` | Record an `IDEA` or `ALGORITHM` (including `REJECTED` dead-ends so they are never repeated) |
| `supermemory proposal create\|advance` | Manage OpenSpec lifecycle (`PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED`) |
| `supermemory exp ...` | Log a single-variable scientific experiment with monotonic baseline delta & post-mortem |
| `supermemory audit` | Audit the entire repository against all active Constitutional `CodeGate`s |
| `supermemory handoff` | Generate zero-loss `memory/HANDOFF_BRIEFING.md` before `/compact` or agent switch |
| `supermemory import-zaloai` | Import Laws, Lessons, Frozen Evaluators, OpenSpec Proposals & Experiments from ZALOAI |
| `supermemory ui --port 8765` | Launch the interactive Knowledge Graph Web Observatory at `http://127.0.0.1:8765` |

---

## Development & Verification

```bash
pytest -q
ruff check src tests plugin/scripts
mypy src tests
supermemory install-plugin --validate-only
supermemory audit
```
