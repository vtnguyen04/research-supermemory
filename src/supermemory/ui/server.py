"""Lightweight stdlib HTTP JSON API + SPA Server for the SuperMemory Graph Observatory."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from supermemory.graph.query_engine import QueryEngine
from supermemory.storage.sqlite_store import GraphStore

STATIC_DIR = Path(__file__).resolve().parent / "static"

_MIME_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}


def build_graph_api_payload(workspace_root: Path) -> Dict[str, Any]:
    """Assemble full Knowledge Graph, Gates, Experiments, Analytics, and Event Stream JSON."""
    with GraphStore(workspace_root) as store:
        qe = QueryEngine(store)
        nodes = [n.to_dict() for n in store.list_nodes(limit=5000)]
        edges = [e.to_dict() for e in store.list_edges()]
        gates = [g.to_dict() for g in store.list_gates()]
        experiments = [x.to_dict() for x in store.list_experiments()]
        events = store.list_events(limit=100)
        analytics = qe.graph_analytics()
        meta = store.get_all_meta()
    return {
        "project": meta.get("project_name") or workspace_root.name,
        "meta": meta,
        "analytics": analytics,
        "nodes": nodes,
        "edges": edges,
        "gates": gates,
        "experiments": experiments,
        "events": events,
    }


def _make_handler(workspace_root: Path) -> type[BaseHTTPRequestHandler]:
    class GraphRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            qs = parse_qs(parsed.query)

            if route == "/api/graph":
                self._send_json(build_graph_api_payload(workspace_root))
                return

            if route == "/api/search":
                q = (qs.get("q") or [""])[0]
                with GraphStore(workspace_root) as store:
                    res = QueryEngine(store).recall(q, limit=15, hops=1) if q.strip() else {"results": [], "anti_repeat_warnings": []}
                self._send_json(res)
                return

            if route.startswith("/api/node/"):
                nid = unquote(route.removeprefix("/api/node/"))
                with GraphStore(workspace_root) as store:
                    node = store.get_node(nid)
                    edges = [e.to_dict() for e in store.list_edges(nid)] if node else []
                if not node:
                    self._send_json({"error": f"Node not found: {nid}"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._send_json({"node": node.to_dict(), "edges": edges})
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
    """Start blocking Graph Observatory Web UI server."""
    srv, actual_port = create_http_server(workspace_root, host=host, port=port)
    print(f"🧠 SuperMemory Graph Observatory live at: http://{host}:{actual_port}")
    print(f"   Workspace: {workspace_root.resolve()}")
    print("   Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
