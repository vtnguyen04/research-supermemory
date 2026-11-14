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
- **4-Tier Cognitive Memory Hierarchy (`WORKING` · `PROCEDURAL` · `SEMANTIC` · `EPISODIC`):** Inspired by CoALA/ACT-R progressive disclosure so the Agent never suffers context overload (`< 850` token prompt capsule; raw `L3 EPISODIC` logs remain paged out on disk and consolidate into `L2 SEMANTIC` / `L1 PROCEDURAL` nodes).
- **Federated `Local` + `Global` SuperMemory:** Every project folder maintains an isolated Local SuperMemory (`<folder>/.supermemory/` + `<folder>/memory/`), while `~/.supermemory/global` stores cross-project preferences, universal `LAW`s/`PROCEDURE`s, and `workspaces.json`. Uninitialized legacy folders operate seamlessly against Global SuperMemory without polluting the repo until `supermemory init .` is run.
- **Agent-Native Semantic Self-Triage & Structural Turn-Attestation (`hooks.json`):**
  - `SessionStart` & `PreInvocation`: Inject Federated `LOCAL + GLOBAL` recall + Semantic Memory Triage protocol without relying on fragile hardcoded regex lists.
  - `PreToolUse` (`< 20ms`): Hard-blocks (`"decision": "deny"`) `MAX_LINES >= 300`, throwaway filenames (`debug_*`, `tmp_*`, `*_v2.py`), `FROZEN_SHA256` evaluator edits, forbidden code regexes, broken Python AST syntax, and destructive shell commands.
  - `PostToolUse` & `Stop`: Structural **Turn-Attestation Gate (`turn_memory_handled` / `supermemory_checkpoint`)** blocks turn exit whenever a subtle or explicit user critique, new rule, dirty edit, or failed experiment insight has not yet been persisted (and live-compiles updated `LAW`s straight into `AGENTS.md` / `GEMINI.md` / `CLAUDE.md`).
- **Native Stdio MCP Server (`mcp_config.json`):** Exposes 14 `supermemory_*` tools (including `scope="local"|"global"`, `supermemory_consolidate`, and `supermemory_checkpoint`), 4 `supermemory://` resources, and boot prompts.
- **Interactive Knowledge Graph & Merge Studio (`supermemory ui`):** Zero-CDN dark engineering dashboard with Workspace/Global Scope Switcher, HTML5 Force-Directed Graph, 4-Tier Token Budget gauge, **Interactive Memory Merge Studio** (checkbox multi-select + 1-click Episodic Auto-Consolidation), **"Promote to Global"** drawer action, Gate Shield telemetry, and OpenSpec Kanban.

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
| `supermemory status [-g]` | Print compact 4-Tier Constitutional + Active State capsule (Local or Global) |
| `supermemory workspaces` | List Global SuperMemory (`~/.supermemory/global`) and all registered Local project folders |
| `supermemory recall "<query>"` | Federated `LOCAL + GLOBAL` SQLite FTS5 BM25 + 2-hop graph retrieval + Anti-Repeat warnings |
| `supermemory learn ... [-g]` | Consolidate a mistake/user rule into a Local or Global `LAW` and bind an executable `CodeGate` |
| `supermemory consolidate ...` | Merge Episodic/Semantic nodes into a `SEMANTIC` or `PROCEDURAL` node (`--auto` for 1-click cluster merge) |
| `supermemory promote <ID>` | Promote a high-value Local node (`LESSON`, `LAW`, `ALGORITHM`, `PROCEDURE`) into Global SuperMemory |
| `supermemory checkpoint` | Attest turn semantic memory review (`CLEAN`) for read-only Q&A turns |
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
