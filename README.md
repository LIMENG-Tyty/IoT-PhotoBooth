# SnapBooth 📸

A vintage-inspired smart photo booth powered by **ESP32-CAM**, **MediaPipe** hand gesture detection, and **Telegram** photo delivery. Raise your hand for a high-five and receive your framed photo instantly on Telegram.

---

## Hardware Required

| Component | Purpose |
|---|---|
| PC / Laptop (Windows) | Runs the Python server + gesture detection |
| ESP32-CAM module | Streams live video over Wi-Fi |
| ESP32 DevKit V1 | Controls the WS2812B ring light via REST |
| WS2812B LED ring (16 LEDs) | Fill light for countdown + flash |
| Wi-Fi router | Connects all devices on the same network |

---

## Project Structure

```
Project/
├── server.py           ← Main entry point (Flask web UI + booth loop)
├── main.py             ← Booth orchestrator (gesture → countdown → capture)
├── state.py            ← Shared state between server and booth
├── gesture.py          ← MediaPipe hand detection
├── ringlight.py        ← ESP32 ring light REST client
├── telegram.py         ← Telegram bot photo delivery
├── stream_server.py    ← ESP32-CAM MJPEG proxy (port 8000)
├── config.py           ← All settings (WiFi, Telegram, timing)
├── index.html          ← Web UI
├── esp32_ringlight.py  ← MicroPython firmware for ESP32 ring light
├── requirements.txt    ← Python dependencies
└── captures/           ← Saved photos (auto-created)
```

---

## Installation

### 1. Prerequisites

