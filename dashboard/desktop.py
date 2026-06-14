"""Run the Work Vault dashboard as a native desktop window.

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

import socket
import threading
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

try:
    import webview  # pywebview
except ImportError:  # pragma: no cover - guidance path
    raise SystemExit(
        "pywebview isn't installed. Run `pip install -r requirements.txt` "
        "(or `pip install pywebview`) and try again.\n"
        "You can still use the browser version any time with `python app.py`."
    )

from app import app

HOST = "127.0.0.1"
WINDOW_TITLE = "Work Vault"

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


def _free_port() -> int:
    """Grab an OS-assigned free port so two instances never collide."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _serve(port: int) -> None:
    # use_reloader=False: the reloader forks a second process, which would open
    # a duplicate window and orphan this server thread. threaded=True so API
    # calls the page makes don't block each other.
    app.run(host=HOST, port=port, debug=False, use_reloader=False, threaded=True)


def _wait_until_up(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(url, timeout=1)
            return True
        except (URLError, OSError):
            time.sleep(0.1)
    return False


def main() -> None:
    port = _free_port()
    url = f"http://{HOST}:{port}"

    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    if not _wait_until_up(url):
        raise SystemExit(f"Dashboard server didn't come up at {url} in time.")

    window = webview.create_window(
        WINDOW_TITLE,
        url,
        width=1280,
        height=860,
        min_size=(900, 600),
        text_select=True,
        js_api=_Api(),
    )
    window.events.loaded += lambda: window.evaluate_js(_INTERCEPT_JS)
    webview.start()


if __name__ == "__main__":
    main()
