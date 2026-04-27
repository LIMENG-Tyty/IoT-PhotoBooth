# telegram.py — Telegram Bot photo delivery
#
# Responsibilities:
#   - Send captured photos to a Telegram chat/group
#   - Return success/failure to main.py

import requests
import config


def send_photo(image_path: str, caption: str = "") -> bool:
    """
    Send a photo file to Telegram.

    Args:
        image_path: local path to the JPEG file
        caption:    optional caption text

    Returns:
        True on success, False on any error
    """
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as f:
            response = requests.post(
                url,
                data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": f},
                timeout=15,
            )
        ok = response.status_code == 200
        if ok:
            print(f"[Telegram] Sent: {image_path}")
        else:
            print(f"[Telegram] Failed {response.status_code}: {response.text[:120]}")
        return ok

    except FileNotFoundError:
        print(f"[Telegram] File not found: {image_path}")
        return False
    except requests.exceptions.Timeout:
        print("[Telegram] Request timed out.")
        return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def send_message(text: str) -> bool:
    """Send a plain text message (useful for status/error notifications)."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[Telegram] sendMessage error: {e}")
        return False
