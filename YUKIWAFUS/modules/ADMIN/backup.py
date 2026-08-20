import asyncio
from html import escape
from typing import Any

from pyrogram import Client, enums, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import backupdb, onoffdb
from YUKIWAFUS.utils.api import get_waifu_list


# This module intentionally owns its state and handlers. Existing game/admin
# modules do not need to know about the backup worker.
OWNER_FILTER = filters.user(config.OWNER_ID)
PAGE_SIZE = 50
PAGE_RETRIES = 4
SEND_RETRIES = 4
PAUSE_AFTER_PHOTOS = 5
PAUSE_SECONDS = 2
STATE_ID = "state"
CHANNEL_KEY = "backup_channel"

_backup_task: asyncio.Task | None = None


async def _get_state() -> dict:
    return await backupdb.find_one({"_id": STATE_ID}) or {
        "_id": STATE_ID,
        "last_id": 0,
        "api_skip": 0,
        "running": False,
        "sent_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "backed_up_ids": [],
    }


async def _save_state(**values: Any) -> None:
    if values:
        await backupdb.update_one(
            {"_id": STATE_ID},
            {"$set": values},
            upsert=True,
        )


async def _get_backup_channel() -> int:
    saved = await onoffdb.find_one({"key": CHANNEL_KEY})
    if saved and saved.get("value"):
        try:
            return int(saved["value"])
        except (TypeError, ValueError):
            pass
    return int(getattr(config, "BACKUP_CHANNEL", 0) or 0)


def _card_id(card: dict) -> int | None:
    raw = card.get("waifu_id", card.get("id"))
    if raw is None:
        raw = card.get("_id")
    try:
        value = int(raw)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _photo(card: dict) -> str | None:
    for key in ("img_url", "image", "photo", "image_url"):
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _text(value: Any, default: str, limit: int = 250) -> str:
    value = default if value is None or str(value).strip() == "" else str(value).strip()
    return escape(value[:limit])


def _caption(card: dict, card_id: int) -> str:
    character = card.get("character_name", card.get("name"))
    anime = card.get("anime_name", card.get("anime"))
    rarity = card.get("rarity")
    event = card.get("event", card.get("event_tag"))
    return (
        f"📛 <b>Character:</b> {_text(character, 'Unknown')}\n"
        f"🎬 <b>Anime:</b> {_text(anime, 'Unknown')}\n"
        f"🆔 <b>ID:</b> <code>{card_id}</code>\n"
        f"🌟 <b>Rarity:</b> {_text(rarity, 'Unknown', 80)}\n"
        f"🏷 <b>Event:</b> {_text(event, 'Standard', 120)}"
    )


def _status_name(status: Any) -> str:
    return str(getattr(status, "value", status)).lower()


async def _validate_channel(client: Client, channel_id: int) -> tuple[bool, str]:
    try:
        chat = await client.get_chat(channel_id)
        if getattr(chat, "type", None) not in {enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP}:
            return False, "Please send a channel or supergroup ID."

        me = await client.get_me()
        member = await client.get_chat_member(channel_id, me.id)
        status = _status_name(member.status)
        if "administrator" not in status and "owner" not in status:
            return False, "The bot must be an administrator in that channel."
        return True, getattr(chat, "title", str(channel_id))
    except Exception as exc:
        LOGGER.warning("Backup channel validation failed for %s: %s", channel_id, exc)
        return False, (
            "I cannot access that chat. Check the channel ID and add this bot as an "
            "administrator with permission to post messages."
        )


async def _fetch_page(skip: int) -> list | None:
    delay = 3
    for attempt in range(PAGE_RETRIES):
        page = await get_waifu_list(skip=skip, limit=PAGE_SIZE)
        if page is not None:
            return page
        if attempt + 1 < PAGE_RETRIES:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
    return None


