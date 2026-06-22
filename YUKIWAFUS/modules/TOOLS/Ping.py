import asyncio
import platform
from datetime import datetime

import psutil
from pyrogram import Client, enums, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

import config
from YUKIWAFUS import app
from YUKIWAFUS.utils.helpers import sc


# ── System Stats ──────────────────────────────────────────────────────────────
async def get_sys_stats() -> tuple:
    cpu  = psutil.cpu_percent(interval=0.5)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    ram_used  = round(ram.used  / (1024 ** 3), 2)
    ram_total = round(ram.total / (1024 ** 3), 2)
    ram_pct   = ram.percent

    disk_used  = round(disk.used  / (1024 ** 3), 2)
    disk_total = round(disk.total / (1024 ** 3), 2)
    disk_pct   = disk.percent

    return cpu, ram_used, ram_total, ram_pct, disk_used, disk_total, disk_pct


def progress_bar(pct: float, length: int = 8) -> str:
    filled = int((pct / 100) * length)
    return "█" * filled + "░" * (length - filled)


# ── /ping ─────────────────────────────────────────────────────────────────────
@app.on_message(filters.command("ping"))
async def ping_handler(client: Client, message: Message):
    start = datetime.now()

    bot = await client.get_me()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(sc("Support"), url=config.SUPPORT_CHAT),
            InlineKeyboardButton(sc("Updates"), url=config.UPDATE_CHANNEL),
        ]
    ]) if config.SUPPORT_CHAT and config.UPDATE_CHANNEL else None

    resp = await message.reply_text(f"🏓 {sc('Pinging')}...")

    ping_ms = round((datetime.now() - start).microseconds / 1000, 2)

    cpu, ram_used, ram_total, ram_pct, disk_used, disk_total, disk_pct = await get_sys_stats()

    text = (
        f"<blockquote>🏓 <b>{sc('Pong')}!</b> — <b>{ping_ms}ms</b></blockquote>\n\n"
        f"🤖 <b>{sc('Bot')}:</b> {bot.mention}\n\n"
        f"<b>{sc('System Stats')}:</b>\n"
        f"  ◈ 🖥 {sc('CPU')}: <b>{cpu}%</b> {progress_bar(cpu)}\n"
        f"  ◈ 🧠 {sc('RAM')}: <b>{ram_used}/{ram_total} GB</b> ({ram_pct}%) {progress_bar(ram_pct)}\n"
        f"  ◈ 💾 {sc('Disk')}: <b>{disk_used}/{disk_total} GB</b> ({disk_pct}%) {progress_bar(disk_pct)}\n\n"
        f"  ◈ 🐍 {sc('Python')}: <b>{platform.python_version()}</b>\n"
        f"  ◈ 🖱 {sc('Platform')}: <b>{platform.system()} {platform.release()}</b>"
    )

    await resp.edit_text(
        text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
    )
