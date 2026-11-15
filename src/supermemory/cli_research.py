"""CLI Subparsers & Handlers for Research v3.0 (`bottleneck`, `scout`, `orchestrate`)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from supermemory.research.bottleneck_engine import (
    diagnose_bottleneck,
    rank_bottlenecks,
    resolve_bottleneck,
)
from supermemory.research.orchestrator import (
    claim_next_task,
    complete_task,
    dag_telemetry,
    list_tasks,
    plan_research_sprint,
)
from supermemory.research.sota_scout import register_method_card, scout_sota_papers
from supermemory.storage.snapshot_io import mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler


def register_research_cli_parsers(sub: Any) -> None:
    """Register `bottleneck`, `scout`, and `orchestrate` CLI subcommands."""
    p_bnk = sub.add_parser("bottleneck", help="Diagnose & rank Pareto research bottlenecks (BNK-XXX + RQ-XXX)")
    p_bnk.add_argument("-w", "--workspace", default=".")
    b_sub = p_bnk.add_subparsers(dest="bnk_cmd", required=True)
    b_sub.add_parser("list")
    bd = b_sub.add_parser("add")
    bd.add_argument("--title", required=True)
    bd.add_argument("--slice", required=True, help="Quantified failure slice evidence")
    bd.add_argument("--share", type=float, required=True, help="Error share percentage (0-100]")
    bd.add_argument("--ceiling", type=float, required=True, help="Oracle metric ceiling gain (>0)")
    bd.add_argument("--rq", required=True, help="Falsifiable Research Question")
    bd.add_argument("--metric", default="primary_metric")
    bd.add_argument("--kill", default="")
    bd.add_argument("--smoke-cmd", default="")
    br = b_sub.add_parser("resolve")
    br.add_argument("id")
    br.add_argument("--exp-id", default="")
    br.add_argument("--note", default="")

    p_sct = sub.add_parser("scout", help="Search SOTA papers (arXiv/S2/OpenAlex) or register METHOD_CARD")
    p_sct.add_argument("-w", "--workspace", default=".")
    s_sub = p_sct.add_subparsers(dest="scout_cmd", required=True)
    ss = s_sub.add_parser("search")
    ss.add_argument("query")
    ss.add_argument("--limit", type=int, default=6)
    ss.add_argument("--min-year", type=int, default=2022)
    ss.add_argument("--save-top", type=int, default=0)
    ss.add_argument("--bottleneck", default="")
    sc = s_sub.add_parser("card")
    sc.add_argument("--title", required=True)
    sc.add_argument("--mechanism", required=True)
    sc.add_argument("--bottleneck", default="")
    sc.add_argument("--addressed", default="")
    sc.add_argument("--limits", default="")
    sc.add_argument("--cost", default="O(N)")
    sc.add_argument("--hook", default="")
    sc.add_argument("--url", default="")
    sc.add_argument("--venue", default="SOTA")
    sc.add_argument("--year", type=int, default=2025)

    p_orc = sub.add_parser("orchestrate", help="Multi-Agent Fast-DAG Sprint Planner & Glob-Lease Scheduler")
    p_orc.add_argument("-w", "--workspace", default=".")
    o_sub = p_orc.add_subparsers(dest="orch_cmd", required=True)
    o_sub.add_parser("status")
    op = o_sub.add_parser("plan")
    op.add_argument("--goal", required=True)
    op.add_argument("--bottleneck", default="")
    op.add_argument("--smoke-cmd", default="pytest -q")
    op.add_argument("--globs", default="src/**")
    oc = o_sub.add_parser("claim")
    oc.add_argument("--agent", default="worker")
    oc.add_argument("--role", default="")
    od = o_sub.add_parser("complete")
    od.add_argument("task_id")
    od.add_argument("--status", default="DONE")
    od.add_argument("--summary", default="")


def handle_bottleneck(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        if args.bnk_cmd == "list":
            items = rank_bottlenecks(store, include_resolved=True)
            print(f"🎯 Pareto Bottlenecks ({len(items)}):")
            for it in items:
                print(
                    f"  [{it['status']}] {it['id']} (Pareto={it['pareto_priority']}, "
                    f"Share={it['error_share_pct']}%, Ceiling=+{it['ceiling_gain']}): {it['title']}"
                )
            return 0
        if args.bnk_cmd == "resolve":
            out = resolve_bottleneck(store, args.id, resolution_exp_id=args.exp_id, note=args.note)
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            print(f"✅ Resolved {out['id']}")
            return 0
        res = diagnose_bottleneck(
            store,
            title=args.title,
            evidence_slice=args.slice,
            error_share_pct=args.share,
            ceiling_gain=args.ceiling,
            falsifiable_rq=args.rq,
            metric_name=args.metric,
            kill_criterion=args.kill,
            smoke_eval_cmd=args.smoke_cmd,
        )
        mark_turn_memory_handled(store)
        MarkdownCompiler(store).compile_all()
        print(
            f"✅ Diagnosed {res['bottleneck']['id']} + {res['research_question']['id']} "
            f"(Pareto Priority={res['pareto_priority']})"
        )
    return 0


def handle_scout(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        if args.scout_cmd == "card":
            card = register_method_card(
                store,
                title=args.title,
                bottleneck_addressed=args.addressed or args.bottleneck or "Target slice",
                core_mechanism=args.mechanism,
                assumptions_and_limits=args.limits or "Validate empirically on slice.",
                complexity_cost=args.cost,
                minimal_integration_hook=args.hook,
                source_url=args.url,
                venue=args.venue,
                year=args.year,
                bottleneck_id=args.bottleneck,
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            print(f"✅ Registered Method Card {card['id']}: {card['title']}")
            return 0
        res = scout_sota_papers(
            store,
            query=args.query,
            limit=args.limit,
            min_year=args.min_year,
            bottleneck_id=args.bottleneck,
            save_top_k=args.save_top,
        )
        if res["saved_method_cards"]:
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
        print(f"🔭 Scouted {len(res['papers'])} papers (cache_hits={res['cache_hits']}, saved={len(res['saved_method_cards'])}):")
        for p in res["papers"]:
            print(f"  • [{p.get('venue')} {p.get('year')} | score={p.get('relevance_score')}] {p.get('title')}")
    return 0


def handle_orchestrate(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        if args.orch_cmd == "plan":
            globs = [g.strip() for g in args.globs.split(",") if g.strip()]
            res = plan_research_sprint(store, goal=args.goal, bottleneck_id=args.bottleneck, smoke_cmd=args.smoke_cmd, target_globs=globs)
            MarkdownCompiler(store).compile_all()
            print(f"⚡ Planned 3-Wave Sprint ({len(res['tasks'])} tasks). Parallel Wave-1: {res['parallel_wave1_ids']}")
            return 0
        if args.orch_cmd == "claim":
            claimed = claim_next_task(store, agent_name=args.agent, role=args.role)
            print(json.dumps({"claimed": claimed}, ensure_ascii=False, indent=2))
            return 0
        if args.orch_cmd == "complete":
            res = complete_task(store, task_id=args.task_id, status=args.status, receipt={"summary": args.summary} if args.summary else {})
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0
        tel = dag_telemetry(store)
        print("🕸️ Fast-DAG Telemetry:", json.dumps(tel, ensure_ascii=False))
        for t in list_tasks(store):
            print(f"  [W{t.wave} | {t.status}] {t.task_id} ({t.role}): {t.title}")
    return 0