async def _send_photo_with_retry(client: Client, channel_id: int, card: dict, card_id: int) -> None:
    delay = 3
    for attempt in range(SEND_RETRIES):
        try:
            await client.send_photo(
                chat_id=channel_id,
                photo=_photo(card),
                caption=_caption(card, card_id),
                parse_mode=enums.ParseMode.HTML,
            )
            return
        except FloodWait as exc:
            wait_for = max(int(getattr(exc, "value", 0) or 0) + 5, 5)
            LOGGER.warning("Backup FloodWait for %ss on card %s", wait_for, card_id)
            await asyncio.sleep(wait_for)
        except Exception:
            if attempt + 1 >= SEND_RETRIES:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def _mark_sent(card_id: int, last_id: int, api_skip: int) -> None:
    await backupdb.update_one(
        {"_id": STATE_ID},
        {
            "$set": {"last_id": last_id, "api_skip": api_skip, "running": True},
            "$addToSet": {"backed_up_ids": str(card_id)},
            "$inc": {"sent_count": 1},
        },
        upsert=True,
    )


async def _backup_worker(client: Client, start_id: int | None = None) -> None:
    state = await _get_state()
    channel_id = await _get_backup_channel()
    cursor = int(state.get("last_id", 0) or 0)
    skip = int(state.get("api_skip", 0) or 0)
    backed_up = {str(item) for item in state.get("backed_up_ids", [])}
    sent_since_pause = 0

    if start_id is not None:
        cursor = max(start_id - 1, 0)
        skip = 0

    await _save_state(running=True, completed=False, error="", last_id=cursor, api_skip=skip)
    try:
        while True:
            page = await _fetch_page(skip)
            if page is None:
                await _save_state(running=False, error="Waifu API was unavailable after retries.")
                return
            if not page:
                await _save_state(running=False, completed=True, error="")
                return

            # The API is expected to return ascending IDs. Sorting each page
            # also makes a partially unordered response safe to resume.
            page = sorted(page, key=lambda item: _card_id(item) or 0)
            for card in page:
                card_id = _card_id(card)
                if card_id is None:
                    await backupdb.update_one(
                        {"_id": STATE_ID},
                        {"$inc": {"skipped_count": 1}},
                        upsert=True,
                    )
                    continue
                if card_id <= cursor or str(card_id) in backed_up:
                    cursor = max(cursor, card_id)
                    await _save_state(last_id=cursor)
                    continue

                image = _photo(card)
                if not image:
                    cursor = max(cursor, card_id)
                    await backupdb.update_one(
                        {"_id": STATE_ID},
                        {"$set": {"last_id": cursor, "running": True}, "$inc": {"skipped_count": 1}},
                        upsert=True,
                    )
                    backed_up.add(str(card_id))
                    await backupdb.update_one(
                        {"_id": STATE_ID},
                        {"$addToSet": {"backed_up_ids": str(card_id)}},
                        upsert=True,
                    )
                    continue

                try:
                    await _send_photo_with_retry(client, channel_id, card, card_id)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    LOGGER.exception("Backup failed on card %s: %s", card_id, exc)
                    await backupdb.update_one(
                        {"_id": STATE_ID},
                        {"$set": {"running": False, "error": f"Card {card_id} failed: {exc}"}, "$inc": {"failed_count": 1}},
                        upsert=True,
                    )
                    return

                cursor = max(cursor, card_id)
                backed_up.add(str(card_id))
                sent_since_pause += 1
                await _mark_sent(card_id, cursor, skip)
                if sent_since_pause >= PAUSE_AFTER_PHOTOS:
                    await asyncio.sleep(PAUSE_SECONDS)
                    sent_since_pause = 0

            skip += len(page)
            await _save_state(api_skip=skip, last_id=cursor, running=True)
    except asyncio.CancelledError:
        await _save_state(running=False, error="Stopped by owner.")
        raise
    except Exception as exc:
        LOGGER.exception("Backup worker crashed: %s", exc)
        await _save_state(running=False, error=str(exc))


