"""Universal CLI entrypoint for SuperMemory (`supermemory`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from supermemory import __version__
from supermemory.cli_cognitive import (
    handle_checkpoint,
    handle_consolidate,
    handle_promote,
    handle_workspaces,
)
from supermemory.cli_handlers import (
    handle_audit_and_sync,
    handle_exp,
    handle_gate,
    handle_idea,
    handle_import_zaloai,
    handle_init,
    handle_install_plugin,
    handle_learn,
    handle_proposal,
    handle_recall,
    handle_status,
    handle_ui,
)
from supermemory.cli_research import (
    handle_bottleneck,
    handle_orchestrate,
    handle_scout,
    register_research_cli_parsers,
)
from supermemory.hooks.runner import main_from_stdin
from supermemory.mcp.server import run_mcp_stdio_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supermemory",
        description="SuperMemory v2.0: Tiered Cognitive Graph, Federated Local/Global Memory & Antigravity Extension",
    )
    parser.add_argument("--version", action="version", version=f"supermemory {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize Local SuperMemory in a project folder")
    p_init.add_argument("dir", nargs="?", default=".")
    p_init.add_argument("--name", default="")
    p_init.add_argument("--max-lines", type=int, default=300)
    p_init.add_argument("--goal", default="")

    p_status = sub.add_parser("status", help="Display 4-Tier Cognitive capsule & graph telemetry")
    p_status.add_argument("-w", "--workspace", default=".")
    p_status.add_argument("-g", "--global", dest="use_global", action="store_true")

    p_rec = sub.add_parser("recall", help="Federated (Local + Global) BM25 + 2-hop Knowledge Graph search")
    p_rec.add_argument("query")
    p_rec.add_argument("--limit", type=int, default=10)
    p_rec.add_argument("--hops", type=int, default=1)
    p_rec.add_argument("-w", "--workspace", default=".")
    p_rec.add_argument("-g", "--global", dest="use_global", action="store_true")
    p_rec.add_argument("-s", "--siblings", action="store_true", help="Include sibling research vaults")

    p_learn = sub.add_parser("learn", help="Record a self-learning lesson/rule into Local or Global LAW + Gate")
    p_learn.add_argument("--title", required=True)
    p_learn.add_argument("--mistake", required=True)
    p_learn.add_argument("--root-cause", required=True)
    p_learn.add_argument("--rule", required=True)
    p_learn.add_argument("--quote", default="")
    p_learn.add_argument("--law", default="")
    p_learn.add_argument("--new-law-title", default="")
    p_learn.add_argument("--forbid-regex", default="")
    p_learn.add_argument("--target-glob", default="**/*.py")
    p_learn.add_argument("--forbid-cmd-regex", default="")
    p_learn.add_argument("--exp-id", default="")
    p_learn.add_argument("-w", "--workspace", default=".")
    p_learn.add_argument("-g", "--global", dest="use_global", action="store_true")

    p_gate = sub.add_parser("gate", help="Manage executable CodeGates & SHA-256 file freezes")
    p_gate.add_argument("-w", "--workspace", default=".")
    g_sub = p_gate.add_subparsers(dest="gate_cmd", required=True)
    g_sub.add_parser("list")
    gf = g_sub.add_parser("freeze")
    gf.add_argument("file")
    gf.add_argument("--law", default="LAW-05")
    ga = g_sub.add_parser("add")
    ga.add_argument("--type", default="FORBIDDEN_REGEX")
    ga.add_argument("--name", required=True)
    ga.add_argument("--law", default="LAW-08")
    ga.add_argument("--glob", default="**/*.py")
    ga.add_argument("--pattern", required=True)

    p_idea = sub.add_parser("idea", help="Log an IDEA or ALGORITHM (with dead-end memory)")
    p_idea.add_argument("--title", required=True)
    p_idea.add_argument("--summary", required=True)
    p_idea.add_argument("--impact", default="")
    p_idea.add_argument("--risks", default="")
    p_idea.add_argument("--status", default="SEED")
    p_idea.add_argument("--reject-reason", default="")
    p_idea.add_argument("--algorithm", action="store_true")
    p_idea.add_argument("--invariants", default="")
    p_idea.add_argument("-w", "--workspace", default=".")

    p_prop = sub.add_parser("proposal", help="Create or advance OpenSpec lifecycle proposals")
    p_prop.add_argument("-w", "--workspace", default=".")
    pr_sub = p_prop.add_subparsers(dest="prop_cmd", required=True)
    prc = pr_sub.add_parser("create")
    prc.add_argument("--title", required=True)
    prc.add_argument("--why", required=True)
    prc.add_argument("--changes", required=True)
    prc.add_argument("--design", default="")
    prc.add_argument("--tasks", default="")
    pra = pr_sub.add_parser("advance")
    pra.add_argument("id")
    pra.add_argument("stage")
    pra.add_argument("--note", default="")

    p_exp = sub.add_parser("exp", help="Log a scientific experiment & crystallize insights")
    p_exp.add_argument("--track", default="main")
    p_exp.add_argument("--id", default="")
    p_exp.add_argument("--title", required=True)
    p_exp.add_argument("--hypothesis", required=True)
    p_exp.add_argument("--diff", required=True)
    p_exp.add_argument("--stack", default="")
    p_exp.add_argument("--baseline", default="")
    p_exp.add_argument("--proposal", default="")
    p_exp.add_argument("--cv-score", type=float, default=None)
    p_exp.add_argument("--cv", default="")
    p_exp.add_argument("--test-score", type=float, default=None)
    p_exp.add_argument("--test", default="")
    p_exp.add_argument("--runtime", default="")
    p_exp.add_argument("--verdict", default="KEEP")
    p_exp.add_argument("--post-mortem", default="")
    p_exp.add_argument("--insight", action="append", default=[])
    p_exp.add_argument("-w", "--workspace", default=".")

    p_ws = sub.add_parser("workspaces", help="List Global SuperMemory + all Local project workspaces")
    p_ws.add_argument("-w", "--workspace", default=".")

    p_cons = sub.add_parser("consolidate", help="Merge Episodic nodes into Semantic/Procedural memory")
    p_cons.add_argument("--ids", default="", help="Comma-separated source node IDs")
    p_cons.add_argument("--tier", choices=["SEMANTIC", "PROCEDURAL"], default="SEMANTIC")
    p_cons.add_argument("--title", default="")
    p_cons.add_argument("--summary", default="")
    p_cons.add_argument("--content", default="")
    p_cons.add_argument("--auto", action="store_true")
    p_cons.add_argument("--min-cluster", type=int, default=3)
    p_cons.add_argument("-w", "--workspace", default=".")
    p_cons.add_argument("-g", "--global", dest="use_global", action="store_true")

    p_prom = sub.add_parser("promote", help="Promote a Local node/law/insight up to Global SuperMemory")
    p_prom.add_argument("node_id")
    p_prom.add_argument("-w", "--workspace", default=".")

    p_chk = sub.add_parser("checkpoint", help="Semantic turn-closing checkpoint attestation")
    p_chk.add_argument("--status", choices=["CLEAN", "CAPTURED"], default="CLEAN")
    p_chk.add_argument("--note", default="")
    p_chk.add_argument("--insight-title", default="")
    p_chk.add_argument("--insight-summary", default="")
    p_chk.add_argument("--tier", choices=["SEMANTIC", "PROCEDURAL"], default="SEMANTIC")
    p_chk.add_argument("-w", "--workspace", default=".")
    p_chk.add_argument("-g", "--global", dest="use_global", action="store_true")

    for simple_cmd, desc in (
        ("audit", "Run all Constitutional & Clean-Code gates across workspace"),
        ("sync", "Compile SQLite Graph -> Markdown files, Snapshot & Agent Rules"),
        ("handoff", "Generate compaction-proof cross-agent HANDOFF_BRIEFING.md"),
    ):
        ps = sub.add_parser(simple_cmd, help=desc)
        ps.add_argument("-w", "--workspace", default=".")

    p_imp = sub.add_parser("import-zaloai", help="Import Laws, Lessons, Experiments & Nodes from ZALOAI")
    p_imp.add_argument("source")
    p_imp.add_argument("--target", default=".")
    p_imp.add_argument("--name", default="")

    p_plug = sub.add_parser("install-plugin", help="Validate (--strict) and install into Antigravity CLI & Claude Code")
    p_plug.add_argument("--validate-only", action="store_true")
    p_plug.add_argument("--claude-only", action="store_true", help="Install only into Claude Code (~/.claude)")

    p_ui = sub.add_parser("ui", help="Launch Multi-Project & Tiered Knowledge Graph Web Observatory")
    p_ui.add_argument("-w", "--workspace", default=".")
    p_ui.add_argument("-g", "--global", dest="use_global", action="store_true", help="Open Global SuperMemory directly")
    p_ui.add_argument("--host", default="127.0.0.1")
    p_ui.add_argument("--port", type=int, default=8765)

    p_hook = sub.add_parser("hook", help="Internal Antigravity & Claude Code lifecycle hook stdin/stdout handler")
    p_hook.add_argument("event", choices=["SessionStart", "PreInvocation", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"])

    p_mcp = sub.add_parser("mcp", help="Run SuperMemory Stdio MCP Server")
    p_mcp.add_argument("-w", "--workspace", default="")

    register_research_cli_parsers(sub)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {
        "init": handle_init,
        "status": handle_status,
        "recall": handle_recall,
        "learn": handle_learn,
        "gate": handle_gate,
        "idea": handle_idea,
        "proposal": handle_proposal,
        "exp": handle_exp,
        "workspaces": handle_workspaces,
        "consolidate": handle_consolidate,
        "promote": handle_promote,
        "checkpoint": handle_checkpoint,
        "audit": handle_audit_and_sync,
        "sync": handle_audit_and_sync,
        "handoff": handle_audit_and_sync,
        "import-zaloai": handle_import_zaloai,
        "install-plugin": handle_install_plugin,
        "ui": handle_ui,
        "bottleneck": handle_bottleneck,
        "scout": handle_scout,
        "orchestrate": handle_orchestrate,
    }
    if args.command in dispatch:
        return dispatch[args.command](args)
    if args.command == "hook":
        return main_from_stdin(args.event)
    if args.command == "mcp":
        default_ws = Path(args.workspace).resolve() if args.workspace else None
        return run_mcp_stdio_server(default_ws=default_ws)
    return 1


if __name__ == "__main__":
    sys.exit(main())
