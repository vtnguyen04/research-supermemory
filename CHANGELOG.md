# Changelog

All notable changes to **SuperMemory** (`research-supermemory`) are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Enforced at `PreToolUse` and `supermemory audit` by **`GATE-030` (`CHANGELOG_SYNC`)**.

---

## [3.6.0] - 2026-11-17

### Added
- **Zero-Orphan Contextual Auto-Linker & Near-Duplicate Insight Supersession (`graph/auto_linker.py`, `checkpoint_sync.py`, `lifecycle/manager.py`):** Automatically wires `DERIVED_FROM` / `CANDIDATE_FOR` / `REFERENCES` edges from explicit graph ID mentions or active `PROPOSAL`/`BOTTLENECK`/`LAW` anchors whenever `OBS`, `ALGO`, `IDEA`, or `PROP` nodes are minted (`0` degree-0 perimeter orphans, without fabricating `EXPERIMENT` utility links), and automatically supersedes near-duplicate positive `OBSERVATION` notes (`>= 0.66` hybrid similarity).
- **L2 Observation Cluster Compaction & Retroactive Orphan Repair (`outcome_ledger.py`, `tiers.py`):** Extended `consolidate_nodes` and `auto_consolidate_episodic` to backfill edges on legacy degree-0 orphans (`repair_orphan_nodes`) and compact overflow L2 `OBSERVATION` clusters (`> 24` active insights) into topic-grouped `SEM-XXX` syntheses while preserving `FAILURE_INSIGHT` warnings and newest working observations.
- **Structural Metric-Direction Inference (`outcome_ledger.py`, `tiers.py`, `ui/api_research.py`):** Added `infer_metric_direction` (`lower_is_better` vs `higher_is_better` inferred from typed `KEEP`/`REVERT` `delta_vs_baseline` signs with `0` regexes) so `build_tiered_capsule` (`🏆 Best SOTA`) and Web Studio `Experiment Ledger` (`Sort: Best Score` / `Sort: Best Delta`) rank minimization benchmarks (`Regret`, `RMSE`, `MAE`, `LogLoss`) accurately via `min()`.

### Fixed
- **Active Core Graph Decluttering & Web Studio Filters (`graph_canvas.js`, `views.js`, `merge_studio.js`, `index.html`):** Upgraded `Active Core` (`chk-hide-aux`) to hide `AGENT_RUN`, `CONSOLIDATED`, and `SUPERSEDED` historical nodes by default on dense 450+ node graphs (auto-expanding on `focusNode`), included `FAILURE_INSIGHT` in `Proposals & Ideas -> Dead-Ends`, surfaced `SUPERSEDED -> <ID>` badges, and honored `metadata.consolidated` in Merge Studio.
- **Information-Gap Sprint Planning, High-Precision Hook Auto-Recall & Handoff Slicing (`orchestrator.py`, `runner.py`, `agent_adapters.py`):** Updated `plan_research_sprint` Wave-1 to audit untried vault mechanisms instead of forcing external `sota-scout` when `count_untried_candidates > 0`, required content-word/ID overlap (`score >= 0.30`) in `PreInvocation` auto-recall to eliminate 3-gram false hits, fixed `HANDOFF_BRIEFING.md` newest-first slicing (`exps[:6]`, `lessons[:8]` from `limit=200`, lazy `build_tiered_capsule`), and skipped duplicate workspace `.agents/hooks.json` generation when the global Antigravity plugin is installed.

---

## [3.5.2] - 2026-11-17

### Fixed
- **Direction-Agnostic Minimization Deltas (`experiments.py`, `stagnation_guard.py`, `GATE-035`):** Fixed signed `delta < 0` / `delta <= 1e-5` checks so minimization breakthroughs (`Regret`, `RMSE`, `MAE`, `LogLoss` dropping with `verdict="KEEP"`/`"VICTORY_CONFIRMED"`) record `IMPROVES_OVER` (`regression_detected=False`) and never trigger false plateau locks (`|delta| <= 1e-5` only).
- **Information-Gap Gated Research (`stagnation_guard.py`, `bottleneck_engine.py`, `detector.py`):** Allowed `manage_proposal` to proceed freely whenever untried `IDEA`/`ALGORITHM`/`METHOD_CARD` candidates exist in the vault (`count_untried_candidates > 0`) or on pre-existing campaign history, raised plateau lock threshold to `>= 3` consecutive failed/zero-delta runs with `0` untried candidates, removed unconditional `scout_sota` directives from `diagnose_bottleneck`, and decoupled `"đề xuất phương pháp"` prompts from paper-search auto-routing.

