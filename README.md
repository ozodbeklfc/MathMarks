# Baholar

Telegram bot and mini app that replace the coloured Excel gradebook.

- Marks are colours: green = 3 points, yellow = 1, red = 0, empty = 0.
- Every topic has two marks: `toq` (classwork) and `juft` (homework). Topics such as Yutuqlar or IDC have one.
- The ranking is by total points, highest first.

## Files

| File | What it does |
| --- | --- |
| `main.py` | Starts the web server and the bot together |
| `bot.py` | Bot commands (Uzbek) |
| `api.py` | JSON API for the mini app, with Telegram signature check |
| `services.py` | Queries and scoring |
| `excel.py` | Excel import and export |
| `db.py` | Database tables (SQLite) |
| `config.py` | Settings and point values |
| `webapp/` | The mini app (HTML, CSS, JS) |

## Deploy on Railway

1. Create a bot with @BotFather and copy the token.
2. Push this folder to a GitHub repository and create a Railway project from it.
3. In the service's **Variables** add `BOT_TOKEN` and `TEACHER_IDS`.
   To find the ID: start the bot before setting `TEACHER_IDS`; it replies with your Telegram ID.
4. In **Settings → Networking** press **Generate Domain** (port 8000 if asked).
5. Attach a **Volume** to the service (mount path `/data`). The database is stored there and survives redeploys.
6. Redeploy. Send `/start` to the bot, then send the Excel file to load the existing marks.

Railway sets `PORT`, `RAILWAY_PUBLIC_DOMAIN` and `RAILWAY_VOLUME_MOUNT_PATH` itself; the app reads them.

## Run locally

```
pip install -r requirements.txt
DEV_MODE=1 python main.py        # open http://localhost:8000
```

`DEV_MODE=1` switches off the Telegram check so the mini app opens in a normal browser. Never set it on Railway.

## Bot commands

`/start`, `/add_class`, `/add_class_members`, `/classes`, `/import`, `/export`, `/cancel`.
Sending an `.xlsx` file imports it: each sheet becomes a class, and a class with the same name is replaced.
