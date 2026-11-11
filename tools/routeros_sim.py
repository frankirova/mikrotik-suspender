#!/usr/bin/env python3
"""Minimal RouterOS API simulator for demos and local testing.

Speaks the RouterOS binary API (v6.43+ plaintext login) on one port and serves a
read-only HTML/plain-text console on another, so a demo can show the same
address-list the application actually wrote.

Only the subset the suspension tool uses is implemented:
    POST /login
    /ip/firewall/address-list/print|add|set|remove

Everything lives in memory: restarting the simulator resets the router.
"""

from __future__ import annotations

import argparse
import html
import socket
import socketserver
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# ── RouterOS word encoding ───────────────────────────────────────────


def encode_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    if length < 0x4000:
        return bytes([0x80 | (length >> 8), length & 0xFF])
    if length < 0x200000:
        return bytes([0xC0 | (length >> 16), (length >> 8) & 0xFF, length & 0xFF])
    if length < 0x10000000:
        return bytes(
            [0xE0 | (length >> 24), (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF]
        )
    return bytes(
        [
            0xF0,
            (length >> 24) & 0xFF,
            (length >> 16) & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
    )


def encode_word(word: str) -> bytes:
    raw = word.encode("utf-8")
    return encode_length(len(raw)) + raw


class Reader:
    """Incremental reader for length-prefixed words over a socket."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buf = b""

    def _fill(self, need: int) -> None:
        while len(self._buf) < need:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("client closed")
            self._buf += chunk

    def _read_length(self) -> int:
        self._fill(1)
        first = self._buf[0]
        self._buf = self._buf[1:]
        if first & 0x80 == 0:
            return first
        if first & 0xC0 == 0x80:
            extra = 1
            length = first & 0x3F
        elif first & 0xE0 == 0xC0:
            extra = 2
            length = first & 0x1F
        elif first & 0xF0 == 0xE0:
            extra = 3
            length = first & 0x0F
        elif first & 0xF8 == 0xF0:
            extra = 4
            length = 0
        else:
            raise ValueError(f"bad length prefix {first:#x}")
        self._fill(extra)
        for _ in range(extra):
            length = (length << 8) | self._buf[0]
            self._buf = self._buf[1:]
        return length

    def read_sentence(self) -> list[str] | None:
        words: list[str] = []
        while True:
            try:
                length = self._read_length()
            except ConnectionError:
                return None if not words else words
            if length == 0:
                return words
            self._fill(length)
            raw = self._buf[:length]
            self._buf = self._buf[length:]
            words.append(raw.decode("utf-8", "replace"))


# ── Router state ─────────────────────────────────────────────────────


@dataclass
class AddressListEntry:
    id: str
    address: str
    list_name: str
    comment: str = ""
    disabled: str = "true"


@dataclass
class RouterState:
    entries: list[AddressListEntry] = field(default_factory=list)
    next_id: int = 1
    lock: threading.RLock = field(default_factory=threading.RLock)
    events: list[str] = field(default_factory=list)

    def new_id(self) -> str:
        value = f"*{self.next_id:X}"
        self.next_id += 1
        return value


STATE = RouterState()


def log_event(message: str) -> None:
    with STATE.lock:
        STATE.events.append(message)
        STATE.events = STATE.events[-200:]
    print(f"[sim] {message}", flush=True)


# ── API handler ──────────────────────────────────────────────────────


def parse_words(words: list[str]) -> tuple[str, dict[str, str], list[str]]:
    """Split a sentence into command, attributes and queries (tolerant)."""
    command = ""
    attributes: dict[str, str] = {}
    queries: list[str] = []
    for word in words:
        if word.startswith("/"):
            command = word
        elif word.startswith("=") and word.count("=") >= 2:
            body = word[1:]
            if body.startswith(".proplist"):
                continue
            key, _, value = body.partition("=")
            attributes[key] = value
        elif word.startswith("?") and word.count("=") >= 2:
            body = word[1:]
            key, _, value = body.partition("=")
            attributes[key] = value
            queries.append(key)
        elif word.startswith(".tag="):
            attributes[".tag"] = word[len(".tag=") :]
    return command, attributes, queries


class ApiHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        sock: socket.socket = self.request
        sock.settimeout(300)
        reader = Reader(sock)
        logged_in = False
        try:
            while True:
                words = reader.read_sentence()
                if words is None:
                    return
                if not words:
                    continue
                command, attributes, _queries = parse_words(words)
                tag = attributes.pop(".tag", None)
                log_event(f"{command} {attributes if attributes else ''}".strip())
                if command in ("/login", "/login/") or not command:
                    logged_in = True
                    self._send(sock, [{"reply": "done"}], tag)
                    continue
                if not logged_in:
                    self._send(
                        sock,
                        [{"reply": "trap", "message": "not logged in"}, {"reply": "done"}],
                        tag,
                    )
                    continue
                self._dispatch(sock, command, attributes, tag)
        except (ConnectionError, socket.timeout, ValueError) as exc:
            log_event(f"connection closed: {exc}")

    def _dispatch(
        self, sock: socket.socket, command: str, attrs: dict[str, str], tag: str | None
    ) -> None:
        action = command.rstrip("/").split("/")[-1]
        if command.startswith("/ip/firewall/address-list"):
            if action == "print":
                with STATE.lock:
                    wanted = attrs.get("list")
                    rows = [
                        e for e in STATE.entries if wanted is None or e.list_name == wanted
                    ]
                    payload = [
                        {
                            "reply": "re",
                            "id": e.id,
                            "address": e.address,
                            "list": e.list_name,
                            "comment": e.comment,
                            "disabled": e.disabled,
                        }
                        for e in rows
                    ]
                self._send(sock, payload + [{"reply": "done"}], tag)
                return
            if action == "add":
                with STATE.lock:
                    entry = AddressListEntry(
                        id=STATE.new_id(),
                        address=attrs.get("address", ""),
                        list_name=attrs.get("list", ""),
                        comment=attrs.get("comment", ""),
                        disabled=attrs.get("disabled", "true"),
                    )
                    STATE.entries.append(entry)
                    log_event(f"address-list add {entry.address} list={entry.list_name} id={entry.id}")
                self._send(sock, [{"reply": "done", "ret": entry.id}], tag)
                return
            if action == "set":
                target = attrs.get("id") or attrs.get(".id") or ""
                with STATE.lock:
                    for entry in STATE.entries:
                        if entry.id == target:
                            if "comment" in attrs:
                                entry.comment = attrs["comment"]
                            if "disabled" in attrs:
                                entry.disabled = attrs["disabled"]
                            log_event(f"address-list set {entry.id} {attrs}")
                            break
                    else:
                        self._send(
                            sock,
                            [
                                {"reply": "trap", "message": f"no such item: {target}"},
                                {"reply": "done"},
                            ],
                            tag,
                        )
                        return
                self._send(sock, [{"reply": "done"}], tag)
                return
            if action in ("remove", "delete"):
                target = attrs.get("id") or attrs.get(".id") or ""
                with STATE.lock:
                    STATE.entries = [e for e in STATE.entries if e.id != target]
                self._send(sock, [{"reply": "done"}], tag)
                return
        self._send(
            sock,
            [{"reply": "trap", "message": f"no such command: {command}"}, {"reply": "done"}],
            tag,
        )

    @staticmethod
    def _send(sock: socket.socket, replies: list[dict[str, str]], tag: str | None = None) -> None:
        out = b""
        for reply in replies:
            kind = reply.pop("reply")
            out += encode_word(f"!{kind}")
            if kind == "re":
                for key, value in reply.items():
                    out += encode_word(f"={key}={value}")
            elif kind == "done" and "ret" in reply:
                out += encode_word(f"=ret={reply['ret']}")
            elif kind == "trap" and "message" in reply:
                out += encode_word(f"=message={reply['message']}")
            if tag is not None:
                out += encode_word(f".tag={tag}")
            out += encode_word("")
        sock.sendall(out)


class ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ── Console views ────────────────────────────────────────────────────


def render_print() -> str:
    with STATE.lock:
        rows = list(STATE.entries)
    if not rows:
        return "(address-list 'suspendido' vacío)\n"
    lines = []
    for entry in rows:
        state = "disabled=yes" if entry.disabled == "true" else "disabled=no"
        lines.append(f'{entry.id:<5} {entry.address:<15} list={entry.list_name:<12} {state}  {entry.comment}')
    return "\n".join(lines) + "\n"


def render_console_html() -> str:
    with STATE.lock:
        rows = [
            {
                "id": e.id,
                "address": e.address,
                "list": e.list_name,
                "comment": e.comment,
                "disabled": e.disabled,
            }
            for e in STATE.entries
        ]
        events = list(STATE.events[-9:])
    suspended = sum(1 for e in rows if e["disabled"] == "false")
    body_rows = "".join(
        f"<tr class=\"{'on' if e['disabled'] == 'false' else 'off'}\">"
        f"<td>{html.escape(e['id'])}</td>"
        f"<td>{html.escape(e['address'])}</td>"
        f"<td>{html.escape(e['list'])}</td>"
        f"<td>{'no' if e['disabled'] == 'false' else 'yes'}</td>"
        f"<td>{html.escape(e['comment'])}</td></tr>"
        for e in rows
    )
    log_rows = "".join(f"<div class=\"log-line\">{html.escape(e)}</div>" for e in events)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>RouterOS simulado — address-list</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0b1020; color:#d7e0f4;
          font-family: ui-monospace, "JetBrains Mono", Menlo, monospace; }}
  header {{ padding:18px 28px; border-bottom:1px solid #1e2a44; display:flex;
            align-items:baseline; gap:14px; }}
  h1 {{ font-size:16px; margin:0; letter-spacing:.04em; text-transform:uppercase; }}
  .badge {{ font-size:11px; padding:3px 9px; border-radius:99px;
            background:#15233c; color:#7fd6a0; border:1px solid #24503a; }}
  .path {{ color:#7b8bb0; font-size:13px; }}
  main {{ padding:22px 28px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th {{ text-align:left; font-weight:600; color:#8fa2c8; font-size:12px;
        text-transform:uppercase; letter-spacing:.05em; padding:8px 12px;
        border-bottom:1px solid #1e2a44; }}
  td {{ padding:9px 12px; border-bottom:1px solid #141d33; }}
  tr.on td {{ color:#8ef0b0; }}
  tr.off td {{ color:#9aa8c4; }}
  tr.on td:nth-child(4)::after {{ content:" ⏻"; }}
  .summary {{ margin:18px 0 10px; font-size:14px; color:#a9b8d6; }}
  .summary b {{ color:#8ef0b0; }}
  .log {{ margin-top:26px; border-top:1px solid #1e2a44; padding-top:14px;
          font-size:12px; color:#6f7f9f; }}
  .log-line {{ padding:2px 0; white-space:pre-wrap; }}
  .log-line::before {{ content:"› "; color:#3f5a8a; }}
</style></head>
<body>
<header>
  <h1>RouterOS simulado</h1>
  <span class="badge">API :8728</span>
  <span class="path">/ip/firewall/address-list print list=suspendido</span>
</header>
<main>
  <table>
    <thead><tr><th>id</th><th>address</th><th>list</th><th>disabled</th><th>comment</th></tr></thead>
    <tbody>{body_rows or '<tr><td colspan="5">(vacío)</td></tr>'}</tbody>
  </table>
  <div class="summary">{len(rows)} entradas · <b>{suspended} suspendidas</b></div>
  <div class="log">{log_rows}</div>
</main>
<script>setTimeout(() => location.reload(), 700);</script>
</body></html>
"""


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = "RouterOSSim/1.0"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/print"):
            payload = render_print().encode()
            content_type = "text/plain; charset=utf-8"
        else:
            payload = render_console_html().encode()
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:  # silence per-request noise
        return


class ThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="RouterOS API simulator (demo only)")
    parser.add_argument("--api-port", type=int, default=8728)
    parser.add_argument("--console-port", type=int, default=8729)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    api = ThreadingTCPServer((args.host, args.api_port), ApiHandler)
    console = ThreadingHTTPServer((args.host, args.console_port), ConsoleHandler)
    threading.Thread(target=console.serve_forever, daemon=True).start()
    print(
        f"[sim] RouterOS API on {args.host}:{args.api_port} · console http://127.0.0.1:{args.console_port}",
        flush=True,
    )
    try:
        api.serve_forever()
    except KeyboardInterrupt:
        print("\n[sim] bye", flush=True)


if __name__ == "__main__":
    main()
