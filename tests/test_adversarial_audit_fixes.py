"""Adversarial Regression Suite for P0-P2 Teamwork Audit Remediation."""

from __future__ import annotations

import io
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command
from supermemory.mcp.server import _read_rpc_message, handle_rpc_request
from supermemory.research.sota_scout import scout_sota_papers
from supermemory.storage.snapshot_io import get_session_state, save_session_state
from supermemory.storage.sqlite_store import GraphStore
from supermemory.ui.server import create_http_server


def test_pretooluse_simulates_replace_multiedit_multiline_and_shell_freeze(tmp_path: Path) -> None:
    """Verify replace_file_content, multi_replace_file_content, multiline regex & shell freeze blocks."""
    ws = tmp_path / "gate_proj"
    init_workspace(ws, project_name="GateSimProj")
    target_py = ws / "src" / "solver.py"
    target_py.parent.mkdir(parents=True, exist_ok=True)
    target_py.write_text("def step(x: int) -> int:\n    return x + 1\n", encoding="utf-8")

    eval_py = ws / "eval" / "verifier.py"
    eval_py.parent.mkdir(parents=True, exist_ok=True)
    eval_py.write_text("SCORE = 1.0\n", encoding="utf-8")
    execute_command("add_gate", {"workspace": str(ws), "freeze_path": "eval/verifier.py", "name": "Freeze verifier"})

    # 1. Invalid regex rejected at gate creation
    with pytest.raises(ValueError, match="Invalid regular expression"):
        execute_command(
            "add_gate",
            {"workspace": str(ws), "gate_type": "FORBIDDEN_REGEX", "name": "Bad Regex", "pattern": "[unclosed"},
        )

    # 2. Multiline FORBIDDEN_REGEX gate
    execute_command(
        "add_gate",
        {
            "workspace": str(ws),
            "gate_type": "FORBIDDEN_REGEX",
            "name": "Block debug block",
            "target_glob": "**/*.py",
            "pattern": r"DEBUG_MODE\s*=\s*True\s*\n\s*SKIP_EVAL\s*=\s*True",
        },
    )

    # 3. Antigravity replace_file_content introducing broken Python syntax -> BLOCKED (decision='deny')
    r_ast = dispatch_hook(
        "PreToolUse",
        {
            "cwd": str(ws),
            "toolCall": {
                "name": "replace_file_content",
                "args": {
                    "TargetFile": str(target_py),
                    "TargetContent": "return x + 1",
                    "ReplacementContent": "return (x + 1",
                },
            },
        },
    )
    assert r_ast.get("decision") == "deny"

    # 4. Antigravity multi_replace_file_content hitting multiline FORBIDDEN_REGEX -> BLOCKED
    r_multi = dispatch_hook(
        "PreToolUse",
        {
            "cwd": str(ws),
            "toolCall": {
                "name": "multi_replace_file_content",
                "args": {
                    "TargetFile": str(target_py),
                    "ReplacementChunks": [
                        {
                            "TargetContent": "return x + 1",
                            "ReplacementContent": "DEBUG_MODE = True\n    SKIP_EVAL = True\n    return x + 1",
                        }
                    ],
                },
            },
        },
    )
    assert r_multi.get("decision") == "deny"

    # 5. Shell redirect attempting to overwrite FROZEN_SHA256 file -> BLOCKED
    r_sh = dispatch_hook(
        "PreToolUse",
        {
            "cwd": str(ws),
            "toolCall": {"name": "run_command", "args": {"CommandLine": "echo 'SCORE = 999' > eval/verifier.py"}},
        },
    )
    assert r_sh.get("decision") == "deny"


