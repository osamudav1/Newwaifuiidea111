import re
import time
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
OWNER_FILTER = filters.user(config.OWNER_ID)
_PENDING: dict[tuple[int, int], dict] = {}
SESSION_TTL = 900


def _key(message: Message) -> tuple[int, int]:
    return message.chat.id, message.from_user.id


def _is_skip(value: str) -> bool:
    return value.strip().lower() in {"skip", "/skip"}


def _normal_rarity(value: str) -> str | None:
    compact = re.sub(r"\s+", "", value).lower()
    return next((item for item in VALID_RARITIES if item.lower() == compact), None)


def _character(card: dict) -> str:
    return str(card.get("character_name") or card.get("name") or "Unknown")


def _anime(card: dict) -> str:
    return str(card.get("anime_name") or card.get("anime") or "Unknown")


def _rarity(card: dict) -> str:
    return str(card.get("rarity") or "Common")


def _event(card: dict) -> str:
    return str(card.get("event") or card.get("event_tag") or "Standard")


def _photo(card: dict) -> str | None:
    for field in ("img_url", "image", "photo"):
        if card.get(field):
            return str(card[field])
    return None


def _skip_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭ Skip", callback_data=f"edit_skip:{user_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"edit_cancel:{user_id}"),
    ]])


async def _ask_step(message: Message, data: dict) -> None:
    card = data["original"]
    step = data["step"]
    if step == "photo":
        prompt = "🖼 <b>Step 1/5 — New photo</b>"
        details = "Send a new photo, or press <b>Skip</b> to keep the current photo."
        current = _photo(card) or "No image"
    elif step == "name":
        prompt = "📛 <b>Step 2/5 — Character name</b>"
        details = "Example: <code>Rem</code>"
        current = _character(card)
    elif step == "rarity":
        prompt = "🌟 <b>Step 3/5 — Rarity</b>"
        details = f"Choose one: <code>{', '.join(VALID_RARITIES)}</code>"
        current = _rarity(card)
    elif step == "anime_name":
        prompt = "🎬 <b>Step 4/5 — Anime name</b>"
        details = "Example: <code>Naruto</code>"
        current = _anime(card)
    else:
        prompt = "🏷 <b>Step 5/5 — Event</b>"
        details = "Example: <code>Summer Event</code>"
        current = _event(card)

    await message.reply_text(
        f"{prompt}\n\n<b>Current:</b> <code>{escape(current[:150])}</code>\n{details}\n"
        "Send <code>Skip</code> or press the button to keep the current value.\n"
        "Send <code>/cancel</code> to stop.",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=_skip_keyboard(message.from_user.id),
    )


