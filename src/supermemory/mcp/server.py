"""Zero-dependency Stdio JSON-RPC 2.0 MCP Server for SuperMemory."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional
from urllib.parse import unquote, urlparse

from supermemory import __version__
from supermemory.cognitive.federation import resolve_default_workspace, set_active_workspace
from supermemory.mcp.tool_defs import MCP_TOOLS, execute_mcp_tool

_CLIENT_ROOT: Optional[Path] = None


def _read_rpc_message(stream: BinaryIO) -> Optional[Dict[str, Any]]:
    """Read either newline-delimited JSON-RPC (MCP 2024-11-05+) or Content-Length framed JSON-RPC."""
    while True:
        line = stream.readline()
        if not line:
            return None
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith(b"content-length:"):
            length = int(stripped.split(b":", 1)[1].strip())
            while True:
                hdr = stream.readline()
                if not hdr or hdr in (b"\r\n", b"\n"):
                    break
            body = stream.read(length)
            return json.loads(body.decode("utf-8"))
        return json.loads(stripped.decode("utf-8"))


def _write_rpc_message(stream: BinaryIO, payload: Dict[str, Any]) -> None:
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    stream.write(data)
    stream.flush()


def handle_rpc_request(msg: Dict[str, Any], default_ws: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Process a single JSON-RPC 2.0 message and return response dict (or None for notifications)."""
    method = str(msg.get("method") or "")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications carry no id and expect no response
    if req_id is None:
        return None

    try:
        if method == "initialize":
            global _CLIENT_ROOT
            folders = params.get("workspaceFolders") or []
            raw_uri = str((folders[0].get("uri") if folders and isinstance(folders[0], dict) else "") or params.get("rootUri") or "")
            if raw_uri.startswith("file://"):
                cand = Path(unquote(urlparse(raw_uri).path)).resolve()
                if cand.is_dir():
                    _CLIENT_ROOT = cand
                    set_active_workspace(cand)
            client_proto = str(params.get("protocolVersion") or "2024-11-05")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": client_proto,
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                    "serverInfo": {"name": "supermemory", "version": __version__},
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS}}

        if method == "tools/call":
            t_name = str(params.get("name") or "")
            t_args = dict(params.get("arguments") or {})
            eff_ws = default_ws or _CLIENT_ROOT
            if eff_ws and not t_args.get("workspace"):
                t_args["workspace"] = str(eff_ws)
            out = execute_mcp_tool(t_name, t_args)
            txt = json.dumps(out, ensure_ascii=False, indent=2)
            if len(txt) > 3200:
                txt = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": txt}],
                    "isError": False,
                },
            }

        if method == "resources/list":
            resources = [
                {"uri": "supermemory://active_state", "name": "Active Project State", "mimeType": "text/markdown"},
                {"uri": "supermemory://constitution", "name": "Anti-Regression Constitution", "mimeType": "text/markdown"},
                {"uri": "supermemory://experiments", "name": "Scientific Experiments Registry", "mimeType": "text/markdown"},
                {"uri": "supermemory://memory_graph", "name": "Master Memory Graph", "mimeType": "text/markdown"},
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": resources}}

        if method == "resources/read":
            uri = str(params.get("uri") or "")
            ws = default_ws or _CLIENT_ROOT or resolve_default_workspace()
            mapping = {
                "supermemory://active_state": ws / "memory" / "01_ACTIVE_STATE.md",
                "supermemory://constitution": ws / "memory" / "02_CONSTITUTION_AND_LESSONS.md",
                "supermemory://experiments": ws / "memory" / "03_EXPERIMENTS_REGISTRY.md",
                "supermemory://memory_graph": ws / "memory" / "00_MEMORY_GRAPH.md",
            }
            target = mapping.get(uri)
            text = target.read_text(encoding="utf-8") if (target and target.is_file()) else f"Resource not initialized: {uri}"
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]},
            }

        if method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "prompts": [
                        {
                            "name": "supermemory-boot",
                            "description": "Load SuperMemory Constitution, Active State, and Anti-Repeat Recall.",
                        }
                    ]
                },
            }

        if method == "prompts/get":
            ws = default_ws or Path.cwd()
            out = execute_mcp_tool("status", {"workspace": str(ws)})
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": "SuperMemory Active Capsule",
                    "messages": [{"role": "user", "content": {"type": "text", "text": out["capsule"]}}],
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    except Exception as exc:
        if method == "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"SuperMemory Error: {exc}"}],
                    "isError": True,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def run_mcp_stdio_server(default_ws: Optional[Path] = None) -> int:
    """Main loop reading JSON-RPC over stdin.buffer and writing responses to stdout.buffer."""
    in_buf = sys.stdin.buffer
    out_buf = sys.stdout.buffer
    while True:
        msg = _read_rpc_message(in_buf)
        if msg is None:
            break
        resp = handle_rpc_request(msg, default_ws=default_ws)
        if resp is not None:
            _write_rpc_message(out_buf, resp)
    return 0
