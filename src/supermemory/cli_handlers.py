"""Command handlers backing the `supermemory` CLI."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.federation import ensure_global_memory, federated_recall
from supermemory.cognitive.tiers import build_tiered_capsule, compute_tier_telemetry
from supermemory.gates.enforcer import GateEnforcer
from supermemory.graph.query_engine import QueryEngine
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.models import CodeGate
from supermemory.self_learning.consolidator import LessonConsolidator
from supermemory.storage.snapshot_io import mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_agent_files, generate_handoff_briefing
from supermemory.sync.claude_installer import install_claude_code_integration
from supermemory.sync.markdown_compiler import MarkdownCompiler
from supermemory.sync.zaloai_importer import import_zaloai_workspace
from supermemory.ui.server import run_ui_server


def handle_init(args: argparse.Namespace) -> int:
    res = init_workspace(
        Path(args.dir),
        project_name=args.name or "",
        max_lines=args.max_lines,
        active_goal=args.goal or "",
    )
    print(f"✅ Initialized SuperMemory in: {res['workspace']}")
    print(f"   Project: {res['project_name']} | Max lines/file: < {res['max_lines']}")
    for k, v in res["memory_files"].items():
        print(f"   • {k}: {v}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    ws = ensure_global_memory() if getattr(args, "use_global", False) else Path(args.workspace).resolve()
    if not (ws / ".supermemory").is_dir() and not (ws / "memory" / "graph_snapshot.json").is_file():
        print(f"ℹ️ No Local SuperMemory in `{ws}` yet — showing Global SuperMemory (`{ensure_global_memory()}`).")
        ws = ensure_global_memory()
    with GraphStore(ws) as store:
        qe = QueryEngine(store)
        print(build_tiered_capsule(store))
        print("\n📊 Graph Telemetry:", json.dumps(qe.graph_analytics(), ensure_ascii=False))
        print("🧠 Cognitive Tiers:", json.dumps(compute_tier_telemetry(store), ensure_ascii=False))
    return 0


def handle_recall(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    local_ok = ((ws / ".supermemory").is_dir() or (ws / "memory" / "graph_snapshot.json").is_file()) and not getattr(args, "use_global", False)
    res = federated_recall(
        args.query,
        local_ws=ws if local_ok else None,
        include_global=True,
        include_siblings=bool(getattr(args, "siblings", False)),
        limit=args.limit,
        hops=args.hops,
    )
    if res["anti_repeat_warnings"]:
        print("⚠️ ANTI-REPEAT WARNINGS:")
        for w in res["anti_repeat_warnings"]:
            print(f"  • {w}")
    print(f"\n🔍 Recalled {len(res['results'])} federated entities for '{args.query}':")
    for r in res["results"]:
        via = f" (hop={r['hop']} via {r.get('via_relation')})" if r.get("hop") else ""
        print(f"  [{r.get('scope', 'LOCAL')}/{r.get('tier', '')}/{r['type']}] {r['id']} [{r['status']}]{via}: {r['title']}\n     {r['summary'][:160]}")
    return 0


def handle_learn(args: argparse.Namespace) -> int:
    ws = ensure_global_memory() if getattr(args, "use_global", False) else Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        out = LessonConsolidator(store).record_lesson(
            title=args.title,
            mistake=args.mistake,
            root_cause=args.root_cause,
            prevention_rule=args.rule,
            user_quote=args.quote or "",
            law_id=args.law or "",
            new_law_title=args.new_law_title or "",
            forbid_regex=args.forbid_regex or "",
            target_glob=args.target_glob,
            forbid_cmd_regex=args.forbid_cmd_regex or "",
            source_exp_id=args.exp_id or "",
        )
        mark_turn_memory_handled(store, clear_lesson_lock=True)
        MarkdownCompiler(store).compile_all()
        generate_agent_files(store, install_workspace_hooks=False)
    print(f"✅ Self-Learning Committed: {out['lesson_id']} -> {out['law_id']} (Gate: {out['gate_id'] or 'Policy'})")
    return 0


def handle_gate(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        enf = GateEnforcer(store)
        if args.gate_cmd == "list":
            for g in store.list_gates():
                print(
                    f"  • {g.id} [{g.gate_type}] ({g.law_id}) blocked={g.blocked_count}: "
                    f"{g.name} | glob={g.target_glob} | pat={g.pattern[:50]}"
                )
        elif args.gate_cmd == "freeze":
            g = enf.freeze_file(args.file, law_id=args.law)
            MarkdownCompiler(store).compile_all()
            print(f"🔒 Frozen SHA-256 Gate Created: {g.id} -> {g.target_glob} ({g.pattern[:16]}...)")
        elif args.gate_cmd == "add":
            gid = LessonConsolidator(store).next_gate_id()
            g = store.upsert_gate(
                CodeGate(
                    id=gid,
                    gate_type=args.type,
                    name=args.name,
                    law_id=args.law,
                    target_glob=args.glob,
                    pattern=args.pattern,
                )
            )
            MarkdownCompiler(store).compile_all()
            print(f"✅ Added CodeGate {g.id} ({g.gate_type}): {g.name}")
    return 0


def handle_idea(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        res = LifecycleManager(store).register_idea(
            title=args.title,
            summary=args.summary,
            expected_impact=args.impact or "",
            risks=args.risks or "",
            status=args.status,
            rejection_reason=args.reject_reason or "",
            is_algorithm=args.algorithm,
            invariants=args.invariants or "",
        )
        MarkdownCompiler(store).compile_all()
    if res["prior_warnings"]:
        print("⚠️ Prior Dead-End / Mistake Warnings:")
        for w in res["prior_warnings"]:
            print(f"  • {w}")
    nd = res["node"]
    print(f"💡 Registered {nd['node_type']} {nd['id']} [{nd['status']}]: {nd['title']}")
    return 0


def handle_proposal(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        lm = LifecycleManager(store)
        if args.prop_cmd == "create":
            tasks = [t.strip() for t in (args.tasks or "").split(";") if t.strip()]
            res = lm.create_proposal(
                title=args.title,
                why=args.why,
                what_changes=args.changes,
                design_notes=args.design or "",
                tasks=tasks or None,
            )
            MarkdownCompiler(store).compile_all()
            print(f"📋 Created Proposal {res['proposal_id']} [{res['stage']}] -> {res['path']}")
        elif args.prop_cmd == "advance":
            nd = lm.advance_proposal(args.id, args.stage, args.note or "")
            MarkdownCompiler(store).compile_all()
            print(f"🚀 Proposal {nd.id} advanced to `{nd.status}`")
    return 0


def handle_exp(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        res = LifecycleManager(store).log_experiment(
            track=args.track,
            exp_id=args.id or "",
            title=args.title,
            hypothesis=args.hypothesis,
            single_var_diff=args.diff,
            model_stack=args.stack or "",
            baseline_id=args.baseline or "",
            proposal_id=args.proposal or "",
            cv_score=args.cv_score,
            cv_summary=args.cv or "",
            test_score=args.test_score,
            test_summary=args.test or "",
            runtime_summary=args.runtime or "",
            verdict=args.verdict,
            post_mortem=args.post_mortem or "",
            insights=list(args.insight or []),
        )
        mark_turn_memory_handled(store)
        MarkdownCompiler(store).compile_all()
    print(
        f"🧪 Logged {res['exp_id']} (Δ={res['delta_vs_baseline']}, regression={res['regression_detected']}) -> {res['log_path']}"
    )
    return 0


def handle_audit_and_sync(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        if args.command == "sync":
            mark_turn_memory_handled(store)
            files = MarkdownCompiler(store).compile_all()
            generate_agent_files(store, install_workspace_hooks=False)
            print(f"🔄 Synced SuperMemory Markdown & Snapshot ({len(files)} artifacts).")
            return 0
        if args.command == "handoff":
            p = generate_handoff_briefing(store)
            print(f"🤝 Generated Zero-Loss Handoff Briefing: {p}")
            return 0
        if args.command == "audit":
            rep = GateEnforcer(store).audit_workspace()
            print(json.dumps(rep, ensure_ascii=False, indent=2))
            return 0 if rep["passed"] else 1
    return 0


def handle_import_zaloai(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    init_workspace(target, project_name=args.name or Path(args.source).resolve().name)
    with GraphStore(target) as store:
        counts = import_zaloai_workspace(Path(args.source), store)
        MarkdownCompiler(store).compile_all()
        generate_agent_files(store, install_workspace_hooks=False)
    print(f"✅ Imported ZALOAI Knowledge Graph into {target}: {counts}")
    return 0


def handle_install_plugin(args: argparse.Namespace) -> int:
    src_pkg = Path(__file__).resolve().parent
    repo_plugin = src_pkg.parents[1] / "plugin"
    wheel_plugin = src_pkg / "_plugin_bundle"
    plugin_src = repo_plugin if (repo_plugin / "plugin.json").is_file() else wheel_plugin
    if not (plugin_src / "plugin.json").is_file():
        print(f"❌ Plugin bundle directory not found: {plugin_src}")
        return 1

    if getattr(args, "claude_only", False):
        c_res = install_claude_code_integration(plugin_src)
        print(f"  [ok]    claude-code (MCP={c_res['mcp_server']}, skills={len(c_res['skills'])}, agents={len(c_res['agents'])}, hooks={len(c_res['hooks'])})")
        return 0

    agy_bin = shutil.which("agy") or str(Path.home() / ".local" / "bin" / "agy")
    if not Path(agy_bin).is_file():
        print("❌ Could not find `agy` binary in PATH or ~/.local/bin/agy")
        return 1

    with tempfile.TemporaryDirectory(prefix="supermemory_pkg_") as stage_dir:
        staged_plugin = Path(stage_dir) / "plugin"
        shutil.copytree(plugin_src, staged_plugin, ignore=shutil.ignore_patterns("lib", "__pycache__", "*.pyc"))
        shutil.copytree(
            src_pkg,
            staged_plugin / "lib" / "supermemory",
            ignore=shutil.ignore_patterns("_plugin_bundle", "__pycache__", "*.pyc"),
        )
        val_res = subprocess.run([agy_bin, "plugin", "validate", "--strict", str(staged_plugin)], check=False)
        if val_res.returncode != 0 or args.validate_only:
            return val_res.returncode
        installed_dir = Path.home() / ".gemini" / "config" / "plugins" / "supermemory"
        if installed_dir.exists():
            subprocess.run([agy_bin, "plugin", "uninstall", "supermemory"], check=False)
        inst_res = subprocess.run([agy_bin, "plugin", "install", str(staged_plugin)], check=False)
        if inst_res.returncode == 0:
            subprocess.run([agy_bin, "plugin", "enable", "supermemory"], check=False)
            if (Path.home() / ".claude").is_dir() or shutil.which("claude"):
                c_res = install_claude_code_integration(plugin_src)
                print(f"  [ok]    claude-code : MCP ({c_res['mcp_server']}) · {len(c_res['skills'])} skills · {len(c_res['agents'])} agents · {len(c_res['hooks'])} hooks -> {c_res['settings_path']}")
        return inst_res.returncode


def handle_ui(args: argparse.Namespace) -> int:
    if getattr(args, "use_global", False):
        target = ensure_global_memory()
    else:
        cand = Path(args.workspace).expanduser().resolve()
        has_local = (cand / ".supermemory").is_dir() or (cand / "memory" / "graph_snapshot.json").is_file()
        target = cand if (has_local or args.workspace != ".") else ensure_global_memory()
    return run_ui_server(target, host=args.host, port=args.port)
