"""Localhost HTTP Security Guards: DNS Rebinding, Browser CSRF, Body Caps & Scope Allowlist."""

from __future__ import annotations

import io
import json
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from typing import Any, BinaryIO, Dict, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from supermemory.cognitive.federation import ensure_global_memory, list_registered_workspaces

MAX_POST_BYTES = 2 * 1024 * 1024

SECURITY_HEADERS: Tuple[Tuple[str, str], ...] = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "same-origin"),
    (
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
    ),
)


def validate_http_request(
    headers: Mapping[str, str] | Message[Any, Any],
    bound_host: str = "127.0.0.1",
    is_post: bool = False,
) -> Optional[Tuple[HTTPStatus, str]]:
    """Enforce loopback Host header (DNS rebinding guard) and browser CSRF checks on POST."""
    host_hdr = (headers.get("Host") or "").strip()
    if not host_hdr:
        return (HTTPStatus.FORBIDDEN, "Missing Host header (DNS rebinding guard).")
    try:
        parsed_host = urlsplit(f"//{host_hdr}")
        hostname = (parsed_host.hostname or "").lower()
    except ValueError:
        return (HTTPStatus.FORBIDDEN, "Malformed Host header.")

    allowed_hosts = {"127.0.0.1", "localhost", "::1"}
    clean_bound = bound_host.strip().strip("[]").lower()
    if clean_bound and clean_bound != "0.0.0.0":
        allowed_hosts.add(clean_bound)
    if hostname not in allowed_hosts:
        return (HTTPStatus.FORBIDDEN, f"Forbidden Host `{hostname}` (DNS rebinding guard).")

    if not is_post:
        return None

    sec_site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if sec_site in {"cross-site", "same-site"}:
        return (HTTPStatus.FORBIDDEN, f"Cross-origin POST blocked (`Sec-Fetch-Site: {sec_site}`).")

    origin = (headers.get("Origin") or "").strip()
    if origin:
        if origin.lower() == "null" or urlsplit(origin).netloc.lower() != host_hdr.lower():
            return (HTTPStatus.FORBIDDEN, "Cross-origin POST blocked (`Origin` mismatch).")
    else:
        referer = (headers.get("Referer") or "").strip()
        if referer and urlsplit(referer).netloc.lower() != host_hdr.lower():
            return (HTTPStatus.FORBIDDEN, "Cross-origin POST blocked (`Referer` mismatch).")

    ctype = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if ctype != "application/json":
        return (HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "POST Content-Type must be `application/json`.")

    return None


def read_json_body(
    rfile: io.BufferedIOBase | BinaryIO,
    headers: Mapping[str, str] | Message[Any, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[HTTPStatus, str]]]:
    """Safely read and parse a bounded UTF-8 JSON object body."""
    raw_len = (headers.get("Content-Length") or "").strip()
    if not raw_len:
        return ({}, None)
    try:
        length = int(raw_len)
    except ValueError:
        return (None, (HTTPStatus.BAD_REQUEST, "Invalid Content-Length header."))
    if length < 0:
        return (None, (HTTPStatus.BAD_REQUEST, "Negative Content-Length is invalid."))
    if length > MAX_POST_BYTES:
        return (None, (HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body exceeds 2MB limit."))
    if length == 0:
        return ({}, None)
    try:
        payload = json.loads(rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return (None, (HTTPStatus.BAD_REQUEST, "Malformed UTF-8 JSON payload."))
    if not isinstance(payload, dict):
        return (None, (HTTPStatus.BAD_REQUEST, "JSON request body must be an object."))
    return (payload, None)


def resolve_authorized_scope(default_ws: Path, scope_param: str) -> Path:
    """Resolve `scope` strictly within `default_ws`, `global`, or registered workspaces."""
    clean = (scope_param or "").strip()
    if not clean or clean == "local":
        return default_ws.resolve()
    g_root = ensure_global_memory().resolve()
    if clean == "global":
        return g_root
    cand = Path(clean).expanduser().resolve()
    allowed = {default_ws.resolve(), g_root}
    for item in list_registered_workspaces():
        raw_p = str(item.get("path") or "").strip()
        if raw_p:
            allowed.add(Path(raw_p).expanduser().resolve())
    if cand in allowed and cand.is_dir():
        return cand
    raise PermissionError(f"Unauthorized or unregistered workspace scope: `{clean}`")
