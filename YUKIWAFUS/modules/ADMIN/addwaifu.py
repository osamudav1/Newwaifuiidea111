import re
import time
from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import waifudb

RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
    "Mythic": "🔴",
}
VALID_RARITIES = tuple(RARITY_EMOJI)
ADMIN_FILTER = filters.user(config.SUDO_USERS + [config.OWNER_ID])
_PENDING: dict[tuple[int, int], dict] = {}
SESSION_TTL = 900


def _key(message: Message) -> tuple[int, int]:
    return message.chat.id, message.from_user.id


def _clean_text(message: Message) -> str:
    return (message.text or "").strip()


def _normal_rarity(value: str) -> str | None:
    compact = re.sub(r"\s+", "", value).lower()
    return next((rarity for rarity in VALID_RARITIES if rarity.lower() == compact), None)


def _event_value(value: str) -> str:
    return "Standard" if value.strip().lower() in {"", "-", "skip", "none"} else value.strip()[:100]


def build_log_caption(name, anime_name, rarity, event, img_url, added_by_name, added_by_id):
    emoji = RARITY_EMOJI.get(rarity, "◈")
    now = datetime.utcnow().strftime("%d %b %Y • %H:%M UTC")
    return (
        "<blockquote>🌸 <b>New Waifu Added!</b></blockquote>\n\n"
        f"📛 <b>Character:</b> {escape(name)}\n"
        f"🎬 <b>Anime:</b> {escape(anime_name)}\n"
        f"{emoji} <b>Rarity:</b> {rarity}\n"
        f"🏷 <b>Event:</b> {escape(event)}\n"
        f"🖼 <b>Image:</b> <a href='{escape(str(img_url))}'>View</a>\n\n"
        f"<blockquote>👤 <b>Added by:</b> <a href='tg://user?id={added_by_id}'>{escape(added_by_name)}</a>\n"
        f"🕐 <b>Time:</b> {now}</blockquote>"
    )


async def _ask_name(message: Message):
    await message.reply_text(
        "📝 <b>Step 1/4 — Character name</b>\n\n"
        "Example: <code>Rem</code>\nSend <code>/cancel</code> to stop.",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )


async def _ask_anime(message: Message):
    await message.reply_text(
        "🎬 <b>Step 2/4 — Anime name</b>\n\n"
        "Example: <code>Re:Zero − Starting Life in Another World</code>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )


async def _ask_rarity(message: Message):
    await message.reply_text(
        "🌟 <b>Step 3/4 — Rarity</b>\n\n"
        f"Choose one: <code>{', '.join(VALID_RARITIES)}</code>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )


async def _ask_event(message: Message):
    await message.reply_text(
        "🏷 <b>Step 4/4 — Event</b>\n\n"
        "Example: <code>Summer Event</code>\n"
        "Send <code>-</code> for Standard.",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )


async def _show_confirmation(message: Message, data: dict):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data=f"awf:confirm:{message.from_user.id}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"awf:cancel:{message.from_user.id}"),
    ]])
    await message.reply_text(
        "<blockquote>📋 <b>Check waifu details</b></blockquote>\n\n"
        f"📛 <b>Character:</b> {escape(data['name'])}\n"
        f"🎬 <b>Anime:</b> {escape(data['anime_name'])}\n"
        f"🌟 <b>Rarity:</b> {data['rarity']}\n"
        f"🏷 <b>Event:</b> {escape(data['event'])}\n\n"
        "Press <b>Confirm</b> to save or <b>Cancel</b> to discard.",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
    )


@app.on_message(filters.photo & ADMIN_FILTER & filters.private)
async def photo_add_handler(client: Client, message: Message):
    if message.caption:
        return await auto_addwaifu_handler(client, message)
    _PENDING[_key(message)] = {
        "img_url": message.photo.file_id,
        "step": "name",
        "created_at": time.monotonic(),
    }
    await message.reply_text("📷 Photo received. Starting add-waifu setup...")
    await _ask_name(message)


@app.on_message(filters.text & ADMIN_FILTER & filters.private)
async def addwaifu_wizard_handler(client: Client, message: Message):
    key = _key(message)
    data = _PENDING.get(key)
    if not data:
        return
    if time.monotonic() - data.get("created_at", 0) > SESSION_TTL:
        _PENDING.pop(key, None)
        return await message.reply_text("⌛ This add-waifu session expired. Send a new photo to start again.")

    text = _clean_text(message)
    if text.lower() in {"/cancel", "cancel"}:
        _PENDING.pop(key, None)
        return await message.reply_text("❌ Add-waifu process cancelled.")
    if text.startswith("/"):
        return

    if data["step"] == "name":
        if not 1 <= len(text) <= 100:
            return await message.reply_text("❌ Character name must be between 1 and 100 characters.")
        data.update(name=text, step="anime_name")
        return await _ask_anime(message)

    if data["step"] == "anime_name":
        if not 1 <= len(text) <= 150:
            return await message.reply_text("❌ Anime name must be between 1 and 150 characters.")
        data.update(anime_name=text, step="rarity")
        return await _ask_rarity(message)

    if data["step"] == "rarity":
        rarity = _normal_rarity(text)
        if not rarity:
            return await message.reply_text(f"❌ Invalid rarity. Choose one: {', '.join(VALID_RARITIES)}")
        data.update(rarity=rarity, step="event")
        return await _ask_event(message)

    if data["step"] == "event":
        data.update(event=_event_value(text), step="confirm")
        return await _show_confirmation(message, data)


