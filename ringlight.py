# ringlight.py — REST API ring light control over mDNS
#
# Responsibilities:
#   - Send HTTP GET commands to the ESP32 ring light
#   - Resolve it by mDNS hostname (photobooth-light.local)
#   - Expose on() / off() / flash() / blink(n) to main.py
#
# ESP32 REST endpoints:
#   GET /on          → solid white
#   GET /off         → all LEDs off
#   GET /flash       → bright burst then auto-off
#   GET /blink?n=3   → blink N times
#   GET /status      → {"state":"on"|"off", "ip":"...", "hostname":"..."}

import requests
import config


class RingLight:
    """
    Ring light controller via HTTP REST + mDNS.

    Usage (from main.py):
        light = RingLight()
        light.connect()   # checks reachability, non-fatal if offline
        light.on()
        light.flash()
        light.off()
    """

    def __init__(self):
        self._base   = config.RINGLIGHT_BASE_URL.rstrip("/")
        self._online = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self):
        """
        Probe the ring light so we know early if it's reachable.
        If it's offline the booth still runs — commands silently no-op.
        """
        try:
            r = self._get("/status", timeout=3)
            if r and r.status_code == 200:
                info = r.json()
                self._online = True
                print(f"[RingLight] Online — {self._base}")
                print(f"[RingLight] Device IP : {info.get('ip', '?')}")
                print(f"[RingLight] Hostname  : {info.get('hostname', '?')}")
            else:
                self._warn()
        except Exception as e:
            print(f"[RingLight] WARNING: {e}")
            self._warn()

    def disconnect(self):
        """Turn off LEDs on exit."""
        self.off()

    # ── Commands ──────────────────────────────────────────────────────────────

    def on(self):
        """Solid white — illuminate for countdown."""
        self._send("/on")
        print("[RingLight] ON")

    def off(self):
        """All LEDs off."""
        self._send("/off")
        print("[RingLight] OFF")

    def flash(self):
        """
        Single bright burst — ESP32 handles timing (300 ms) then self-extinguishes.
        No need to call off() after this.
        """
        self._send("/flash")
        print("[RingLight] FLASH")

    def blink(self, times: int = 3):
        """Blink N times (useful for countdown ticks if desired)."""
        self._send(f"/blink?n={times}")
        print(f"[RingLight] BLINK x{times}")

    def status(self) -> dict:
        """Return raw status dict from ESP32, or empty dict if offline."""
        try:
            r = self._get("/status", timeout=2)
            if r and r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _send(self, path: str):
        """Fire-and-forget GET; silently skips if device is offline."""
        if not self._online:
            return
        try:
            self._get(path, timeout=2)
        except Exception as e:
            print(f"[RingLight] Command failed ({path}): {e}")

    def _get(self, path: str, timeout: int = 2):
        return requests.get(self._base + path, timeout=timeout)

    def _warn(self):
        self._online = False
        print("[RingLight] Device unreachable — booth will run without ring light.")
        print(f"[RingLight] Expected at: {self._base}")
