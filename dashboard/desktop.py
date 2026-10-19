"""Run the Regalia dashboard as a native desktop window.

This wraps the EXACT Flask app from app.py in an OS webview (EdgeWebView2 /
Chromium on Windows) instead of a browser tab. Nothing about the web stack
changes, so anything served by Flask — today's task dashboard, and the future
web-search / agent views — renders here identically. The only desktop-specific
behavior added is that external (http/https) links open in the real system
browser rather than getting trapped inside the app window, which is exactly
what web-search result links will need.

Run:  python desktop.py   (or double-click desktop.bat)
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen


def _run_frozen_mail_mcp_entrypoint() -> None:
    """Run the bundled mailbox MCP server when this executable is its launcher."""
    if not (getattr(sys, "frozen", False) and sys.argv[1:] == ["--mail-mcp"]):
        return

    # Imported only in MCP mode so a normal desktop launch does not initialize
    # the server or its optional SDK. PyInstaller includes it as a hidden import.
    from mail_mcp import mcp

    mcp.run()
    raise SystemExit(0)


_run_frozen_mail_mcp_entrypoint()

try:
    import webview  # pywebview
except ImportError:  # pragma: no cover - guidance path
    raise SystemExit(
        "pywebview isn't installed. Run `pip install -r requirements.txt` "
        "(or `pip install pywebview`) and try again.\n"
        "You can still use the browser version any time with `python app.py`."
    )

# `app` is imported inside _serve(), not here: importing it (Flask, the router,
# every backend module) takes seconds — longer from a onefile exe — and doing it
# up front kept the window from appearing at all until it finished. Now the
# window opens at once on _SPLASH_HTML and switches to the app when it's up.

HOST = "127.0.0.1"
WINDOW_TITLE = "Regalia"

# Injected after the page loads: route external links to the system browser via
# the exposed js_api, keeping in-window navigation for localhost. Future
# web-search results (and the markdown links in twin chat) flow through here.
_INTERCEPT_JS = r"""
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a[href]');
  if (!a) return;
  var href = a.getAttribute('href') || '';
  var external = /^https?:\/\//i.test(href) && !href.startsWith(location.origin);
  if (external && window.pywebview && window.pywebview.api) {
    e.preventDefault();
    window.pywebview.api.open_external(href);
  }
}, true);
"""


class _Api:
    """Bridge exposed to the page as window.pywebview.api."""

    def open_external(self, url: str) -> None:
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            webbrowser.open(url)


def _allow_local_microphone(window, origin: str) -> None:
    """Grant mic access to Regalia's own page, silently, for the voice agent.

    pywebview runs WebView2 in private mode, so a granted permission is never
    remembered: without this, hands-free listening would raise a permission
    prompt on every launch (including the unattended one at sign-in). Only
    the microphone, and only for our localhost origin — every other request
    falls through to WebView2's normal prompt. Best-effort: on a non-WebView2
    backend (macOS WKWebView, GTK) the page's own prompt still works.
    """
    try:
        from Microsoft.Web.WebView2.Core import (  # type: ignore
            CoreWebView2PermissionKind, CoreWebView2PermissionState,
        )
        from System import Action  # type: ignore
        native = window.native
        core_host = native.browser.webview
    except Exception:
        return

    def on_request(_sender, args):
        if (args.PermissionKind == CoreWebView2PermissionKind.Microphone
                and str(args.Uri).startswith(origin)):
            args.State = CoreWebView2PermissionState.Allow

    def attach():
        core_host.CoreWebView2.PermissionRequested += on_request

    # CoreWebView2 is UI-thread-affine; `loaded` fires on a worker thread.
    native.Invoke(Action(attach))
    window._regalia_mic_handler = on_request  # keep the delegate alive


def _free_port() -> int:
    """Grab an OS-assigned free port so two instances never collide."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


_SPLASH_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
  html, body { margin: 0; height: 100%%; background: %(bg)s; color: %(text)s;
    font-family: Inter, "Segoe UI", system-ui, sans-serif; }
  body { display: flex; align-items: center; justify-content: center; }
  .t { font-size: 40px; letter-spacing: -0.03em; }
  .t span { color: %(accent)s; }
  .s { margin-top: 10px; font: 11px ui-monospace, Consolas, monospace; color: %(faint)s;
    text-transform: uppercase; }
</style></head><body><div><div class="t">Regalia<span>.</span></div>
<div class="s">%(status)s</div></div></body></html>"""


def _splash_html(status: str = "Starting…") -> str:
    """The native first frame, shown before Flask exists. Matches the saved
    theme so the hand-off to the page's own loading screen doesn't flash."""
    try:
        import config  # light: stdlib + paths only
        cfg = config.load()
    except Exception:
        cfg = {}
    light = cfg.get("theme") == "light"
    return _SPLASH_HTML % {
        "bg": "#f6f5f2" if light else "#101010",
        "text": "#1a1a1a" if light else "#f3f3f3",
        "faint": "#8a8478" if light else "#6e6e6e",
        "accent": cfg.get("accent") or ("#a06a24" if light else "#e7c59a"),
        "status": status,
    }


_server_error: list[str] = []


def _serve(port: int) -> None:
    try:
        from app import app
    except Exception as e:  # surfaced in the window instead of a silent hang
        _server_error.append(f"{type(e).__name__}: {e}")
        return
    # use_reloader=False: the reloader forks a second process, which would open
    # a duplicate window and orphan this server thread. threaded=True so API
    # calls the page makes don't block each other.
    app.run(host=HOST, port=port, debug=False, use_reloader=False, threaded=True)


def _boot(window, port: int, url: str) -> None:
    """Runs once the GUI is up: start the server, then hand the window over."""
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    if _wait_until_up(url, timeout=90.0):
        window.load_url(url)
    else:
        detail = _server_error[0] if _server_error else "the server didn't start in time"
        window.load_html(_splash_html(f"Couldn't start — {detail}"))


def _wait_until_up(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_error:
            return False
        try:
            urlopen(url, timeout=1)
            return True
        except (URLError, OSError):
            time.sleep(0.1)
    return False


def main() -> None:
    # Chromium won't let a page speak (speechSynthesis) or start audio until the
    # user has clicked it. The voice agent answers hands-free — often right after
    # an unattended launch at sign-in — so lift that gate for this window only.
    # The env var *replaces* the creation-properties args pywebview sets, so its
    # own ElasticOverscroll flag is restated here to keep that behavior.
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--disable-features=ElasticOverscroll --autoplay-policy=no-user-gesture-required",
    )
    port = _free_port()
    url = f"http://{HOST}:{port}"

    window = webview.create_window(
        WINDOW_TITLE,
        html=_splash_html(),
        width=1280,
        height=860,
        min_size=(900, 600),
        text_select=True,
        js_api=_Api(),
    )
    assert window is not None, "Failed to create webview window"
    mic_granted = []

    def on_loaded():
        if not mic_granted:
            mic_granted.append(True)
            _allow_local_microphone(window, url)
        window.evaluate_js(_INTERCEPT_JS)

    window.events.loaded += on_loaded
    webview.start(_boot, (window, port, url))


if __name__ == "__main__":
    main()
