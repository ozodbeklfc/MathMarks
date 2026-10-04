"""Settings, read from environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telegram IDs allowed to use the bot and mini app, comma separated.
TEACHER_IDS = {int(x) for x in os.getenv("TEACHER_IDS", "").replace(" ", "").split(",") if x}

# Public HTTPS address of the mini app. Railway sets RAILWAY_PUBLIC_DOMAIN itself.
_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL") or (f"https://{_domain}" if _domain else "")

# Database file. On Railway it goes on the attached volume so it survives redeploys.
_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "")
DB_PATH = os.getenv("DB_PATH") or str(Path(_volume or BASE_DIR / "data") / "baholar.db")

PORT = int(os.getenv("PORT", "8000"))

# DEV_MODE=1 turns off the Telegram signature check (local testing only).
DEV_MODE = os.getenv("DEV_MODE", "") == "1"

# Points per colour. An empty cell gives 0.
POINTS = {"green": 3, "yellow": 1, "red": 0}
COLORS = tuple(POINTS)
