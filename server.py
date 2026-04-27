# server.py — SnapBooth Web UI server
# Single command: python server.py → http://localhost:5000

from flask import Flask, jsonify, send_from_directory, send_file, Response, request
from flask_cors import CORS
import os, threading, requests as req_lib
import state                        # shared BOOTH + frame_lock
import main as booth                # booth loop

app = Flask(__name__, static_folder=".")
CORS(app)

# ── Routes ────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/status")
def status():
    return jsonify(state.BOOTH)

@app.route("/api/live-frame")
def live_frame():
    if state.LIVE_FRAME_JPEG is None:
        return ("", 204)
    return Response(
        state.LIVE_FRAME_JPEG,
        mimetype="image/jpeg",
        headers={"Cache-Control": "no-store"}
    )

@app.route("/api/frame-choice", methods=["POST"])
def set_frame_choice():
    data = request.get_json(silent=True) or {}
    with state.frame_lock:
        if data.get("style"): state.BOOTH["frame_style"] = data["style"]
        if data.get("color"): state.BOOTH["frame_color"] = data["color"]
        if data.get("theme"): state.BOOTH["frame_theme"] = data["theme"]
        state.save_prefs(
            state.BOOTH["frame_style"],
            state.BOOTH["frame_color"],
            state.BOOTH["frame_theme"]
        )
        print(f"[Server] ✓ Frame → style={state.BOOTH['frame_style']}  color={state.BOOTH['frame_color']}")
    return jsonify({"ok": True,
                    "style": state.BOOTH["frame_style"],
                    "color": state.BOOTH["frame_color"]})

@app.route("/api/latest")
def latest_photo():
    if not state.BOOTH["latest_photo"]:
        return jsonify({"error": "no photo yet"}), 404
    path = os.path.join("captures", state.BOOTH["latest_photo"])
    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404
    return send_file(path, mimetype="image/jpeg")

@app.route("/captures/<filename>")
def serve_capture(filename):
    return send_from_directory("captures", filename)

@app.route("/stream")
def proxy_stream():
    import config
    def generate():
        buffer = b""
        try:
            r = req_lib.get(config.ESP32_STREAM_URL, stream=True, timeout=15)
            for chunk in r.iter_content(chunk_size=1024):
                buffer += chunk
                while True:
                    start = buffer.find(b'\xff\xd8')
                    end   = buffer.find(b'\xff\xd9')
                    if start == -1 or end == -1 or end < start:
                        break
                    jpeg   = buffer[start:end+2]
                    buffer = buffer[end+2:]
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n"
                        b"\r\n" + jpeg + b"\r\n"
                    )
        except Exception as e:
            print(f"[Stream] Proxy error: {e}")

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", "Expires": "0",
            "Access-Control-Allow-Origin": "*",
        }
    )

# ── Entry point ───────────────────────────────────────────

if __name__ == "__main__":
    t = threading.Thread(target=booth.run, daemon=True)
    t.start()
    print("=" * 45)
    print("  SnapBooth Web UI  →  http://localhost:5000")
    print("=" * 45)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)