async def _start_backup(client: Client, message: Message, start_id: int | None) -> None:
    global _backup_task
    channel_id = await _get_backup_channel()
    if not channel_id:
        return await message.reply_text(
            "❌ No backup channel is configured. In owner DM, send:\n"
            "<code>/setbackupchannel -100xxxxxxxxxx</code>",
            parse_mode=enums.ParseMode.HTML,
        )
    valid, detail = await _validate_channel(client, channel_id)
    if not valid:
        return await message.reply_text(f"❌ Backup channel is not ready: {detail}")
    if _backup_task and not _backup_task.done():
        return await message.reply_text("⏳ Card backup is already running. Use /backupstatus.")

    _backup_task = asyncio.create_task(_backup_worker(client, start_id))
    await message.reply_text(
        "✅ Backup started in the background. Use /backupstatus to monitor it."
    )


@app.on_message(filters.command("setbackupchannel") & OWNER_FILTER & filters.private)
async def set_backup_channel_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "📡 Send the channel ID in this format:\n<code>/setbackupchannel -100xxxxxxxxxx</code>",
            parse_mode=enums.ParseMode.HTML,
        )
    try:
        channel_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Channel ID must be a number, for example -1001234567890.")

    valid, detail = await _validate_channel(client, channel_id)
    if not valid:
        return await message.reply_text(f"❌ {detail}")
    await onoffdb.update_one(
        {"key": CHANNEL_KEY},
        {"$set": {"key": CHANNEL_KEY, "value": channel_id, "owner_id": config.OWNER_ID}},
        upsert=True,
    )
    await message.reply_text(
        f"✅ Backup channel connected: <b>{escape(str(detail))}</b>\n"
        f"<code>{channel_id}</code>\n\n"
        "The bot will send each card with its image and information caption.",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("backupcards") & OWNER_FILTER)
async def backup_cards_handler(client: Client, message: Message):
    start_id = None
    if len(message.command) > 1:
        try:
            start_id = int(message.command[1])
            if start_id < 1:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ Usage: <code>/backupcards</code> or <code>/backupcards 1</code>", parse_mode=enums.ParseMode.HTML)
    await _start_backup(client, message, start_id)


@app.on_message(filters.command("backupstatus") & OWNER_FILTER)
async def backup_status_handler(client: Client, message: Message):
    state = await _get_state()
    active = bool(_backup_task and not _backup_task.done())
    channel_id = await _get_backup_channel()
    if active:
        status = "RUNNING"
    elif state.get("completed"):
        status = "COMPLETED"
    elif state.get("last_id", 0) or state.get("api_skip", 0):
        status = "RESUMABLE"
    else:
        status = "STOPPED"
    error = state.get("error") or "None"
    await message.reply_text(
        "<b>📦 API card backup status</b>\n\n"
        f"Status: <code>{status}</code>\n"
        f"Channel: <code>{channel_id or 'Not configured'}</code>\n"
        f"Last ID: <code>{state.get('last_id', 0)}</code>\n"
        f"Sent: <code>{state.get('sent_count', 0)}</code>\n"
        f"Skipped: <code>{state.get('skipped_count', 0)}</code>\n"
        f"Failed: <code>{state.get('failed_count', 0)}</code>\n"
        f"Error: <code>{escape(str(error))[:300]}</code>",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(filters.command("backupstop") & OWNER_FILTER)
async def backup_stop_handler(client: Client, message: Message):
    global _backup_task
    if not _backup_task or _backup_task.done():
        await _save_state(running=False, error="Stopped by owner.")
        return await message.reply_text("ℹ️ No active card backup is running.")

    _backup_task.cancel()
    try:
        await _backup_task
    except asyncio.CancelledError:
        pass
    finally:
        _backup_task = None
    await _save_state(running=False, completed=False, error="Stopped by owner.")
    await message.reply_text("🛑 Card backup stopped. You can resume with /backupcards.")