---

## [3.5.1] - 2026-11-17

### Changed
- **Zero-Regex Structural Provenance & Domain-Agnostic Subword TF-IDF Novelty (`LAW-01`, `GATE-034`):** Removed static keyword buckets (`_MECHANISM_FAMILIES`) and phrase regexes (`_SELF_FABRICATED_PATTERNS`), replacing them with pure URI scheme/host parsing (`urlparse`) for `07_METHOD_VAULT` provenance and IDF-weighted subword 3/4-gram cosine + graph module/bottleneck overlap in `novelty_guard.py`.
- **Lossless Pass/Fail Scaling Across 100+ Experiments (`outcome_ledger.py`, `tiers.py`):** Preserved negative `REVERT`/`FAILED`/`DISCARD`/`REJECTED` verdicts across REM-sleep episodic consolidation (never overwritten by `CONSOLIDATED`), split `SEM-XXX` consolidated nodes into structured `Verified Wins` vs `Falsified Dead-Ends` ledgers from typed SQLite columns, and surfaced `L0 PROVEN WINS` + `L0 FALSIFIED DEAD-ENDS` directly in session capsules.

---

## [3.5.0] - 2026-11-17

### Added
- **Anti-Stagnation Research Circuit-Breaker (`stagnation_guard.py`):** Automatically detects local hill-climbing plateaus (`>= 2` consecutive `REVERT`/`FAILED`/`DISCARD` runs, `>= 3` consecutive flat/non-improving deltas `<= 1e-5`, or `>= 2` failed attempts on the same `BNK-XXX`), injects `🚨 ANTI-STAGNATION CIRCUIT-BREAKER` alerts in `log_experiment` and `PreInvocation`/`UserPromptSubmit`, and hard-blocks `manage_proposal(action="create")` until fresh verified external SOTA literature is scouted.
- **Anti-Hallucination Citation Provenance Gate (`07_METHOD_VAULT`):** Rejects self-fabricated internal notes/venues or local file paths disguised as `METH-XXX` papers (`LAW-01`), tags cards with `VERIFIED_EXTERNAL` vs `UNVERIFIED_MANUAL` scholarly domain provenance (`arxiv.org`, `doi.org`, `semanticscholar.org`, `openalex.org`, `openreview.net`, etc.), and requires `VERIFIED_EXTERNAL` provenance to unlock stagnation locks.
- **Updated v3.5 Rules & Skills (`AGENTS.md`, `supermemory-research`, `supermemory-experiment`):** Synchronized plugin instructions across Antigravity CLI and Claude Code with zero-turn auto-recall, `supersedes=[...]`, Kanban `task_updates`, and anti-stagnation pivot rules.

---

## [3.4.1] - 2026-11-17

### Added
- **Closed-Loop Kanban Autopilot (`kanban_digest.py`, `GATE-032`):**
  - Rendered live `RUNNING`/`QUEUED` Kanban tasks and `IMPLEMENTING`/`DESIGNED` proposals with `[x]`/`[ ]` subtask indices directly into `memory/01_ACTIVE_STATE.md`.
  - Added SHA-1 Kanban board revision fingerprinting in `PreInvocation` / `UserPromptSubmit` so newly added or edited Web Studio Kanban tasks (e.g., `DAG-025`) are injected into the agent's prompt immediately on the next turn without user reminders.
  - Tracked `pending_kanban_sync` separately from `log_experiment` and insight-only `checkpoint` calls so `PostToolUse` and `Stop` require ticking completed Kanban subtasks (or explicit `status="CLEAN"` attestation when midway).

