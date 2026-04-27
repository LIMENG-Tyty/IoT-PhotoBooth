# config.py — all project settings in one place
# esp32cam-a1b2.local:81/stream
# ── ESP32-CAM (stream) ────────────────────────────────────
ESP32_STREAM_URL = "http://localhost:8000/video"

# ── ESP32 Ring Light (REST + mDNS) ───────────────────────
# Flash this sketch: esp32/esp32_ringlight/esp32_ringlight.ino
# The ESP32 advertises itself as http://photobooth-light.local
RINGLIGHT_BASE_URL = "http://photobooth-light.local"

# REST endpoints (served by the Arduino sketch):
#   GET /on          → solid white on
#   GET /off         → all LEDs off
#   GET /flash       → bright burst then off
#   GET /blink?n=3   → blink N times

# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "REDACTED"    # ← from @BotFather
TELEGRAM_CHAT_ID   = "REDACTED"      # ← from @userinfobot

# ── Booth timing ──────────────────────────────────────────
COUNTDOWN_SECONDS   = 3     # seconds from trigger to capture
FLASH_DURATION      = 0.4   # seconds of white flash overlay
RESULT_HOLD_SECONDS = 2.5   # seconds to show result before idle

# ── Gesture detection ─────────────────────────────────────
MIN_FINGERS_OPEN    = 4     # fingers open to count as high five
FINGER_THRESHOLD    = 0.35  # extension sensitivity
TRIGGER_HOLD_FRAMES = 4     # consecutive frames to confirm trigger

# ── Storage ───────────────────────────────────────────────
CAPTURE_DIR = "captures"
