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

# One pending wizard per admin and private chat. The Telegram file_id is kept so
# no external image URL is required.
_PENDING: dict[tuple[int, int], dict] = {}


def _key(message: Message) -> tuple[int, int]:
    return message.chat.id, message.from_user.id


def _clean_text(message: Message) -> str:
    return (message.text or "").strip()


def build_log_caption(name, rarity, event_tag, img_url, added_by_name, added_by_id):
    emoji = RARITY_EMOJI.get(rarity, "◈")
    now = datetime.utcnow().strftime("%d %b %Y • %H:%M UTC")
    return (
        "<blockquote>🌸 <b>New Waifu Added!</b></blockquote>\n\n"
        f"📛 <b>Name:</b> {escape(name)}\n"
        f"{emoji} <b>Rarity:</b> {rarity}\n"
        f"🏷 <b>Tag:</b> {escape(event_tag)}\n"
        f"🖼 <b>Image:</b> <a href='{escape(str(img_url))}'>View</a>\n\n"
        f"<blockquote>👤 <b>Added by:</b> <a href='tg://user?id={added_by_id}'>{escape(added_by_name)}</a>\n"
        f"🕐 <b>Time:</b> {now}</blockquote>"
    )


async def _ask_name(message: Message):
    await message.reply_text(
        "📝 <b>Step 1/3 — Send the waifu name.</b>\n\n"
        "Example: <code>Rem</code>\n"
        "Send <code>/cancel</code> to stop.",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )


async def _ask_rarity(message: Message):
    valid = ", ".join(VALID_RARITIES)
    await message.reply_text(
        "🌟 <b>Step 2/3 — Send the rarity.</b>\n\n"
        f"Choose one: <code>{valid}</code>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )


async def _ask_event(message: Message):
    await message.reply_text(
        "🏷 <b>Step 3/3 — Send the event/tag.</b>\n\n"
        "Example: <code>Re:Zero</code>\n"
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
        f"📛 <b>Name:</b> {escape(data['name'])}\n"
        f"🌟 <b>Rarity:</b> {data['rarity']}\n"
        f"🏷 <b>Event/Tag:</b> {escape(data['event_tag'])}\n\n"
        "Press <b>Confirm</b> to save or <b>Cancel</b> to discard.",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
    )


# ── STEP 1: Photo sent by Owner/Sudo ───────────────────────────────────────────
@app.on_message(filters.photo & ADMIN_FILTER & filters.private)
async def photo_add_handler(client: Client, message: Message):
    if message.caption:
        # Keep caption mode for backward compatibility.
        return await auto_addwaifu_handler(client, message)

    _PENDING[_key(message)] = {
        "img_url": message.photo.file_id,
        "step": "name",
        "created_at": time.monotonic(),
    }
    await _ask_name(message)


# ── STEP-BY-STEP TEXT WIZARD ────────────────────────────────────────────────────
@app.on_message(filters.text & ADMIN_FILTER & filters.private)
async def addwaifu_wizard_handler(client: Client, message: Message):
    key = _key(message)
    data = _PENDING.get(key)
    if not data:
        return
    if time.monotonic() - data.get("created_at", 0) > 900:
        _PENDING.pop(key, None)
        return await message.reply_text("⌛ This add-waifu session expired. Send a new photo to start again.")

    text = _clean_text(message)
    if text.lower() in {"/cancel", "cancel"}:
        _PENDING.pop(key, None)
        return await message.reply_text("❌ Add-waifu process cancelled.")

    if text.startswith("/"):
        return

    if data["step"] == "name":
        if len(text) < 1 or len(text) > 100:
            return await message.reply_text("❌ Name must be between 1 and 100 characters.")
        data["name"] = text
        data["step"] = "rarity"
        return await _ask_rarity(message)

    if data["step"] == "rarity":
        rarity_key = re.sub(r"\s+", "", text).lower()
        rarity = next((r for r in VALID_RARITIES if r.lower() == rarity_key), None)
        if not rarity:
            return await message.reply_text(
                f"❌ Invalid rarity. Choose one: {', '.join(VALID_RARITIES)}"
            )
        data["rarity"] = rarity
        data["step"] = "event_tag"
        return await _ask_event(message)

    if data["step"] == "event_tag":
        data["event_tag"] = "Standard" if text in {"", "-", "skip", "Skip"} else text[:100]
        data["step"] = "confirm"
        return await _show_confirmation(message, data)


@app.on_callback_query(filters.regex(r"^awf:(confirm|cancel):(\d+)$"))
async def addwaifu_confirm_callback(client: Client, callback: CallbackQuery):
    action, user_id = callback.data.split(":")[1:]
    user_id = int(user_id)
    if callback.from_user.id != user_id:
        return await callback.answer("This confirmation is not for you.", show_alert=True)

    key = (callback.message.chat.id, user_id)
    data = _PENDING.get(key)
    if not data or time.monotonic() - data.get("created_at", 0) > 900:
        _PENDING.pop(key, None)
        return await callback.answer("This add-waifu session has expired.", show_alert=True)

    if action == "cancel":
        _PENDING.pop(key, None)
        await callback.message.edit_text("❌ Add-waifu process cancelled.")
        return await callback.answer()

    _PENDING.pop(key, None)
    await callback.answer("Saving waifu...")
    await save_waifu(
        client,
        callback.message,
        data["name"],
        data["img_url"],
        data["rarity"],
        data["event_tag"],
        actor=callback.from_user,
        reply_target=callback.message,
    )


# ── CORE SAVE FUNCTION ─────────────────────────────────────────────────────────
async def save_waifu(
    client,
    message,
    name,
    img_url,
    rarity,
    event_tag,
    *,
    actor=None,
    reply_target=None,
):
    user = actor or message.from_user
    target = reply_target or message

    try:
        existing = await waifudb.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    except Exception as exc:
        LOGGER.exception("/addwaifu duplicate check failed: %s", exc)
        return await target.reply_text("❌ Waifu database is unavailable. Please try again later.")

    if existing:
        return await target.reply_text(
            f"⚠️ <b>{escape(name)}</b> already exists in database!",
            parse_mode=enums.ParseMode.HTML,
        )

    processing = await target.reply_text("⏳ Saving waifu to database...")
    try:
        doc = {
            "name": name,
            "img_url": img_url,
            "rarity": rarity,
            "event_tag": event_tag,
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
                f"📛 <b>{escape(name)}</b>\n"
                f"{emoji} {rarity} • 🏷 {escape(event_tag)}"
            ),
            parse_mode=enums.ParseMode.HTML,
        )

        if config.LOG_CHANNEL:
            try:
                await client.send_photo(
                    chat_id=config.LOG_CHANNEL,
                    photo=img_url,
                    caption=build_log_caption(
                        name, rarity, event_tag, img_url,
                        user.first_name, user.id,
                    ),
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


# ── Legacy direct command (kept for admins who still need it) ───────────────────
@app.on_message(filters.command("addwaifu") & ADMIN_FILTER)
async def addwaifu_cmd_handler(client: Client, message: Message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply_text(
            "📷 Send a photo to start the step-by-step add-waifu process.\n"
            "Then reply to the bot's questions one by one.\n\n"
            "Send <code>/cancel</code> at any time to stop.",
            parse_mode=enums.ParseMode.HTML,
        )

    parts = [p.strip() for p in args[1].split("|")]
    if len(parts) < 3:
        return await message.reply_text("❌ Use: Name | Image URL | Rarity | EventTag")

    name, img_url, rarity = parts[:3]
    rarity = next((r for r in VALID_RARITIES if r.lower() == rarity.lower()), None)
    event_tag = parts[3] if len(parts) > 3 else "Standard"
    if not rarity:
        return await message.reply_text(f"❌ Invalid rarity. Valid: {', '.join(VALID_RARITIES)}")
    await save_waifu(client, message, name, img_url, rarity, event_tag)


# ── Caption mode ────────────────────────────────────────────────────────────────
async def auto_addwaifu_handler(client: Client, message: Message):
    parts = [p.strip() for p in (message.caption or "").split("|")]
    if len(parts) < 2:
        return await message.reply_text(
            "❌ Caption format: <code>Name | Rarity | EventTag</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    name = parts[0]
    rarity = next((r for r in VALID_RARITIES if r.lower() == parts[1].lower()), None)
    event_tag = parts[2] if len(parts) > 2 else "Standard"
    if not rarity:
        return await message.reply_text(
            f"❌ Invalid rarity. Valid: {', '.join(VALID_RARITIES)}"
        )
    await save_waifu(client, message, name, message.photo.file_id, rarity, event_tag)