def test_lesson_lock_not_bypassed_by_manual_constitution_edit_and_compaction_marker(tmp_path: Path) -> None:
    """Verify editing 02_CONSTITUTION_AND_LESSONS.md cannot clear pending_lesson_lock and SessionStart sets NONE."""
    ws = tmp_path / "hook_lock_proj"
    init_workspace(ws, project_name="HookLockProj")
    t_file = tmp_path / "transcript.jsonl"
    t_file.write_text("", encoding="utf-8")

    dispatch_hook(
        "SessionStart",
        {"hook_event_name": "SessionStart", "session_id": "cc-comp", "cwd": str(ws), "transcript_path": str(t_file)},
    )
    with GraphStore(ws) as store:
        st = get_session_state(store, "cc-comp")
        assert st["last_compaction_marker"] == "NONE"
        st["pending_lesson_lock"] = True
        st["pending_lesson_quote"] = "User scolded hardcoded IDs"
        save_session_state(store, st)

    # Attempting to hand-edit memory/02_CONSTITUTION_AND_LESSONS.md does NOT clear pending_lesson_lock
    dispatch_hook(
        "PostToolUse",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "cc-comp",
            "cwd": str(ws),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(ws / "memory" / "02_CONSTITUTION_AND_LESSONS.md")},
        },
    )
    stop_res = dispatch_hook("Stop", {"hook_event_name": "Stop", "session_id": "cc-comp", "cwd": str(ws)})
    assert stop_res.get("decision") == "block"