@app.on_callback_query(filters.regex(r"^awf:(confirm|cancel):(\d+)$"))
async def addwaifu_confirm_callback(client: Client, callback: CallbackQuery):
    action, user_id = callback.data.split(":")[1:]
    user_id = int(user_id)
    if callback.from_user.id != user_id:
        return await callback.answer("This confirmation is not for you.", show_alert=True)

    key = (callback.message.chat.id, user_id)
    data = _PENDING.get(key)
    if not data or time.monotonic() - data.get("created_at", 0) > SESSION_TTL:
        _PENDING.pop(key, None)
        return await callback.answer("This add-waifu session has expired.", show_alert=True)
    if action == "cancel":
        _PENDING.pop(key, None)
        await callback.message.edit_text("❌ Add-waifu process cancelled.")
        return await callback.answer()

    _PENDING.pop(key, None)
    await callback.answer("Saving waifu...")
    await save_waifu(
        client, callback.message, data["name"], data["anime_name"], data["img_url"],
        data["rarity"], data["event"], actor=callback.from_user, reply_target=callback.message,
    )


async def save_waifu(
    client, message, name, anime_name, img_url, rarity, event,
    *, actor=None, reply_target=None,
):
    user = actor or message.from_user
    target = reply_target or message
    try:
        existing = await waifudb.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    except Exception as exc:
        LOGGER.exception("/addwaifu duplicate check failed: %s", exc)
        return await target.reply_text("❌ Waifu database is unavailable. Please try again later.")
    if existing:
        return await target.reply_text(f"⚠️ <b>{escape(name)}</b> already exists in database!", parse_mode=enums.ParseMode.HTML)

    processing = await target.reply_text("⏳ Saving waifu to database...")
    try:
        doc = {
            "name": name,
            "character_name": name,
            "anime_name": anime_name,
            "img_url": img_url,
            "rarity": rarity,
            "event": event,
            "event_tag": event,
            "added_by": user.first_name,
            "added_by_id": user.id,
            "date": datetime.utcnow().strftime("%d/%m/%Y"),
        }
        await waifudb.insert_one(doc)
        await processing.delete()
        emoji = RARITY_EMOJI.get(rarity, "◈")
        await target.reply_photo(
            photo=img_url,
            caption=(
                f"✅ <b>Waifu Added!</b>\n\n"
                f"📛 <b>Character:</b> {escape(name)}\n"
                f"🎬 <b>Anime:</b> {escape(anime_name)}\n"
                f"{emoji} <b>Rarity:</b> {rarity}\n"
                f"🏷 <b>Event:</b> {escape(event)}"
            ),
            parse_mode=enums.ParseMode.HTML,
        )
        if config.LOG_CHANNEL:
            try:
                await client.send_photo(
                    chat_id=config.LOG_CHANNEL,
                    photo=img_url,
                    caption=build_log_caption(name, anime_name, rarity, event, img_url, user.first_name, user.id),
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception as exc:
                LOGGER.warning("Waifu log send failed: %s", exc)
    except Exception as exc:
        LOGGER.exception("/addwaifu save failed: %s", exc)
        try:
            await processing.edit_text(f"❌ Failed to save waifu: {escape(str(exc))}")
        except Exception:
            pass


@app.on_message(filters.command("addwaifu") & ADMIN_FILTER)
async def addwaifu_cmd_handler(client: Client, message: Message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply_text(
            "📷 Send a photo to start: Character name → Anime name → Rarity → Event → Confirm.",
            parse_mode=enums.ParseMode.HTML,
        )
    parts = [part.strip() for part in args[1].split("|")]
    if len(parts) < 3:
        return await message.reply_text("❌ Use: Name | Image URL | Rarity | Event")

    name, img_url = parts[:2]
    if len(parts) >= 5:
        anime_name, rarity_text, event = parts[2:5]
    else:
        anime_name, rarity_text, event = "Unknown", parts[2], parts[3] if len(parts) > 3 else "Standard"
    rarity = _normal_rarity(rarity_text)
    if not rarity:
        return await message.reply_text(f"❌ Invalid rarity. Valid: {', '.join(VALID_RARITIES)}")
    await save_waifu(client, message, name, anime_name, img_url, rarity, _event_value(event))


async def auto_addwaifu_handler(client: Client, message: Message):
    parts = [part.strip() for part in (message.caption or "").split("|")]
    if len(parts) < 2:
        return await message.reply_text("❌ Caption format: Character | Anime | Rarity | Event", parse_mode=enums.ParseMode.HTML)

    name = parts[0]
    if len(parts) >= 3 and _normal_rarity(parts[1]):
        anime_name, rarity_text, event = "Unknown", parts[1], parts[2] if len(parts) > 2 else "Standard"
    else:
        anime_name = parts[1]
        rarity_text = parts[2] if len(parts) > 2 else ""
        event = parts[3] if len(parts) > 3 else "Standard"
    rarity = _normal_rarity(rarity_text)
    if not rarity:
        return await message.reply_text(f"❌ Invalid rarity. Valid: {', '.join(VALID_RARITIES)}")
    await save_waifu(client, message, name, anime_name, message.photo.file_id, rarity, _event_value(event))