### Fixed
- **Newest-First Proposal & Experiment Slicing:** Fixed `01_ACTIVE_STATE.md` and `SessionStart` capsule slicing (`list_experiments()[:6]` and `limit=100` newest-first active proposals) so recent experiments and high-numbered proposals (e.g., `PROP-018`, `EXP-MAIN-040`) are never truncated behind early Day-1 entries, and upgraded `summarize_active_task_focus` to surface multiple newest active items.

---

## [3.4.0] - 2026-11-17

### Added
- **Relational Temporal Fact Supersession & Baseline Decay (`METH-002`, `supermemory.graph.supersession`):** Added directional `SUPERSEDES` Personalized PageRank flow (`1.6x` forward to newer truth, `0.25x` backward), `0.42x` score decay on superseded positive observations (`status="SUPERSEDED"`), and `0.72x` decay on baseline experiments beaten via `IMPROVES_OVER` — while preserving `100%` unpenalized strength on `LESSON`, `FAILURE_INSIGHT`, and `REVERT`/`FAILED` dead-ends.
- **Atomic `supersedes=[...]` Wiring in `checkpoint` & `log_experiment`:** Added optional `supersedes` parameter (`--supersedes` on CLI) to automatically link `SUPERSEDES` edges, tag `superseded_by` in recall cards, and retire outdated positive observations in 1 call.
- **Zero-Turn Hook Auto-Recall (`PreInvocation` & `UserPromptSubmit`):** Automatically injects up to `3` session-deduplicated, non-superseded domain memories (`BNK`, `METH`, `OBS`, `EXP`, `PROP`) plus anti-repeat warnings in `< 25ms` before the first model turn across both Antigravity CLI and Claude Code (resetting cleanly on context compaction).

### Fixed
- **Hybrid Recall Hook Score Scale:** Updated `_on_pre_invocation` threshold from legacy v2 BM25 scale (`>= 8.5`) to normalized v3 hybrid scale (`>= 0.22` warnings / `>= 0.26` direct context).

---

## [3.3.5] - 2026-11-17

### Added
- **Keep-a-Changelog Release Ledger (`CHANGELOG.md`):** Documented full release history (`v1.0.0` – `v3.3.5`) with tag diff links and linked it from `README.md` and `README.vi.md`.
- **`CHANGELOG_SYNC` PreToolUse & Audit CodeGate (`GateType.CHANGELOG_SYNC`, `GATE-030`):** Blocks any `pyproject.toml` version bump at `PreToolUse` and `supermemory audit` unless `CHANGELOG.md` already contains a matching `## [X.Y.Z] - YYYY-MM-DD` release entry.

### Fixed
- **Version-Agnostic README Headers (`GATE-031`):** Removed stale hardcoded version strings (`v3.2`, `Web Studio 3.1`) from `README.md` and `README.vi.md`.

---

## [3.3.4] - 2026-11-16

### Added
- **Dynamic Browser-Measured Zero-Shift Pagination (`syncPagers` / `resetPagers`):** Measures Page 1's natural unclipped height on visible tabs and locks container `minHeight` across Pages `2..N` (`0px` `Prev`/`Next` button drift without hardcoded card `height:` CSS).
- **Anti-Clip CSS Geometry Gate (`GATE-029`):** Bans fixed `height:` declarations on text card/row containers in `styles.css`.

### Fixed
- **Flex-Column Vertical Squashing & Button Clipping:** Removed hardcoded `rem` heights across `Constitution & Gates`, `Research & DAG`, `Tiers`, `Proposals`, and `System Events`; added `flex-shrink: 0` and W3C `nowrap` ellipsis titles so `50%`–`200%` Firefox/Chrome zoom never clips titles or bottom action buttons.
- **Paginated Active-First Fast-DAG Waves:** Sorted Wave 1–3 columns `RUNNING` -> `QUEUED` -> `DONE` (newest first) and paginated to `3` cards per Wave column instead of stacking old `DONE` runs into an unpaginated tower.
- **1440p Experiment Ledger & System Events Polish:** Widened `Verdict` column (`12.25rem`) so `VICTORY_CONFIRMED` pills never clip, added ellipsis on table headers, and enabled 2-column `System Events` starting at `>= 78rem` (`1248px+`).

---

## [3.3.3] - 2026-11-16

