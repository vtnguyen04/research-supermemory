"""Imports ZALOAI-style memory graphs (Laws, Lessons, Experiments, Nodes, OpenSpec) into SuperMemory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from supermemory.models import (
    CodeGate,
    EdgeType,
    ExperimentRecord,
    ExperimentVerdict,
    GateType,
    MemoryEdge,
    MemoryNode,
    NodeType,
    ProposalStage,
)
from supermemory.storage.sqlite_store import GraphStore


def _parse_float_first(text: str) -> Optional[float]:
    m = re.search(r"([+-]?\d+\.\d+)", text or "")
    return float(m.group(1)) if m else None


def import_zaloai_workspace(source_root: Path | str, target_store: GraphStore) -> Dict[str, int]:
    """Read-only extraction of ZALOAI rules, lessons, experiments, knowledge nodes & OpenSpec."""
    src = Path(source_root).resolve()
    mem = src / "memory"
    if not mem.is_dir():
        raise FileNotFoundError(f"No memory/ directory found at {src}")

    counts = {"laws": 0, "lessons": 0, "experiments": 0, "knowledge_nodes": 0, "proposals": 0, "gates": 0}
    target_store.set_meta("imported_from", str(src))
    if not target_store.get_meta("project_name"):
        target_store.set_meta("project_name", src.name)

    # 1. Import Active State summary
    state_file = mem / "01_ACTIVE_STATE.md"
    if state_file.is_file():
        s_txt = state_file.read_text(encoding="utf-8")
        first_bullets = [ln.strip() for ln in s_txt.splitlines() if ln.strip().startswith("- ")][:4]
        if first_bullets:
            target_store.set_meta("active_goal", first_bullets[0].lstrip("- ").strip()[:300])
        target_store.set_meta("state_notes", "\n".join(s_txt.splitlines()[:35]))

    # 2. Import Laws & Consolidated Lessons from 02_USER_CORRECTIONS_AND_LESSONS.md
    const_file = mem / "02_USER_CORRECTIONS_AND_LESSONS.md"
    if const_file.is_file():
        c_txt = const_file.read_text(encoding="utf-8")
        law_blocks = re.split(r"(?=^### `LAW-\d+`)", c_txt, flags=re.MULTILINE)
        for blk in law_blocks:
            m_hdr = re.match(r"^### `(LAW-\d+)`\s*[—–-]\s*(.+)$", blk.splitlines()[0] if blk.strip() else "")
            if not m_hdr:
                continue
            law_id, law_title = m_hdr.group(1), m_hdr.group(2).strip()
            lesson_nums = sorted(set(re.findall(r"\b(\d{3})\b", blk)))
            lesson_ids = [f"LESSON-{num}" for num in lesson_nums]
            target_store.upsert_node(
                MemoryNode(
                    id=law_id,
                    node_type=NodeType.LAW.value,
                    title=law_title,
                    summary=law_title[:220],
                    content=blk.strip()[:3000],
                    file_path="memory/02_CONSTITUTION_AND_LESSONS.md",
                    tags=["law", "zaloai"],
                    priority=100,
                    metadata={"consolidated_lessons": lesson_ids, "recurrence_count": len(lesson_ids)},
                ),
                log_event=False,
            )
            counts["laws"] += 1
            for lid in lesson_ids:
                target_store.upsert_node(
                    MemoryNode(
                        id=lid,
                        node_type=NodeType.LESSON.value,
                        title=f"{lid} (Consolidated under {law_id}: {law_title[:55]})",
                        summary=f"Historical violation consolidated into {law_id}.",
                        content=blk.strip()[:1200],
                        tags=["lesson", law_id.lower()],
                        priority=80,
                        metadata={"law_id": law_id, "severity": "HIGH"},
                    ),
                    log_event=False,
                )
                target_store.add_edge(
                    MemoryEdge(source_id=lid, target_id=law_id, relation=EdgeType.CONSOLIDATED_INTO.value)
                )
                counts["lessons"] += 1

    # 3. Import Experiments from 03_EXPERIMENTS_REGISTRY.md + detailed logs
    reg_file = mem / "03_EXPERIMENTS_REGISTRY.md"
    if reg_file.is_file():
        current_track = "general"
        prev_exp_by_track: Dict[str, str] = {}
        for line in reg_file.read_text(encoding="utf-8").splitlines():
            if "LifeMate" in line and line.startswith("##"):
                current_track = "lifemate"
            elif "DataMate" in line and line.startswith("##"):
                current_track = "datamate"
            elif line.startswith("| **`EXP-"):
                cols = [c.strip() for c in line.strip("|").split("|")]
                if len(cols) < 6:
                    continue
                m_id = re.search(r"(EXP-[A-Z0-9-]+)", cols[0])
                if not m_id:
                    continue
                exp_id = m_id.group(1)
                hyp_col = cols[2]
                stack_col = cols[3].strip("` ")
                cv_col = cols[4]
                lb_col = cols[5]
                verdict_col = cols[7] if len(cols) > 7 else ""
                verdict = (
                    ExperimentVerdict.VICTORY_CONFIRMED.value
                    if ("KỶ LỤC" in lb_col.upper() or "VICTORY" in verdict_col.upper() or "Đỉnh mới" in verdict_col)
                    else (
                        ExperimentVerdict.REVERT.value
                        if ("Tụt" in lb_col or "Tụt" in verdict_col)
                        else ExperimentVerdict.KEEP.value
                    )
                )
                prev_id = prev_exp_by_track.get(current_track, "")
                rec = ExperimentRecord(
                    exp_id=exp_id,
                    track=current_track,
                    title=hyp_col[:95].strip("* "),
                    hypothesis=hyp_col[:500],
                    single_var_diff=hyp_col[:350],
                    model_stack=stack_col[:120],
                    baseline_id=prev_id,
                    cv_score=_parse_float_first(cv_col),
                    cv_summary=cv_col[:120],
                    test_score=_parse_float_first(lb_col),
                    test_summary=lb_col[:120],
                    verdict=verdict,
                    post_mortem=verdict_col[:400],
                )
                detail_md = mem / "experiments" / current_track / f"{exp_id}.md"
                rich_body = (
                    detail_md.read_text(encoding="utf-8", errors="ignore")[:4000]
                    if detail_md.is_file()
                    else f"{hyp_col}\n\nVerdict: {verdict_col}"
                )
                target_store.upsert_experiment(rec)
                target_store.upsert_node(
                    MemoryNode(
                        id=exp_id,
                        node_type=NodeType.EXPERIMENT.value,
                        title=rec.title,
                        status=verdict,
                        summary=f"[{current_track}] LB={lb_col[:80]}",
                        content=rich_body,
                        tags=["experiment", current_track, verdict.lower()],
                        priority=85,
                        metadata=rec.to_dict(),
                    ),
                    log_event=False,
                )
                if prev_id:
                    rel = EdgeType.REGRESSED_FROM.value if verdict == ExperimentVerdict.REVERT.value else EdgeType.DERIVED_FROM.value
                    target_store.add_edge(MemoryEdge(source_id=exp_id, target_id=prev_id, relation=rel))
                for cited_ls in set(re.findall(r"LESSON-\d{3}", f"{hyp_col} {lb_col} {verdict_col}")):
                    if target_store.get_node(cited_ls):
                        target_store.add_edge(
                            MemoryEdge(source_id=exp_id, target_id=cited_ls, relation=EdgeType.PRODUCED_LESSON.value)
                        )
                prev_exp_by_track[current_track] = exp_id
                counts["experiments"] += 1

    # 4. Import Knowledge Nodes & Research files
    kn_dir = mem / "04_KNOWLEDGE_NODES"
    if kn_dir.is_dir():
        for idx, md_f in enumerate(sorted(kn_dir.glob("*.md")), 1):
            nid = f"NODE-{md_f.stem.upper()[:20]}"
            body = md_f.read_text(encoding="utf-8", errors="ignore")
            first_hdr = body.splitlines()[0].lstrip("# ").strip() if body.strip() else md_f.stem
            target_store.upsert_node(
                MemoryNode(
                    id=nid,
                    node_type=NodeType.KNOWLEDGE_NODE.value,
                    title=first_hdr[:120],
                    summary=body[:220].replace("\n", " "),
                    content=body[:4000],
                    tags=["knowledge-node", "domain-brain"],
                    priority=88 - idx,
                ),
                log_event=False,
            )
            counts["knowledge_nodes"] += 1

    # 5. Import OpenSpec Changes as PROPOSAL nodes
    os_changes = src / "openspec" / "changes"
    if os_changes.is_dir():
        for ch_dir in sorted(os_changes.iterdir()):
            prop_md = ch_dir / "proposal.md"
            if ch_dir.is_dir() and prop_md.is_file():
                pid = f"PROP-{ch_dir.name.upper()[:24]}"
                p_txt = prop_md.read_text(encoding="utf-8", errors="ignore")
                target_store.upsert_node(
                    MemoryNode(
                        id=pid,
                        node_type=NodeType.PROPOSAL.value,
                        title=f"OpenSpec: {ch_dir.name}",
                        status=ProposalStage.IMPLEMENTING.value,
                        summary=p_txt[:220].replace("\n", " "),
                        content=p_txt[:4000],
                        tags=["openspec", "proposal"],
                        priority=90,
                    ),
                    log_event=False,
                )
                counts["proposals"] += 1

    # 6. Import CodeGates from ZALOAI run_submission.py (_FROZEN_VERIFIER_SHA256)
    run_sub = src / "datamate" / "src" / "run_submission.py"
    if run_sub.is_file():
        r_txt = run_sub.read_text(encoding="utf-8", errors="ignore")
        for m_sha in re.finditer(r'"([^"]+\.py)"\s*:\s*"([0-9a-f]{64})"', r_txt):
            rel_py, sha_hex = m_sha.group(1), m_sha.group(2)
            gid = f"GATE-ZALO-{Path(rel_py).stem.upper()[:14]}"
            gate = target_store.upsert_gate(
                CodeGate(
                    id=gid,
                    gate_type=GateType.FROZEN_SHA256.value,
                    name=f"ZALOAI Frozen Verifier: {rel_py}",
                    law_id="LAW-01",
                    target_glob=f"datamate/src/{rel_py}",
                    pattern=sha_hex,
                )
            )
            target_store.upsert_node(
                MemoryNode(id=gid, node_type=NodeType.GATE.value, title=gate.name, summary=f"SHA256={sha_hex[:16]}...", metadata=gate.to_dict()),
                log_event=False,
            )
            target_store.add_edge(MemoryEdge(source_id="LAW-01", target_id=gid, relation=EdgeType.ENFORCED_BY.value))
            counts["gates"] += 1

    target_store.log_event("ZALOAI_IMPORT", src.name, f"Imported ZALOAI graph: {counts}")
    return counts
