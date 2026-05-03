# ringlight_server.py — MicroPython REST server for ESP32 ring light
# Hardware: GPIO 23, 24x WS2812B LEDs, static white color
#           GPIO 18, Active buzzer (LOW-level triggered, MB12A05)
#
# Upload to ESP32 as main.py via Thonny
#
# REST API:
#   GET /on          → solid white + beep once
#   GET /off         → all LEDs off + beep twice
#   GET /flash       → bright burst 300ms then off
#   GET /blink?n=3   → blink N times
#   GET /status      → JSON status

import network
import socket
import neopixel
from machine import Pin
import time
import json

# ── CONFIG ────────────────────────────────────────────────
WIFI_SSID     = "Hotspot"
WIFI_PASSWORD = "123456789"
HOSTNAME      = "photobooth-light"   # → http://photobooth-light.local

LED_PIN    = 23
LED_COUNT  = 24
BRIGHTNESS = 0.78   # 0.0 – 1.0

BUZZER_PIN = 18     # HIGH-level triggered: 1=ON, 0=OFF

WHITE = (int(255 * BRIGHTNESS), int(255 * BRIGHTNESS), int(255 * BRIGHTNESS))
OFF   = (0, 0, 0)
# ─────────────────────────────────────────────────────────

np     = neopixel.NeoPixel(Pin(LED_PIN), LED_COUNT)
buzzer = Pin(BUZZER_PIN, Pin.OUT, value=0)  # LOW = silent on init
current_state = "off"


# ── Buzzer helpers ────────────────────────────────────────
# HIGH-level triggered: 1 = ON, 0 = OFF

def buzzer_beep(times=1, on_ms=100, off_ms=100):
    """Beep N times. HIGH = ON, LOW = OFF."""
    for i in range(times):
        buzzer.value(1)          # HIGH = buzz ON
        time.sleep_ms(on_ms)
        buzzer.value(0)          # LOW = buzz OFF
        if i < times - 1:
            time.sleep_ms(off_ms)


# ── LED helpers ───────────────────────────────────────────

def leds_on():
    global current_state
    for i in range(LED_COUNT):
        np[i] = WHITE
    np.write()
    current_state = "on"
    print("[Ring] ON")
    buzzer_beep(times=1, on_ms=80)   # 1 short beep = lights on


def leds_off():
    global current_state
    for i in range(LED_COUNT):
        np[i] = OFF
    np.write()
    current_state = "off"
    print("[Ring] OFF")
    # no beep on off


def leds_flash():
    """Full brightness burst for 300ms then off."""
    for i in range(LED_COUNT):
        np[i] = (255, 255, 255)
    np.write()
    print("[Ring] FLASH")
    time.sleep_ms(300)
    leds_off()
    # no beep on flash


def leds_blink(times=3):
    print(f"[Ring] BLINK x{times}")
    for _ in range(times):
        leds_on()
        time.sleep_ms(200)
        leds_off()
        time.sleep_ms(200)


# ── WiFi ──────────────────────────────────────────────────

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(dhcp_hostname=HOSTNAME)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    print(f"Connecting to {WIFI_SSID}", end="")
    for _ in range(20):
        if wlan.isconnected():
            break
        print(".", end="")
        time.sleep(1)

    if not wlan.isconnected():
        raise RuntimeError("WiFi connection failed")

    ip = wlan.ifconfig()[0]
    print(f"\nConnected! IP: {ip}")
    print(f"Access via: http://{HOSTNAME}.local  or  http://{ip}")
    return ip


# ── HTTP helpers ──────────────────────────────────────────

def parse_query(path):
    if "?" in path:
        route, qs = path.split("?", 1)
        params = {}
        for pair in qs.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v
        return route.strip("/"), params
    return path.strip("/"), {}


def send_json(conn, data, status=200):
    body = json.dumps(data)
    resp = (
        f"HTTP/1.1 {status} OK\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Connection: close\r\n\r\n"
        f"{body}"
    )
    conn.sendall(resp.encode())


# ── Request handler ───────────────────────────────────────

def handle_request(conn, addr):
    try:
        request = conn.recv(512).decode("utf-8", "ignore")
        if not request:
            return

        first_line = request.split("\r\n")[0]
        parts = first_line.split(" ")
        if len(parts) < 2:
            return

        method   = parts[0]
        raw_path = parts[1]
        route, params = parse_query(raw_path)

        print(f"[HTTP] {method} /{route} from {addr[0]}")

        if method != "GET":
            send_json(conn, {"ok": False, "msg": "method not allowed"}, status=405)
            return

        if route == "on":
            leds_on()
            send_json(conn, {"ok": True, "state": current_state})

        elif route == "off":
            leds_off()
            send_json(conn, {"ok": True, "state": current_state})

        elif route == "flash":
            send_json(conn, {"ok": True, "msg": "flash"})
            conn.close()
            leds_flash()
            return

        elif route == "blink":
            times = int(params.get("n", 3))
            times = max(1, min(times, 10))
            send_json(conn, {"ok": True, "msg": f"blink x{times}"})
            conn.close()
            leds_blink(times)
            return

        elif route == "status":
            wlan = network.WLAN(network.STA_IF)
            send_json(conn, {
                "ok":         True,
                "state":      current_state,
                "ip":         wlan.ifconfig()[0],
                "hostname":   f"{HOSTNAME}.local",
                "rssi":       wlan.status("rssi"),
                "leds":       LED_COUNT,
                "led_pin":    LED_PIN,
                "buzzer_pin": BUZZER_PIN,
            })

        elif route == "" or route == "index.html":
            body = (
                "<h2>Photo Booth Ring Light</h2>"
                f"<p>LEDs: {LED_COUNT} on GPIO {LED_PIN} | "
                f"Buzzer: GPIO {BUZZER_PIN} (low-level)</p>"
                "<p>"
                "<a href='/on'>/on</a> | "
                "<a href='/off'>/off</a> | "
                "<a href='/flash'>/flash</a> | "
                "<a href='/blink?n=3'>/blink?n=3</a> | "
                "<a href='/status'>/status</a>"
                "</p>"
            )
            resp = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: text/html\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"Connection: close\r\n\r\n"
                f"{body}"
            )
            conn.sendall(resp.encode())

        else:
            send_json(conn, {"ok": False, "msg": "not found"}, status=404)

    except Exception as e:
        print(f"[HTTP] Error: {e}")
    finally:
        conn.close()


# ── Server loop ───────────────────────────────────────────

def run_server(ip):
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(3)
    print(f"[HTTP] Server ready!")
    print(f"[HTTP] http://{HOSTNAME}.local/  or  http://{ip}/")

    while True:
        try:
            conn, addr = s.accept()
            handle_request(conn, addr)
        except OSError as e:
            print(f"[HTTP] Socket error: {e}")


# ── Entry point ───────────────────────────────────────────

def main():
    leds_off()
    ip = connect_wifi()

    # 3 white blinks + 3 beeps = ready
    leds_blink(3)

    print("[Ring] Ready! Waiting for commands...")
    run_server(ip)


main()