### Changed
- **Locked Table & Task-List Column Tracks (`GATE-028`):** Switched `Experiment Ledger` (`table-layout: fixed`) and `Task List` rows to fixed-width peripheral columns so column boundaries stay aligned across pagination.
- **Inline Compact System Event Actions:** Merged `Open <NODE>` buttons inline with relative/wall-clock timestamps inside `System Events` rows.

---

## [3.3.2] - 2026-11-16

### Added
- **Default-ON `4s` Live Stream (`GATE-027`):** Enabled `Live` auto-sync by default in Web Studio (`sessionStorage`-persisted toggle) with a live `System Events` count badge in the sidebar.
- **Complete Audit, Kanban & Stop-Hook Event Telemetry:** Emitted structured events for `GATE_AUDIT_PASSED`, `GATE_AUDIT_FAILED`, `GATE_UPSERTED`, `DAG_TASK_ENQUEUED`, `KANBAN_STEP_TOGGLED`, `CHECKPOINT_SYNCED`, and `STOP_GATE_ENFORCED` with local relative + wall-clock timestamps (`4m ago · 19:11:58`).

---

## [3.3.1] - 2026-11-16

### Fixed
- **Circular-Safe Inward-Only Kernel Imports (`GATE-025`):** Moved `checkpoint` domain handler into `supermemory.kernel.checkpoint_ops` so `supermemory.kernel` never imports outward adapters (`mcp`, `ui`, `hooks`, `cli`).
- **Compact Linear-Style Task List (`GATE-026`) & Word-Boundary Ellipsis:** Replaced tall multi-checkbox `Task List` cards with compact single-line rows (`ID + Status | Title + Next Step | Role | Progress | Actions`) and clean word-boundary truncation.

---

## [3.3.0] - 2026-11-16

### Changed
- **SOLID Hexagonal `CommandRegistry` (`GATE-024`):** Unified all 17 domain commands so 1 `@REGISTRY.register` definition drives MCP tool schemas, Unit-of-Work transactions, Markdown compilation, and hook mutation classification.
- **Single-Source-of-Truth Version (`GATE-022`, `GATE-023`) & Lazy CLI Isolation:** Resolved `__version__` dynamically from `pyproject.toml`, stamped `{{SM_VERSION}}` into `index.html` at serve time, and lazy-loaded CLI subcommands to keep hook latency `< 20ms`.

---

## [3.2.1] - 2026-11-16

### Added
- **Domain-Agnostic AI Notification Bus (`GATE-021`):** Upgraded `PostToolUse` hook notifications to structural file/command classification without domain-specific metric regexes, and enforced strict Kanban subtask schemas on proposals.

---

## [3.2.0] - 2026-11-16

### Added
- **Zero-Reminder Closed-Loop Auto-Sync (`checkpoint`):** Added 1-call atomic `checkpoint` MCP/CLI command (`insights`, `new_task`, `task_updates`, `next_actions`, `current_phase`) coupled with `PostToolUse` and `Stop` turn-attestation hooks (`GATE-020`).

---

## [3.1.4] - 2026-11-16

### Fixed
- **Zero-Loop Editable Server Version Sync (`GATE-018`, `GATE-019`):** Read live `ui_version` from disk `pyproject.toml` and guarded `app.js` auto-reload with semver comparison + `sessionStorage` circuit breaker.

---

## [3.1.3] - 2026-11-16

### Added
- **Native Claude Code Integration (`supermemory install-plugin`):** Automated installation of `supermemory_graph` MCP server (`~/.claude.json`), 5 lifecycle hooks (`~/.claude/settings.json`), 9 slash skills, 8 subagents, and `@AGENTS.md` import in `CLAUDE.md`.
- **Developer-First Bilingual README (`< 150` Lines, `GATE-016`, `GATE-017`):** Rewrote `README.md` and `README.vi.md` with real Studio screenshots and concise CLI/MCP reference tables.

---

## [3.1.2] - 2026-11-15

### Changed
- **Full-Width 8-Page Fluid Studio (`GATE-014`, `GATE-015`):** Removed fixed container `max-width` caps across all 8 tabs, added viewport culling for `200+` node graphs, and bounded Kanban column scrolling.

