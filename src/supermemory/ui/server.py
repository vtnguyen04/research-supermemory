"""Stdlib HTTP JSON API + SPA Server for the SuperMemory Interactive Management Console."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from supermemory.cognitive.federation import (
    ensure_global_memory,
    federated_recall,
    list_registered_workspaces,
)
from supermemory.cognitive.tiers import classify_tier, compute_tier_telemetry
from supermemory.graph.query_engine import QueryEngine
from supermemory.storage.sqlite_store import GraphStore
from supermemory.ui.api_actions import dispatch_store_mutation, handle_workspace_action
from supermemory.ui.api_research import enrich_graph_payload_v3

STATIC_DIR = Path(__file__).resolve().parent / "static"

_MIME_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


def _resolve_scope_workspace(default_ws: Path, scope_param: str) -> Path:
    clean = (scope_param or "").strip()
    if not clean or clean == "local":
        return default_ws
    if clean == "global":
        return ensure_global_memory()
    cand = Path(clean).expanduser().resolve()
    if cand.is_dir() and ((cand / ".supermemory").is_dir() or (cand / "memory" / "graph_snapshot.json").is_file()):
        return cand
    return default_ws


def build_graph_api_payload(workspace_root: Path) -> Dict[str, Any]:
    """Assemble full Tiered Knowledge Graph, Gates, Experiments, Analytics & Workspaces."""
    with GraphStore(workspace_root) as store:
        qe = QueryEngine(store)
        nodes = []
        for n in store.list_nodes(limit=5000):
            d = n.to_dict()
            d["memory_tier"] = classify_tier(n)
            nodes.append(d)
        edges = [e.to_dict() for e in store.list_edges()]
        gates = [g.to_dict() for g in store.list_gates()]
        experiments = [x.to_dict() for x in store.list_experiments()]
        events = store.list_events(limit=100)
        analytics = qe.graph_analytics()
        tiers = compute_tier_telemetry(store)
        meta = store.get_all_meta()
        payload = {
            "workspace_path": str(workspace_root),
            "is_global": workspace_root == ensure_global_memory(),
            "project": meta.get("project_name") or workspace_root.name,
            "meta": meta,
            "analytics": analytics,
            "cognitive_tiers": tiers,
            "workspaces": list_registered_workspaces(),
            "nodes": nodes,
            "edges": edges,
            "gates": gates,
            "experiments": experiments,
            "events": events,
        }
        return enrich_graph_payload_v3(store, payload)


def _make_handler(default_ws: Path) -> type[BaseHTTPRequestHandler]:
    class GraphRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            qs = parse_qs(parsed.query)
            scope = (qs.get("scope") or ["local"])[0]
            ws = _resolve_scope_workspace(default_ws, scope)

            if route == "/api/workspaces":
                self._send_json({"default_workspace": str(default_ws), "workspaces": list_registered_workspaces()})
                return

            if route == "/api/graph":
                self._send_json(build_graph_api_payload(ws))
                return

            if route == "/api/search":
                q = (qs.get("q") or [""])[0]
                if not q.strip():
                    self._send_json({"results": [], "anti_repeat_warnings": []})
                    return
                inc_sib = (qs.get("siblings") or ["0"])[0] in ("1", "true", "yes")
                res = federated_recall(q, local_ws=ws, include_global=True, include_siblings=inc_sib, limit=15, hops=1)
                self._send_json(res)
                return

            if route.startswith("/api/node/"):
                nid = unquote(route.removeprefix("/api/node/"))
                with GraphStore(ws) as store:
                    node = store.get_node(nid)
                    edges = [e.to_dict() for e in store.list_edges(nid)] if node else []
                if not node:
                    self._send_json({"error": f"Node not found: {nid}"}, status=HTTPStatus.NOT_FOUND)
                    return
                nd = node.to_dict()
                nd["memory_tier"] = classify_tier(node)
                self._send_json({"node": nd, "edges": edges})
                return

            rel_static = "index.html" if route in ("/", "/index.html") else route.lstrip("/")
            target = (STATIC_DIR / rel_static).resolve()
            if not target.is_relative_to(STATIC_DIR) or not target.is_file():
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
            mime = _MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

            try:
                if route == "/api/workspaces/init":
                    self._send_json(handle_workspace_action(body))
                    return
                ws = _resolve_scope_workspace(default_ws, str(body.get("scope") or "local"))
                with GraphStore(ws) as store:
                    result = dispatch_store_mutation(route, store, body)
                if result is not None:
                    self._send_json(result)
                    return
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            self._send_json({"error": f"Unknown route: {route}"}, status=HTTPStatus.NOT_FOUND)

        def _send_json(self, obj: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    return GraphRequestHandler


def create_http_server(workspace_root: Path, host: str = "127.0.0.1", port: int = 8765) -> Tuple[ThreadingHTTPServer, int]:
    """Bind ThreadingHTTPServer (supports port=0 for ephemeral test ports)."""
    srv = ThreadingHTTPServer((host, port), _make_handler(workspace_root.resolve()))
    actual_port = int(srv.server_address[1])
    return srv, actual_port


def run_ui_server(workspace_root: Path, host: str = "127.0.0.1", port: int = 8765) -> int:
    """Start blocking SuperMemory Constitutional Graph Workbench server."""
    srv, actual_port = create_http_server(workspace_root, host=host, port=port)
    print(f"[SuperMemory v3.0.3] Daylight Architectural Research Studio live at: http://{host}:{actual_port}")
    print(f"   Default Workspace: {workspace_root.resolve()}")
    print("   Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
