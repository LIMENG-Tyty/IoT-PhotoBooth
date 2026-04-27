# state.py — shared booth state, imported by both server.py and main.py
import threading, json, os

_PREFS_FILE = "frame_prefs.json"

def _load_prefs():
    try:
        with open(_PREFS_FILE) as f:
            p = json.load(f)
            print(f"[State] Loaded saved frame: {p.get('frame_style')}/{p.get('frame_color')}")
            return p
    except Exception:
        return {}

def save_prefs(style, color, theme):
    try:
        with open(_PREFS_FILE, "w") as f:
            json.dump({"frame_style": style, "frame_color": color, "frame_theme": theme}, f)
    except Exception:
        pass

_prefs = _load_prefs()

# ── Shared state ──────────────────────────────────────────
frame_lock = threading.Lock()

BOOTH = {
    "state":        "IDLE",
    "seconds_left": 0,
    "fingers":      0,
    "progress":     0.0,
    "send_ok":      None,
    "latest_photo": None,
    "frame_style":  _prefs.get("frame_style", "classic"),
    "frame_color":  _prefs.get("frame_color", "gold"),
    "frame_theme":  _prefs.get("frame_theme", "vintage"),
}

LIVE_FRAME_JPEG = None   # raw bytes, updated by main.py