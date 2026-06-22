import logging
from YUKIWAFUS.Logging import LOGGER  # object
from pyrogram import Client
import config

app = Client(
    "YUKIWAFUS",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

__all__ = ["app", "LOGGER"]
