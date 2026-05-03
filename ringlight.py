# ringlight.py — REST API ring light control over mDNS
#
# Responsibilities:
#   - Send HTTP GET commands to the ESP32 ring light
#   - Resolve it by mDNS hostname (photobooth-light.local)
#   - Expose on() / off() / flash() / blink(n) / beep(n) to main.py
#
# ESP32 REST endpoints:
#   GET /on          → solid white + 1 beep
#   GET /off         → all LEDs off
#   GET /flash       → bright burst then auto-off
#   GET /blink?n=3   → blink N times
#   GET /beep?n=1    → beep N times (countdown tick)
#   GET /status      → {"state":"on"|"off", "ip":"...", "hostname":"..."}

import requests
import config


class RingLight:
    """
    Ring light controller via HTTP REST + mDNS.

    Usage (from main.py):
        light = RingLight()
        light.connect()
        light.on()
        light.beep()   # once per countdown tick
        light.flash()
        light.off()
    """

    def __init__(self):
        self._base   = config.RINGLIGHT_BASE_URL.rstrip("/")
        self._online = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self):
        """
        Probe the ring light. Non-fatal if offline — booth still runs.
        Also used internally to auto-reconnect after a failed command.
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
        if self._send("/on"):
            print("[RingLight] ON")

    def off(self):
        """All LEDs off."""
        if self._send("/off"):
            print("[RingLight] OFF")

    def flash(self):
        """
        Single bright burst (ESP32 handles 300 ms timing then self-extinguishes).
        No need to call off() after this.
        """
        if self._send("/flash"):
            print("[RingLight] FLASH")

    def blink(self, times: int = 3):
        """Blink N times."""
        if self._send(f"/blink?n={times}"):
            print(f"[RingLight] BLINK x{times}")

    def beep(self, times: int = 1, on_ms: int = 80):
        """
        Beep N times — call once per countdown second so the buzzer
        chirps in sync with the 3-2-1 countdown on screen.
        """
        if self._send(f"/beep?n={times}&ms={on_ms}"):
            print(f"[RingLight] BEEP x{times}")

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

    def _send(self, path: str) -> bool:
        """
        Fire-and-forget GET.
        Returns True on success, False on any error.
        Attempts one auto-reconnect if the device was previously offline.
        """
        if not self._online:
            # Try to reconnect once before giving up
            self.connect()
            if not self._online:
                return False
        try:
            r = self._get(path, timeout=3)
            return r is not None and r.status_code == 200
        except Exception as e:
            print(f"[RingLight] Command failed ({path}): {e}")
            # Mark offline so next call triggers a reconnect attempt
            self._online = False
            return False

    def _get(self, path: str, timeout: int = 3):
        return requests.get(self._base + path, timeout=timeout)

    def _warn(self):
        self._online = False
        print("[RingLight] Device unreachable — booth will run without ring light.")
        print(f"[RingLight] Expected at: {self._base}")
