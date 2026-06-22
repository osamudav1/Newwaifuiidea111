import asyncio
from datetime import datetime

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import (
    usersdb, chatsdb, collectiondb,
    waifudb, balancedb, sudoersdb
)
from YUKIWAFUS.utils.api import get_stats
from YUKIWAFUS.utils.helpers import sc

BOT_START_TIME = datetime.utcnow()


def uptime_str() -> str:
    delta = datetime.utcnow() - BOT_START_TIME
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    d, h   = divmod(h, 24)
    parts  = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


# ── /stats ────────────────────────────────────────────────────────────────────
@app.on_message(filters.command("stats") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def stats_handler(client: Client, message: Message):
    processing = await message.reply_text(f"⏳ {sc('Fetching stats...')}")

    # Gather all counts concurrently
    (
        total_users,
        total_groups,
        total_collectors,
        api_stats,
        sudo_data,
    ) = await asyncio.gather(
        usersdb.count_documents({}),
        chatsdb.count_documents({"chat_id": {"$lt": 0}}),
        collectiondb.count_documents({}),
        get_stats(),
        sudoersdb.find_one({"sudo": "sudo"}),
    )

    total_waifus   = (api_stats or {}).get("total", "N/A")
    total_sudoers  = len((sudo_data or {}).get("sudoers", []))
    bot_info       = await client.get_me()

    text = (
        f"<blockquote>📊 <b>{sc('Yukiwafus Stats')}</b></blockquote>\n\n"

        f"🤖 <b>{sc('Bot')}:</b>\n"
        f"  ◈ {sc('Name')}: <b>{bot_info.first_name}</b>\n"
        f"  ◈ {sc('Username')}: @{bot_info.username}\n"
        f"  ◈ {sc('Uptime')}: <b>{uptime_str()}</b>\n\n"

        f"👥 <b>{sc('Database')}:</b>\n"
        f"  ◈ {sc('Users')}: <b>{total_users}</b>\n"
        f"  ◈ {sc('Groups')}: <b>{total_groups}</b>\n"
        f"  ◈ {sc('Collectors')}: <b>{total_collectors}</b>\n"
        f"  ◈ {sc('Sudo Users')}: <b>{total_sudoers}</b>\n\n"

        f"🌸 <b>{sc('Waifu')}:</b>\n"
        f"  ◈ {sc('Total in API')}: <b>{total_waifus}</b>\n\n"

        f"👑 <b>{sc('Owner')}: </b><code>{config.OWNER_ID}</code>"
    )

    await processing.edit_text(text, parse_mode=enums.ParseMode.HTML)


# ── /botstats (public) ────────────────────────────────────────────────────────
@app.on_message(filters.command("botstats"))
async def botstats_handler(client: Client, message: Message):
    total_users  = await usersdb.count_documents({})
    total_groups = await chatsdb.count_documents({"chat_id": {"$lt": 0}})
    api_stats    = await get_stats()
    total_waifus = (api_stats or {}).get("total", "N/A")

    text = (
        f"<blockquote>🌸 <b>{sc('Yukiwafus')}</b></blockquote>\n\n"
        f"👤 {sc('Users')}: <b>{total_users}</b>\n"
        f"👥 {sc('Groups')}: <b>{total_groups}</b>\n"
        f"🎴 {sc('Waifus in DB')}: <b>{total_waifus}</b>\n"
        f"⏱ {sc('Uptime')}: <b>{uptime_str()}</b>"
    )

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
  
