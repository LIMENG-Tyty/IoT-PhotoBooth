import cv2
import threading
import time
import socket
import subprocess
import re
from flask import Flask, Response

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
HOSTNAME = "esp32cam-a1b2.local"
PORT = 81

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8000

app = Flask(__name__)

latest_frame = None
frame_lock = threading.Lock()


# ─────────────────────────────────────────────
# DNS / Ping / Resolve fallback
# ─────────────────────────────────────────────
def resolve_ip(hostname):
    # 1) Try normal DNS/mDNS
    try:
        return socket.gethostbyname(hostname)
    except:
        pass

    # 2) Fallback: ping + arp table
    try:
        subprocess.run(["ping", "-c", "1", hostname],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

        arp = subprocess.check_output(["arp", "-n"]).decode()

        match = re.search(r"(\d+\.\d+\.\d+\.\d+).*" + re.escape(hostname), arp)
        if match:
            return match.group(1)

    except Exception as e:
        print("[Resolve] fallback failed:", e)

    return None


def get_stream_url():
    ip = resolve_ip(HOSTNAME)

    if not ip:
        print("[Stream] Cannot resolve ESP32 IP")
        return None

    url = f"http://{ip}:{PORT}/stream"
    print("[Stream] Using:", url)
    return url


# ─────────────────────────────────────────────
# Capture thread (ONLY ONE connection)
# ─────────────────────────────────────────────
def capture_stream():
    global latest_frame

    cap = None

    while True:
        try:
            if cap is None or not cap.isOpened():
                url = get_stream_url()

                if not url:
                    time.sleep(2)
                    continue

                cap = cv2.VideoCapture(url)

            ret, frame = cap.read()

            if not ret:
                print("[Stream] Frame lost, reconnecting...")
                cap.release()
                cap = None
                time.sleep(1)
                continue

            with frame_lock:
                latest_frame = frame

        except Exception as e:
            print("[Stream] Error:", e)
            if cap:
                cap.release()
            cap = None
            time.sleep(1)


threading.Thread(target=capture_stream, daemon=True).start()


# ─────────────────────────────────────────────
# Flask MJPEG output
# ─────────────────────────────────────────────
def generate_frames():
    global latest_frame

    while True:
        with frame_lock:
            frame = latest_frame

        if frame is None:
            time.sleep(0.01)
            continue

        try:
            _, buffer = cv2.imencode(".jpg", frame)
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" +
                   buffer.tobytes() +
                   b"\r\n")
        except:
            time.sleep(0.1)


@app.route("/")
def index():
    return '<h2>ESP32 Proxy Stream</h2><img src="/video">'


@app.route("/video")
def video():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("[Stream] Running on http://localhost:8000")
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True)