- **Python 3.11** — download from [python.org](https://www.python.org/downloads/)
- **Arduino IDE** — for flashing the ESP32-CAM
- **Thonny IDE** — for flashing MicroPython to the ESP32 ring light

### 2. Clone / Download the Project

Place all project files in a folder, e.g. `C:\Users\YourName\Desktop\Project\`

### 3. Create a Virtual Environment

Open a terminal in the project folder:

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
```

### 4. Install Python Dependencies

```powershell
pip install -r requirements.txt
```

---

## Hardware Setup

### ESP32-CAM — Video Stream

1. Open **Arduino IDE**
2. Go to **File → Examples → ESP32 → Camera → CameraWebServer**
3. In the sketch, set your Wi-Fi credentials:
   ```cpp
   const char* ssid     = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
4. Set the camera model at the top of the sketch:
   ```cpp
   #define CAMERA_MODEL_AI_THINKER
   ```
5. Select board: **Tools → Board → ESP32 Arduino → AI Thinker ESP32-CAM**
6. Upload the sketch (use a USB-to-serial adapter, IO0 to GND during flash)
7. Open Serial Monitor at 115200 baud — note the IP address printed
8. The stream will be available at `http://<ESP32-CAM-IP>:81/stream`

Update `stream_server.py` with the correct hostname or IP:
```python
HOSTNAME = "esp32cam-a1b2.local"   # ← change to your ESP32-CAM hostname or IP
PORT = 81
```

### ESP32 Ring Light — MicroPython Firmware

1. Flash **MicroPython** to your ESP32 DevKit V1 using Thonny:
   - Download MicroPython `.bin` for ESP32 from [micropython.org](https://micropython.org/download/esp32/)
   - In Thonny: **Tools → Options → Interpreter → MicroPython (ESP32)**
   - Flash firmware via **Tools → Flash firmware**

2. Open `esp32_ringlight.py` in Thonny and edit the Wi-Fi credentials:
   ```python
   SSID     = "YOUR_WIFI_SSID"       # ← your Wi-Fi name
   PASSWORD = "YOUR_WIFI_PASSWORD"   # ← your Wi-Fi password
   ```

3. Also adjust hardware if needed:
   ```python
   LED_PIN  = 4    # GPIO pin connected to ring data line
   NUM_LEDS = 16   # number of LEDs on your ring
   ```

4. Save the file **to the ESP32 as `main.py`**:
   - File → Save as → MicroPython device → name it `main.py`

5. Reset the ESP32 — it will connect to Wi-Fi and advertise itself as `photobooth-light.local`

---

## Configuration

Open `config.py` and update the following:

```python
# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"    # from @BotFather on Telegram
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID"      # from @userinfobot on Telegram

# ── Booth timing (optional) ───────────────────────────────
COUNTDOWN_SECONDS   = 3     # seconds from gesture to capture
FLASH_DURATION      = 0.4   # ring light flash duration
RESULT_HOLD_SECONDS = 2.5   # seconds to show result

# ── Gesture sensitivity (optional) ────────────────────────
MIN_FINGERS_OPEN    = 4     # fingers needed to trigger (4 or 5)
FINGER_THRESHOLD    = 0.35  # raise if detection is too sensitive
TRIGGER_HOLD_FRAMES = 4     # frames to hold gesture before triggering
```

### Getting Telegram Credentials

**Bot Token:**
1. Open Telegram → search `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the token it gives you

**Chat ID:**
1. Add your bot to a group, or start a private chat with it
2. Open Telegram → search `@userinfobot`
3. Forward a message from your group to get the group chat ID (starts with `-`)

---

## Running the Booth

You need **two terminals** open simultaneously, both with the venv activated:

**Terminal 1 — Camera stream proxy:**
```powershell
venv\Scripts\activate
python stream_server.py
```
> Connects to the ESP32-CAM and re-serves the stream at `http://localhost:8000/video`

**Terminal 2 — Main booth server:**
```powershell
venv\Scripts\activate
python server.py
```
> Starts the web UI at `http://localhost:5000` and the gesture detection loop

Then open your browser and go to: **http://localhost:5000**

---

## Using the Booth

1. **Home** — overview of the booth
2. **Frame** — choose your frame style (Classic Gold, 35mm Film, Polaroid, Botanical) and accent colour
3. **Capture** — step in front of the camera
   - Raise your hand with all 5 fingers open
   - Hold for ~1 second until detected
   - Countdown: 3 → 2 → 1 → 📸
   - Photo is saved with your chosen frame and sent to Telegram automatically
4. **How It Works** — technical overview
5. **About** — team info

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ConnectionRefusedError` on port 5000 | `server.py` is not running |
| `ConnectionRefusedError` on port 8000 | `stream_server.py` is not running |
| Camera feed shows "Waiting for ESP32-CAM" | Check ESP32-CAM is on the same Wi-Fi; check hostname in `stream_server.py` |
| Ring light not responding | Check ESP32 is powered and on same Wi-Fi; check `RINGLIGHT_BASE_URL` in `config.py` |
| Gesture not detecting | Stand 0.5–1.5m from camera; ensure good lighting; spread all 5 fingers clearly |
| Wrong frame applied to photo | Select frame on Frame page before entering the booth; check Terminal 2 shows `[Server] ✓ Frame →` with correct style |
| Telegram not receiving photo | Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `config.py`; ensure bot is in the chat |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Camera | ESP32-CAM (AI Thinker) · Arduino CameraWebServer |
| Ring Light | ESP32 DevKit V1 · MicroPython · WS2812B NeoPixel |
| Gesture Detection | Python · OpenCV · MediaPipe Hands |
| Backend | Python 3.11 · Flask · Flask-CORS |
| Messaging | Telegram Bot API |
| Frontend | HTML · CSS · Bootstrap 5 · Vanilla JavaScript |
| Transport | Wi-Fi · HTTP REST · MJPEG stream |

---

## Team

| Role | Name |
|---|---|
| Hardware Lead | Limeng Tyty |
| Vision Engineer | Channeath Ros |
| Backend Dev | Lim Darichhy |
| Frontend Dev | Sorn Somavatey |

---

*SnapBooth · IoT Final Project · Built with ❤ using ESP32 + MediaPipe*
