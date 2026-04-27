# gesture.py — MediaPipe hand gesture detection

import cv2
import mediapipe as mp
import math
import time
import config

mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
mp_style = mp.solutions.drawing_styles

# Landmark indices
WRIST       = 0
FINGER_TIPS = [4,  8,  12, 16, 20]   # thumb, index, middle, ring, pinky tips
FINGER_PIP  = [3,  6,  10, 14, 18]   # PIP joints (middle knuckle) — better reference
FINGER_MCP  = [1,  5,   9, 13, 17]   # MCP joints (base knuckle at palm)


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _finger_is_open(lms, tip_idx, pip_idx, mcp_idx, is_thumb=False):
    """
    Check if a finger is extended.
    - Thumb: tip must be far from wrist laterally
    - Others: tip must be clearly above (lower y) the PIP joint,
              normalized by palm size so it works at any distance.
    """
    tip   = lms[tip_idx]
    pip   = lms[pip_idx]
    mcp   = lms[mcp_idx]
    wrist = lms[WRIST]

    if is_thumb:
        # Thumb: lateral distance from wrist
        dist_tip  = math.hypot(tip.x - wrist.x, tip.y - wrist.y)
        dist_mcp  = math.hypot(mcp.x - wrist.x, mcp.y - wrist.y)
        return dist_tip > dist_mcp * 1.2

    # Palm reference = distance from wrist to middle finger MCP (landmark 9)
    palm_size = math.hypot(lms[9].x - wrist.x, lms[9].y - wrist.y)
    if palm_size < 1e-6:
        return False

    # Finger is open if tip is above PIP by at least THRESHOLD * palm_size
    # "above" = smaller y in image coords
    tip_to_pip = pip.y - tip.y   # positive when tip is above pip
    return (tip_to_pip / palm_size) > config.FINGER_THRESHOLD


def count_open_fingers(hand_landmarks):
    """Return how many fingers are extended (0–5)."""
    lms = hand_landmarks.landmark
    count = 0
    for i, (tip, pip, mcp) in enumerate(zip(FINGER_TIPS, FINGER_PIP, FINGER_MCP)):
        if _finger_is_open(lms, tip, pip, mcp, is_thumb=(i == 0)):
            count += 1
    return count


# ── Stream + detector class ───────────────────────────────────────────────────

class GestureDetector:

    def __init__(self):
        self._cap            = None
        self._hands          = None
        self._trigger_frames = 0

    def start(self):
        self._cap = self._open_stream()
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.6,   # slightly relaxed for ESP32-CAM
            min_tracking_confidence=0.5,
            model_complexity=0,
        )
        print(f"[Gesture] Stream opened: {config.ESP32_STREAM_URL}")

    def stop(self):
        if self._cap:
            self._cap.release()
        if self._hands:
            self._hands.close()
        print("[Gesture] Stopped.")

    def read(self, detect=True):
        # Flush stale buffered frames from the MJPEG stream
        # grab() discards without decoding — keeps us on the latest frame
        for _ in range(3):
            self._cap.grab()

        ret, frame = self._cap.read()
        if not ret or frame is None:
            print("[Gesture] Stream lost, reconnecting...")
            time.sleep(0.5)
            self._cap.release()
            self._cap = self._open_stream()
            return None, False, 0

        triggered = False
        fingers   = 0

        if detect:
            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb)

            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(
                        frame, hand_lms,
                        mp_hands.HAND_CONNECTIONS,
                        mp_style.get_default_hand_landmarks_style(),
                        mp_style.get_default_hand_connections_style(),
                    )
                    f = count_open_fingers(hand_lms)
                    fingers = max(fingers, f)
                    # Debug: print per-finger state to terminal
                    lms = hand_lms.landmark
                    states = []
                    for i, (tip, pip, mcp) in enumerate(zip(FINGER_TIPS, FINGER_PIP, FINGER_MCP)):
                        open_ = _finger_is_open(lms, tip, pip, mcp, is_thumb=(i==0))
                        states.append("1" if open_ else "0")
                    print(f"[Gesture] fingers={''.join(states)}  count={f}  need={config.MIN_FINGERS_OPEN}")

            # Debounce
            if fingers >= config.MIN_FINGERS_OPEN:
                self._trigger_frames += 1
            else:
                self._trigger_frames = max(0, self._trigger_frames - 2)  # decay faster

            if self._trigger_frames >= config.TRIGGER_HOLD_FRAMES:
                triggered = True
                self._trigger_frames = 0

        return frame, triggered, fingers

    @property
    def trigger_progress(self):
        return min(self._trigger_frames / config.TRIGGER_HOLD_FRAMES, 1.0)

    @staticmethod
    def _open_stream():
        cap = cv2.VideoCapture(config.ESP32_STREAM_URL)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap