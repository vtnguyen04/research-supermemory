# 🧠 SuperMemory Harness (`v2.5`)

**Zero-Amnesia 4-Tier Cognitive Graph, Zero-Overhead Constitutional Hooks, PreToolUse CodeGates, Scientific Experiment Registry, OpenSpec Lifecycle Manager, and Daylight Architectural Web Studio — Built as a Native Antigravity Plugin & Standalone Zero-Dependency Python CLI/SDK.**

---

## Why SuperMemory?

Standard coding agent harnesses suffer from **Context Compaction Amnesia**, **Agent-Switch Drift**, and **Repeated Mistake Loops**:
1. When `/compact` runs or a task moves between agents (Antigravity, Claude Code, Gemini CLI, Codex), critical architectural invariants, failed hypotheses, and user corrections vanish.
2. Text-only lessons in `.md` files bloat over time or get ignored under token pressure.
3. Unverified experiments mix multiple variables, accidentally touch evaluation scripts, or repeat previously rejected dead-ends.

**SuperMemory** solves all three permanently with **zero external runtime dependencies** (pure Python 3.10+ stdlib + SQLite WAL + FTS5 BM25):

- **Hybrid Dual-Persistence Memory:** Every entity (`LAW`, `LESSON`, `GATE`, `IDEA`, `ALGORITHM`, `PROPOSAL`, `EXPERIMENT`, `KNOWLEDGE_NODE`, `OBSERVATION`) lives in both ACID SQLite FTS5 (`.supermemory/supermemory.db`) AND Git-versioned JSON/Markdown (`memory/graph_snapshot.json`, `00_MEMORY_GRAPH.md`, `01_ACTIVE_STATE.md` `< 150`L, `02_CONSTITUTION_AND_LESSONS.md` `< 200`L, `03_EXPERIMENTS_REGISTRY.md`). Cloning any repo on a new machine auto-hydrates 100% of the graph from `graph_snapshot.json`.
- **4-Tier Cognitive Memory Hierarchy (`WORKING` · `PROCEDURAL` · `SEMANTIC` · `EPISODIC`):** Progressive disclosure (`< 850` token prompt capsule) keeps `L3 EPISODIC` logs paged out on disk and consolidates them into `L2 SEMANTIC` / `L1 PROCEDURAL` rules.
- **Federated `Local` + `Global` SuperMemory:** Every project folder maintains an isolated Local SuperMemory (`<folder>/.supermemory/` + `<folder>/memory/`), while `~/.supermemory/global` stores cross-project preferences, universal `LAW`s/`PROCEDURE`s, and `workspaces.json`.
- **Zero-Overhead Event-Driven Hooks (`hooks.json`):**
  - `SessionStart` & `PreInvocation`: Inject compact Federated `LOCAL + GLOBAL` capsule + anti-repeat dead-end warnings with zero latency overhead on casual Q&A turns.
  - `PreToolUse` (`< 20ms`): Hard-blocks (`"decision": "deny"`) `MAX_LINES >= 300`, throwaway filenames (`debug_*`, `tmp_*`, `*_v2.py`), `FROZEN_SHA256` evaluator edits, forbidden code regexes, broken Python AST syntax, and destructive shell commands.
  - `PostToolUse` & `Stop`: Automatically locks turn completion only when an explicit user correction/rule or unlogged benchmark run still needs to be persisted into a `LAW` + `CodeGate` or `EXPERIMENT`.
- **Native Stdio MCP Server (`mcp_config.json`):** Exposes 14 `supermemory_*` tools, 4 `supermemory://` resources, and boot prompts.
- **Daylight Architectural Web Studio (`supermemory ui`):** Zero-CDN interactive console with Local/Global Workspace Switcher, **3-Mode Knowledge Graph** (`Force Network` · `Concentric Rings` · `3-Lane Cards`), paginated Bento ledgers, Slide-Over Inspector Sheet, Interactive Merge Studio, and OpenSpec Stage Pipeline.

---

## Quick Install (From GitHub)

### Option A — 1-Command Direct Install via `uv` or `pipx` (No Clone Needed)

```bash
# Using uv (recommended):
uv tool install git+https://github.com/<your-username>/supermemory.git
supermemory install-plugin

# Or using pipx:
pipx install git+https://github.com/<your-username>/supermemory.git
supermemory install-plugin
```

### Option B — `git clone` + Universal `./install.sh` (Works With `uv`, `pipx`, or Plain `python3`)

```bash
git clone https://github.com/<your-username>/supermemory.git
cd supermemory
./install.sh
```

### Bootstrap Inside Any Project or Open Global Studio

```bash
# Initialize Local SuperMemory inside a project repository:
cd /path/to/your-project
supermemory init . --name "MyProject" --max-lines 300 --goal "Ship verified SOTA pipeline"

# Launch Web Studio for the current project:
supermemory ui --port 8765

# Or open Global SuperMemory Studio from anywhere on your machine:
supermemory ui --global
```

---

## CLI Quick Reference

| Command | Purpose |
| :--- | :--- |
| `supermemory init [dir]` | Initialize Knowledge Graph, Universal Laws (`LAW-01..08`), default `CodeGate`s, and `AGENTS.md` / `GEMINI.md` / `CLAUDE.md` |
| `supermemory status [-g]` | Print compact 4-Tier Constitutional + Active State capsule (Local or Global) |
| `supermemory workspaces` | List Global SuperMemory (`~/.supermemory/global`) and all registered Local project folders |
| `supermemory recall "<query>"` | Federated `LOCAL + GLOBAL` SQLite FTS5 BM25 + 2-hop graph retrieval + Anti-Repeat warnings |
| `supermemory learn ... [-g]` | Consolidate a mistake/user rule into a Local or Global `LAW` and bind an executable `CodeGate` |
| `supermemory consolidate ...` | Merge Episodic/Semantic nodes into a `SEMANTIC` or `PROCEDURAL` node (`--auto` for 1-click cluster merge) |
| `supermemory promote <ID>` | Promote a high-value Local node (`LESSON`, `LAW`, `ALGORITHM`, `PROCEDURE`) into Global SuperMemory |
| `supermemory gate list\|add\|freeze` | List active `PreToolUse` gates, add regex/command guards, or SHA-256 lock an evaluator |
| `supermemory idea ...` | Record an `IDEA` or `ALGORITHM` (including `REJECTED` dead-ends so they are never repeated) |
| `supermemory proposal create\|advance` | Manage OpenSpec lifecycle (`PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED`) |
| `supermemory exp ...` | Log a single-variable scientific experiment with monotonic baseline delta & post-mortem |
| `supermemory audit` | Audit the entire repository against all active Constitutional `CodeGate`s |
| `supermemory handoff` | Generate zero-loss `memory/HANDOFF_BRIEFING.md` before `/compact` or agent switch |
| `supermemory ui [-g] [--port 8765]` | Launch the Daylight Architectural Web Studio at `http://127.0.0.1:8765` (Local or Global) |
| `supermemory install-plugin` | Validate (`--strict`) and install/update the global Antigravity Plugin |

---

## Development & Verification

```bash
pytest -q
ruff check src tests plugin/scripts setup.py
mypy src tests
supermemory install-plugin --validate-only
supermemory audit
```