async def _save_edit(message: Message, data: dict) -> None:
    updates = data["updates"]
    if not updates:
        _PENDING.pop(_key(message), None)
        return await message.reply_text("ℹ️ No fields changed. The card remains unchanged.")

    try:
        result = await waifudb.update_one(data["query"], {"$set": updates})
    except Exception as exc:
        LOGGER.exception("/edit update failed: %s", exc)
        return await message.reply_text("❌ Could not update the card database. Please try again.")

    if getattr(result, "matched_count", 1) == 0:
        _PENDING.pop(_key(message), None)
        return await message.reply_text("❌ This card no longer exists. Edit cancelled.")

    card = dict(data["original"])
    card.update(updates)
    _PENDING.pop(_key(message), None)
    emoji = RARITY_EMOJI.get(_rarity(card), "◈")
    caption = (
        "✅ <b>Card replaced successfully!</b>\n\n"
        f"🆔 <b>ID:</b> <code>{data['card_id']}</code>\n"
        f"📛 <b>Character:</b> {escape(_character(card))}\n"
        f"🎬 <b>Anime:</b> {escape(_anime(card))}\n"
        f"{emoji} <b>Rarity:</b> {escape(_rarity(card))}\n"
        f"🏷 <b>Event:</b> {escape(_event(card))}"
    )
    photo = _photo(card)
    if photo:
        try:
            return await message.reply_photo(photo, caption=caption, parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass
    await message.reply_text(caption, parse_mode=enums.ParseMode.HTML)


async def _advance(message: Message, data: dict, value: str | None = None) -> None:
    step = data["step"]
    if value is not None:
        if step == "photo":
            data["updates"]["img_url"] = value
            if "image" in data["original"]:
                data["updates"]["image"] = value
            if "photo" in data["original"]:
                data["updates"]["photo"] = value
        elif step == "name":
            data["updates"].update(name=value, character_name=value)
        elif step == "rarity":
            data["updates"]["rarity"] = value
        elif step == "anime_name":
            data["updates"]["anime_name"] = value
        elif step == "event":
            data["updates"].update(event=value, event_tag=value)

    next_step = {
        "photo": "name",
        "name": "rarity",
        "rarity": "anime_name",
        "anime_name": "event",
        "event": None,
    }[step]
    if next_step is None:
        return await _save_edit(message, data)
    data["step"] = next_step
    await _ask_step(message, data)


@app.on_message(filters.command("edit") & OWNER_FILTER & filters.private)
async def edit_cmd_handler(client: Client, message: Message):
    args = message.command or []
    if len(args) != 2 or not args[1].isdigit():
        return await message.reply_text(
            "🛠 <b>Usage:</b> <code>/edit &lt;card_id&gt;</code>\nExample: <code>/edit 1846</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    card_id = int(args[1])
    key = _key(message)
    query = {"$or": [{"waifu_id": card_id}, {"id": card_id}]}
    try:
        card = await waifudb.find_one(query)
    except Exception as exc:
        LOGGER.exception("/edit lookup failed: %s", exc)
        return await message.reply_text("❌ Waifu database is unavailable. Please try again later.")
    if not card:
        return await message.reply_text(
            f"❌ No card found with ID <code>{card_id}</code>.",
            parse_mode=enums.ParseMode.HTML,
        )

    _PENDING[key] = {
        "card_id": card_id,
        "query": query,
        "original": card,
        "updates": {},
        "step": "photo",
        "created_at": time.monotonic(),
    }
    await message.reply_text(
        f"🛠 <b>Editing card <code>{card_id}</code></b>\n"
        "This replaces fields on the existing card and keeps the same ID.",
        parse_mode=enums.ParseMode.HTML,
    )
    await _ask_step(message, _PENDING[key])


@app.on_message(filters.photo & OWNER_FILTER & filters.private)
async def edit_photo_handler(client: Client, message: Message):
    data = _PENDING.get(_key(message))
    if not data or data["step"] != "photo":
        return
    if time.monotonic() - data["created_at"] > SESSION_TTL:
        _PENDING.pop(_key(message), None)
        return await message.reply_text("⌛ This edit session expired. Send `/edit <id>` again.")
    await _advance(message, data, message.photo.file_id)


@app.on_message(filters.text & OWNER_FILTER & filters.private)
async def edit_wizard_handler(client: Client, message: Message):
    key = _key(message)
    data = _PENDING.get(key)
    if not data:
        return
    if time.monotonic() - data["created_at"] > SESSION_TTL:
        _PENDING.pop(key, None)
        return await message.reply_text("⌛ This edit session expired. Send `/edit <id>` again.")

    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "cancel"}:
        _PENDING.pop(key, None)
        return await message.reply_text("❌ Card edit cancelled. The existing card was not changed.")
    if text.startswith("/") and not _is_skip(text):
        return
    if _is_skip(text):
        return await _advance(message, data)

    step = data["step"]
    if step == "photo":
        return await message.reply_text("❌ Please send a photo or press Skip.")
    if step == "name":
        if not 1 <= len(text) <= 100:
            return await message.reply_text("❌ Character name must be between 1 and 100 characters.")
        return await _advance(message, data, text)
    if step == "rarity":
        rarity = _normal_rarity(text)
        if not rarity:
            return await message.reply_text(f"❌ Invalid rarity. Choose one: {', '.join(VALID_RARITIES)}")
        return await _advance(message, data, rarity)
    if step == "anime_name":
        if not 1 <= len(text) <= 150:
            return await message.reply_text("❌ Anime name must be between 1 and 150 characters.")
        return await _advance(message, data, text)
    if step == "event":
        if not 1 <= len(text) <= 100:
            return await message.reply_text("❌ Event must be between 1 and 100 characters.")
        return await _advance(message, data, text)


@app.on_callback_query(filters.regex(r"^edit_(skip|cancel):(\d+)$"))
async def edit_skip_callback(client: Client, callback: CallbackQuery):
    action, raw_user_id = callback.data.split(":", 1)
    user_id = int(raw_user_id)
    if callback.from_user.id != user_id or user_id != config.OWNER_ID:
        return await callback.answer("This edit session is not for you.", show_alert=True)

    key = (callback.message.chat.id, user_id)
    data = _PENDING.get(key)
    if not data:
        return await callback.answer("This edit session has expired.", show_alert=True)
    if action == "cancel":
        _PENDING.pop(key, None)
        await callback.answer("Edit cancelled.")
        return await callback.message.edit_text("❌ Card edit cancelled. The existing card was not changed.")

    await callback.answer("Skipped")
    await _advance(callback.message, data)


async def has_edit_session(key: tuple[int, int]) -> bool:
    return key in _PENDING


__all__ = ["has_edit_session"]