---

## [3.1.0] - 2026-11-15

### Added
- **Interactive Kanban Board & Granular Subtask Checklists (`v3.1.0` – `v3.1.1`):** Shipped 4-stage drag-and-drop Kanban board (`Backlog`, `Ready`, `In Progress`, `Done`), interactive subtask checkboxes, `Task List` view, and `4s` live polling.

---

## [3.0.0] - 2026-11-15

### Added
- **Bottleneck-First Research Engine & SOTA Paper Scout (`v3.0.0` – `v3.0.3`):** Added Pareto error-slice diagnostics (`BNK-XXX`, `RQ-XXX`), cached `arXiv` / `Semantic Scholar` / `OpenAlex` SOTA method cards (`METH-XXX`), Personalized PageRank + subword n-gram hybrid recall (`compact=True` 2-stage progressive disclosure), and 3-wave glob-locked Fast-DAG orchestration.

---

## [2.0.0] - 2026-11-15

### Added
- **4-Tier Federated Cognitive Graph & Daylight Web Studio (`v2.0` – `v2.6.1`):** Introduced `L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, and `L3 EPISODIC` memory tiers across Local + Global + Sibling workspaces, interactive 4-mode Knowledge Graph (`Force`, `Radial`, `Hierarchy`, `Lanes`), Command Palette, split-pane Inspector, and zero-CDN LaTeX math rendering.

---

## [1.0.0] - 2026-11-15

### Added
- **Initial Release:** SQLite WAL + FTS5 knowledge graph, `LAW-01`..`LAW-08` Constitutional Markdown compiler, `PreToolUse` CodeGate enforcer (`MAX_LINES`, `FORBIDDEN_REGEX`, `FORBIDDEN_FILENAME`, `FORBIDDEN_CMD_PATTERN`, `FROZEN_SHA256`, `AST_SYNTAX`), OpenSpec proposal state machine, and Antigravity CLI plugin package.

[3.5.2]: https://github.com/vtnguyen04/research-supermemory/compare/v3.5.1...v3.5.2
[3.5.1]: https://github.com/vtnguyen04/research-supermemory/compare/v3.5.0...v3.5.1
[3.5.0]: https://github.com/vtnguyen04/research-supermemory/compare/v3.4.1...v3.5.0
[3.4.1]: https://github.com/vtnguyen04/research-supermemory/compare/v3.4.0...v3.4.1
[3.4.0]: https://github.com/vtnguyen04/research-supermemory/compare/v3.3.5...v3.4.0
[3.3.5]: https://github.com/vtnguyen04/research-supermemory/compare/v3.3.4...v3.3.5
[3.3.4]: https://github.com/vtnguyen04/research-supermemory/compare/v3.3.3...v3.3.4
[3.3.3]: https://github.com/vtnguyen04/research-supermemory/compare/v3.3.2...v3.3.3
[3.3.2]: https://github.com/vtnguyen04/research-supermemory/compare/v3.3.1...v3.3.2
[3.3.1]: https://github.com/vtnguyen04/research-supermemory/compare/v3.3.0...v3.3.1
[3.3.0]: https://github.com/vtnguyen04/research-supermemory/compare/v3.2.1...v3.3.0
[3.2.1]: https://github.com/vtnguyen04/research-supermemory/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/vtnguyen04/research-supermemory/compare/v3.1.4...v3.2.0
[3.1.4]: https://github.com/vtnguyen04/research-supermemory/compare/v3.1.3...v3.1.4
[3.1.3]: https://github.com/vtnguyen04/research-supermemory/compare/v3.1.2...v3.1.3
[3.1.2]: https://github.com/vtnguyen04/research-supermemory/compare/v3.1.1...v3.1.2
[3.1.0]: https://github.com/vtnguyen04/research-supermemory/compare/v3.0.3...v3.1.0
[3.0.0]: https://github.com/vtnguyen04/research-supermemory/compare/v2.6.1...v3.0.0
[2.0.0]: https://github.com/vtnguyen04/research-supermemory/compare/v2.5.0...v2.6.1
[1.0.0]: https://github.com/vtnguyen04/research-supermemory/releases/tag/v2.5.0