def test_web_studio_csrf_dns_rebinding_body_caps_and_scope_allowlist(tmp_path: Path) -> None:
    """Verify Web Studio blocks DNS rebinding, browser CSRF, non-JSON POST, malformed JSON, and rogue scopes."""
    ws = tmp_path / "ui_sec_proj"
    init_workspace(ws, project_name="UISecProj")
    rogue_ws = tmp_path / "unregistered_other"
    rogue_ws.mkdir(parents=True)
    (rogue_ws / ".supermemory").mkdir()

    srv, port = create_http_server(ws, host="127.0.0.1", port=0)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{port}"
    try:
        # 1. DNS rebinding Host header -> 403
        req_dns = urllib.request.Request(f"{base}/api/graph", headers={"Host": "evil.attacker.com"})
        with pytest.raises(urllib.error.HTTPError) as e_dns:
            urllib.request.urlopen(req_dns, timeout=3)
        assert e_dns.value.code == 403

        # 2. Browser cross-origin POST (Origin mismatch / Sec-Fetch-Site: cross-site) -> 403
        req_csrf = urllib.request.Request(
            f"{base}/api/state",
            data=b'{"active_goal":"pwn"}',
            headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as e_csrf:
            urllib.request.urlopen(req_csrf, timeout=3)
        assert e_csrf.value.code == 403

        # 3. Form-encoded POST (no CORS preflight in browsers) -> 415 Unsupported Media Type
        req_form = urllib.request.Request(
            f"{base}/api/state",
            data=b"active_goal=pwn",
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as e_form:
            urllib.request.urlopen(req_form, timeout=3)
        assert e_form.value.code == 415

        # 4. Malformed JSON body -> 400 (clean error, zero crash)
        req_bad = urllib.request.Request(
            f"{base}/api/state",
            data=b"{broken_json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as e_bad:
            urllib.request.urlopen(req_bad, timeout=3)
        assert e_bad.value.code == 400

        # 5. Unregistered arbitrary directory scope -> 403
        req_scope = urllib.request.Request(f"{base}/api/graph?scope={rogue_ws}")
        with pytest.raises(urllib.error.HTTPError) as e_sc:
            urllib.request.urlopen(req_scope, timeout=3)
        assert e_sc.value.code == 403
    finally:
        srv.shutdown()
        srv.server_close()


def test_path_traversal_sibling_readonly_compaction_order_and_mcp_framing(tmp_path: Path) -> None:
    """Verify entity ID path traversal rejection, read-only sibling recall, newest-first L2 compaction & MCP framing."""
    ws_main = tmp_path / "main_vault"
    ws_sib = tmp_path / "sib_snapshot_only"
    init_workspace(ws_main, project_name="MainVault")
    init_workspace(ws_sib, project_name="SibVault")

    # Add reusable METHOD_CARD + private LESSON/DEAD-END in sibling, then delete sibling .supermemory/ DB!
    with GraphStore(ws_sib) as s_store:
        scout_sota_papers(
            s_store,
            query="Kalman rollout",
            save_top_k=1,
            offline_fixtures=[
                {
                    "title": "Differentiable Kalman Filter for Long Rollouts",
                    "abstract": "Stabilizes latent state covariance.",
                    "year": 2025,
                    "venue": "ICML",
                    "citations": 25,
                    "url": "https://arxiv.org/abs/2502.12345",
                    "source": "arxiv",
                }
            ],
        )
    execute_command(
        "record_lesson",
        {
            "workspace": str(ws_sib),
            "title": "Private Sibling Secret Incident",
            "mistake": "Internal key rotation note",
            "root_cause": "Ops config",
            "prevention_rule": "Rotate internal token",
        },
    )
    for f in (ws_sib / ".supermemory").glob("*"):
        f.unlink()
    (ws_sib / ".supermemory").rmdir()
    assert not (ws_sib / ".supermemory").exists()

    # Sibling recall loads snapshot in `:memory:`, creates ZERO `.supermemory` on sibling, and hides private LESSON!
    sib_rec = execute_command(
        "recall", {"workspace": str(ws_main), "query": "Differentiable Kalman Private Incident", "include_siblings": True}
    )
    assert not (ws_sib / ".supermemory").exists()
    assert any(r["id"] == "METH-001" and r["scope"] == "SIBLING:SibVault" for r in sib_rec["results"])
    assert all("SibVault" not in w for w in sib_rec["anti_repeat_warnings"])
    priv_detail = execute_command(
        "recall", {"workspace": str(ws_main), "node_id": "LESSON-001", "include_siblings": True}
    )
    assert "error" in priv_detail

    # Path traversal IDs rejected on Proposal and Experiment
    with pytest.raises(ValueError, match="Invalid `proposal_id`"):
        execute_command("manage_proposal", {"workspace": str(ws_main), "action": "create", "proposal_id": "../../evil", "title": "Valid Proposal Title", "why": "Testing path traversal security guard", "what_changes": "Reject traversal characters in custom IDs"})
    with pytest.raises(ValueError, match="Invalid `exp_id`"):
        execute_command("log_experiment", {"workspace": str(ws_main), "exp_id": "../escape", "track": "main", "title": "Traversal Test Run", "hypothesis": "Verify exp_id sanitizer blocks ../", "single_var_diff": "exp_id validation", "cv_score": 0.9})

    # L2 compaction keeps 12 NEWEST observations active and consolidates OLDER overflow
    stems = [
        "Quantile Pinball Tail", "Kalman Cholesky Jitter", "Hungarian Cosine Track", "SQLite WAL Timeout",
        "Trigram Camel Split", "Enthalpy Boiler Balance", "Cosine AdamW Warmup", "PageRank Damping Hop",
        "HeavyHitter KV Evict", "LogMel Acoustic Filter", "Weisfeiler Cycle Motif", "Barrier Slack Horizon",
        "Poisson Micro Batch", "Monotone Tree Bound", "InfoNCE Margin Tau", "Dynamic RoPE Window",
        "Mmap Float32 Shard", "Bayesian UCB Regret", "BlockSparse SRAM Tile", "Huber Outlier Clip",
        "Polyak Teacher EMA", "Spectral Norm Drift", "Viterbi Bigram Prior", "Schmitt Chiller Band",
        "Dirichlet Ngram Alpha", "Orthogonal QR Layer", "Grouped Fold Leakage",
    ]
    for s_txt in stems:
        execute_command("checkpoint", {"workspace": str(ws_main), "insights": [f"{s_txt}: Verified empirical invariant for {s_txt.lower()}"]})
    execute_command("consolidate", {"workspace": str(ws_main), "mode": "auto", "min_cluster_size": 4})
    with GraphStore(ws_main) as m_store:
        newest = m_store.get_node("OBS-027")
        oldest = m_store.get_node("OBS-001")
        assert newest is not None and newest.status == "SCIENTIFIC_INSIGHT"
        assert oldest is not None and oldest.status == "CONSOLIDATED"

    # MCP malformed framing returns clean JSON-RPC Parse Error (-32700) without raising
    bad_msg = _read_rpc_message(io.BytesIO(b"Content-Length: 999999999\r\n\r\n{}"))
    rpc_err = handle_rpc_request(bad_msg)
    assert rpc_err is not None and rpc_err["error"]["code"] == -32700
