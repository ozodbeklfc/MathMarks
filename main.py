"""Starts the web server (API + mini app) and the Telegram bot in one process."""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
from api import router
from db import init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("baholar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = None
    if config.BOT_TOKEN:
        from bot import run_bot
        task = asyncio.create_task(run_bot())
        task.add_done_callback(lambda t: t.cancelled() or (t.exception() and log.error("Bot stopped: %r", t.exception())))
        if not config.TEACHER_IDS:
            log.warning("TEACHER_IDS is empty: nobody can use the bot yet")
    else:
        log.warning("BOT_TOKEN is not set: the bot is off, only the web server runs")
    yield
    if task:
        task.cancel()


app = FastAPI(title="Baholar", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True}


@app.middleware("http")
async def no_cache(request, call_next):
    # Telegram's built-in browser caches hard; make it always check for new files.
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/", StaticFiles(directory=config.BASE_DIR / "webapp", html=True), name="webapp")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
