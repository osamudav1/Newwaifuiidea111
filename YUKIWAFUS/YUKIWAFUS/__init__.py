import logging
from YUKIWAFUS.logging import LOGGER
from pyrogram import Client
import config

# ── Bot Client ────────────────────────────────────────────────────────────────
app = Client(
    "YUKIWAFUS",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

# ── Export ────────────────────────────────────────────────────────────────────
__all__ = ["app", "LOGGER"]
