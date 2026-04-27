# main.py — Photo Booth orchestrator
# Run via: python server.py

import cv2
import os, time, math
from datetime import datetime

import config
import state                        # shared BOOTH, frame_lock, LIVE_FRAME_JPEG
from gesture   import GestureDetector
from ringlight import RingLight
import telegram

os.makedirs(config.CAPTURE_DIR, exist_ok=True)


def _sync(**kwargs):
    state.BOOTH.update(kwargs)


def _push_frame(frame):
    try:
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        state.LIVE_FRAME_JPEG = buf.tobytes()
    except Exception:
        pass


def _get_frame_choice():
    """Thread-safe read of current frame style/color."""
    with state.frame_lock:
        return (
            state.BOOTH.get("frame_style", "classic"),
            state.BOOTH.get("frame_color",  "gold"),
        )


# ── Frame overlays (BGR for OpenCV) ──────────────────────
COLOR_MAP = {
    "gold":       (110, 169, 200),
    "rose":       (106, 125, 201),
    "sage":       (110, 140, 122),
    "slate":      (160, 127, 106),
    "lavender":   (160, 122, 156),
    "terracotta": ( 90, 122, 160),
    "charcoal":   ( 42,  33,  24),
    "cream":      (232, 247, 245),
}

def apply_frame(image, style, color_name):
    img = image.copy()
    h, w = img.shape[:2]
    col  = COLOR_MAP.get(color_name, COLOR_MAP["gold"])

    if style == "classic":
        t = max(12, w // 40)
        cv2.rectangle(img, (0, 0), (w-1, h-1), col, t)
        cv2.rectangle(img, (t+4, t+4), (w-t-5, h-t-5), col, 2)

    elif style == "film":
        t  = max(18, w // 30)
        ov = img.copy()
        cv2.rectangle(ov, (0, 0), (w, h), (26, 10, 8), -1)
        cv2.addWeighted(ov, 0.55, img, 0.45, 0, img)
        cv2.rectangle(img, (0, 0), (w-1, h-1), (26, 10, 8), t)
        pw, ph, gap = 14, 20, 34
        for y in range(gap, h - gap, gap + ph):
            cv2.rectangle(img, (6, y),      (6+pw, y+ph),  (245, 240, 232), -1)
            cv2.rectangle(img, (w-6-pw, y), (w-6,  y+ph),  (245, 240, 232), -1)

    elif style == "polaroid":
        s = max(10, w // 50)
        b = max(50, h // 6)
        cv2.rectangle(img, (0, 0),   (w-1, h-1), (250, 247, 245), s)
        cv2.rectangle(img, (0, h-b), (w, h),     (250, 247, 245), -1)
        cv2.rectangle(img, (0, 0),   (w-1, h-1), (220, 215, 210),  2)

    elif style == "botanical":
        t   = max(10, w // 45)
        inn = t + 6
        cv2.rectangle(img, (0, 0),         (w-1, h-1),         col, t)
        cv2.rectangle(img, (inn, inn),     (w-inn-1, h-inn-1), col, 2)
        cv2.rectangle(img, (inn+6, inn+6), (w-inn-7, h-inn-7), col, 1)

    return img


def _style_label(s):
    return {"classic":"Classic Gold","film":"35mm Film",
            "polaroid":"Polaroid","botanical":"Botanical"}.get(s, s.title())

def _color_label(c):
    return {"gold":"Vintage Gold","rose":"Dusty Rose","sage":"Sage Green",
            "slate":"Slate Blue","lavender":"Muted Lavender",
            "terracotta":"Terracotta","charcoal":"Charcoal",
            "cream":"Ivory Cream"}.get(c, c.title())


# ── Main loop ─────────────────────────────────────────────

def run():
    detector = GestureDetector()
    light    = RingLight()

    detector.start()
    light.connect()

    print("=" * 50)
    print("   SnapBooth running  →  http://localhost:5000")
    print("=" * 50)

    booth_state     = "IDLE"
    countdown_start = None
    captured_frame  = None
    last_frame      = None
    result_time     = None
    locked_style    = "classic"
    locked_color    = "gold"

    _sync(state="IDLE", seconds_left=0, fingers=0, progress=0.0,
          send_ok=None, latest_photo=None)

    try:
        while True:
            now = time.time()

            # ── IDLE ─────────────────────────────────────────
            if booth_state == "IDLE":
                frame, triggered, fingers = detector.read(detect=True)
                if frame is not None:
                    last_frame = frame.copy()
                    _push_frame(frame)

                _sync(state="IDLE", fingers=fingers,
                      progress=detector.trigger_progress)

                if triggered:
                    # Lock frame choice at trigger time (thread-safe)
                    locked_style, locked_color = _get_frame_choice()
                    print(f"[Booth] ✋ HIGH FIVE!  style={locked_style}  color={locked_color}")
                    light.on()
                    booth_state     = "COUNTDOWN"
                    countdown_start = now
                    _sync(state="COUNTDOWN",
                          seconds_left=config.COUNTDOWN_SECONDS)

            # ── COUNTDOWN ────────────────────────────────────
            elif booth_state == "COUNTDOWN":
                frame, _, _ = detector.read(detect=False)
                if frame is not None:
                    last_frame = frame.copy()
                    _push_frame(frame)

                elapsed      = now - countdown_start
                remaining    = config.COUNTDOWN_SECONDS - elapsed
                seconds_left = max(1, math.ceil(remaining))
                _sync(state="COUNTDOWN", seconds_left=seconds_left)

                if remaining <= 0:
                    captured_frame = last_frame.copy()
                    booth_state = "CAPTURE"
                    _sync(state="CAPTURE", seconds_left=0)

            # ── CAPTURE ──────────────────────────────────────
            elif booth_state == "CAPTURE":
                light.flash()
                time.sleep(config.FLASH_DURATION)
                light.off()

                print(f"[Booth] Applying frame: style={locked_style}  color={locked_color}")
                framed = apply_frame(captured_frame, locked_style, locked_color)

                ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"photobooth_{ts}.jpg"
                savepath = os.path.join(config.CAPTURE_DIR, filename)
                cv2.imwrite(savepath, framed)
                print(f"[Booth] ✓ Saved → {savepath}")

                _push_frame(framed)
                _sync(state="SENDING", latest_photo=filename)

                caption = (
                    f"SnapBooth · {_style_label(locked_style)} · {_color_label(locked_color)}\n"
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                send_result = telegram.send_photo(savepath, caption)
                result_time = now
                booth_state = "RESULT"
                _sync(state="RESULT", send_ok=send_result)

            # ── RESULT ───────────────────────────────────────
            elif booth_state == "RESULT":
                frame, _, _ = detector.read(detect=False)
                if frame is not None:
                    last_frame = frame.copy()

                if now - result_time >= max(config.RESULT_HOLD_SECONDS, 8.0):
                    print("[Booth] Back to idle.")
                    booth_state = "IDLE"
                    result_time = captured_frame = None
                    _sync(state="IDLE", send_ok=None, seconds_left=0,
                          fingers=0, progress=0.0)

            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        detector.stop()
        light.disconnect()
        print("[Booth] Bye!")


if __name__ == "__main__":
    run()