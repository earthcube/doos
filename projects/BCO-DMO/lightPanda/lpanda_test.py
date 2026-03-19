"""
Simple Python CDP client for Lightpanda browser.
Requires Lightpanda running: ./lightpanda serve --host 127.0.0.1 --port 9222

https://github.com/lightpanda-io/browser
"""

import asyncio
import json
import httpx
import websockets


CDP_HTTP = "http://0.0.0.0:9222"
CDP_WS   = "ws://0.0.0.0:9222"

# How long to wait after the load event for JS/XHR to settle (seconds)
SETTLE_TIMEOUT = 5


class CDPClient:
    """Minimal Chrome DevTools Protocol client for Lightpanda."""

    def __init__(self, ws_url: str):
        self._ws_url = ws_url
        self._ws = None
        self._id = 0
        self._events: list[dict] = []
        self._inflight: set[str] = set()
        self._last_idle: float = 0.0

    async def connect(self):
        self._ws = await websockets.connect(self._ws_url)
        print(f"[CDP] Connected to {self._ws_url}")

    async def close(self):
        if self._ws:
            await self._ws.close()
            print("[CDP] Connection closed")

    def _handle_network_event(self, method: str, params: dict) -> None:
        """Update in-flight request tracking from network events."""
        rid = params.get("requestId")
        if not rid:
            return
        if method == "Network.requestWillBeSent":
            self._inflight.add(rid)
        elif method in ("Network.loadingFinished", "Network.loadingFailed",
                        "Network.responseReceived"):
            self._inflight.discard(rid)
            if not self._inflight:
                self._last_idle = asyncio.get_event_loop().time()

    async def send(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and return the response, buffering any events."""
        self._id += 1
        msg_id = self._id
        msg = {"id": msg_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(msg))

        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error on '{method}': {data['error']}")
                return data.get("result", {})
            if "method" in data:
                self._handle_network_event(data["method"], data.get("params", {}))
                self._events.append(data)

    async def wait_for_event(self, event_method: str, timeout: float = 30.0) -> dict:
        """Wait for a specific CDP event to arrive."""
        for i, ev in enumerate(self._events):
            if ev.get("method") == event_method:
                self._events.pop(i)
                return ev.get("params", {})

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {event_method}")
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Timed out waiting for {event_method}")
            data = json.loads(raw)
            if "method" in data:
                self._handle_network_event(data["method"], data.get("params", {}))
            if data.get("method") == event_method:
                return data.get("params", {})
            self._events.append(data)

    async def wait_for_network_idle(
        self, idle_duration: float = 0.5, timeout: float = 30.0
    ) -> None:
        """
        Wait until no in-flight requests for `idle_duration` seconds (like networkidle0).
        """
        deadline = asyncio.get_event_loop().time() + timeout
        self._last_idle = asyncio.get_event_loop().time()

        while True:
            now = asyncio.get_event_loop().time()
            if now > deadline:
                print("[warn] wait_for_network_idle timed out")
                return
            if not self._inflight:
                if now - self._last_idle >= idle_duration:
                    return
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=0.1)
                data = json.loads(raw)
                if "method" in data:
                    self._handle_network_event(data["method"], data.get("params", {}))
                    self._events.append(data)
            except asyncio.TimeoutError:
                pass

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.close()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_ws_endpoint() -> str:
    try:
        resp = httpx.get(f"{CDP_HTTP}/json/version", timeout=3)
        resp.raise_for_status()
        return resp.json().get("webSocketDebuggerUrl", CDP_WS)
    except Exception as exc:
        print(f"[warn] Could not reach /json/version ({exc}), using default: {CDP_WS}")
        return CDP_WS


async def navigate_and_extract(url: str) -> dict:
    ws_url = get_ws_endpoint()

    async with CDPClient(ws_url) as cdp:
        # Create a new blank target FIRST (before enabling any domains)
        target = await cdp.send("Target.createTarget", {"url": "about:blank"})
        target_id = target["targetId"]
        print(f"[CDP] Created target: {target_id}")

        # Attach to it
        session = await cdp.send("Target.attachToTarget",
                                  {"targetId": target_id, "flatten": True})
        session_id = session.get("sessionId")
        print(f"[CDP] Session: {session_id}")

        # NOW enable Page and Network domains — we have a context to enable them in
        await cdp.send("Page.enable")
        await cdp.send("Network.enable")

        # Navigate
        print(f"[CDP] Navigating to {url} …")
        await cdp.send("Page.navigate", {"url": url})

        # ── Wait strategy ──────────────────────────────────────────────────
        # 1. Wait for the browser's load event
        print("[CDP] Waiting for Page.loadEventFired …")
        try:
            await cdp.wait_for_event("Page.loadEventFired", timeout=30)
            print("[CDP] Load event fired.")
        except TimeoutError:
            print("[warn] Page.loadEventFired timed out — continuing anyway")

        # 2. Wait for network to go idle (no requests for 500ms) — like networkidle0
        print("[CDP] Waiting for network idle …")
        await cdp.wait_for_network_idle(idle_duration=0.5, timeout=15.0)
        print("[CDP] Network idle.")
        # ──────────────────────────────────────────────────────────────────

        # Get document root
        doc = await cdp.send("DOM.getDocument", {"depth": 1})
        root_node_id = doc["root"]["nodeId"]

        # Full page HTML via DOM.getOuterHTML on root
        html_result = await cdp.send("DOM.getOuterHTML", {"nodeId": root_node_id})
        html_content = html_result.get("outerHTML", "")

        # Title via querySelector
        title_result = await cdp.send("DOM.querySelector",
                                       {"nodeId": root_node_id, "selector": "title"})
        title_text = ""
        if title_node_id := title_result.get("nodeId"):
            title_node = await cdp.send("DOM.getOuterHTML", {"nodeId": title_node_id})
            title_text = (
                title_node.get("outerHTML", "")
                .replace("<title>", "").replace("</title>", "").strip()
            )

        # Current URL
        url_result = await cdp.send("Runtime.evaluate",
                                     {"expression": "window.location.href"})
        current_url = url_result.get("result", {}).get("value", "")

        return {
            "url": current_url,
            "title": title_text,
            "html": html_content,
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    target_url = "https://www.bco-dmo.org/doi/dataset/10.26008/1912/bco-dmo.990510.1"
    print(f"\n=== Lightpanda CDP client — fetching {target_url} ===\n")

    try:
        info = await navigate_and_extract(target_url)
        print("\n--- Result ---")
        print(f"  URL   : {info['url']}")
        print(f"  Title : {info['title']}")
        print(f"  HTML length: {len(info['html'])} chars")
        print("\n--- HTML Content ---")
        print(info["html"])
    except Exception as exc:
        print(f"[ERROR] {exc}")
        print(
            "\nMake sure Lightpanda is running:\n"
            "  ./lightpanda serve --host 127.0.0.1 --port 9222"
        )


if __name__ == "__main__":
    asyncio.run(main())