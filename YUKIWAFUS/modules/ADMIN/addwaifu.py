from datetime import datetime
from html import escape
from pyrogram import Client, enums, filters
from pyrogram.types import Message, ForceReply

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import waifudb

log = LOGGER

RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
    "Mythic": "🔴",
}
VALID_RARITIES = list(RARITY_EMOJI.keys())

def build_log_caption(name, rarity, event_tag, img_url, added_by_name, added_by_id, source_msg_id=0):
    emoji = RARITY_EMOJI.get(rarity, "◈")
    now = datetime.utcnow().strftime("%d %b %Y • %H:%M UTC")
    return (
        f"<blockquote>🌸 <b>New Waifu Added!</b></blockquote>\n\n"
        f"📛 <b>Name:</b> {escape(name)}\n"
        f"{emoji} <b>Rarity:</b> {rarity}\n"
        f"🏷 <b>Tag:</b> {event_tag}\n"
        f"🖼 <b>Image:</b> <a href='{img_url}'>View</a>\n\n"
        f"<blockquote>👤 <b>Added by:</b> <a href='tg://user?id={added_by_id}'>{escape(added_by_name)}</a>\n"
        f"🕐 <b>Time:</b> {now}</blockquote>"
    )

# ── STEP 1: Photo sent by Owner/Sudo ──────────────────────────────────────────
@app.on_message(filters.photo & filters.user(config.SUDO_USERS + [config.OWNER_ID]) & filters.private)
async def photo_add_handler(client: Client, message: Message):
    if message.caption:
        # If caption exists, try to parse it directly
        return await auto_addwaifu_handler(client, message)
    
    # Otherwise, ask for details
    await message.reply_text(
        "📷 <b>Photo Received!</b>\n\n"
        "Please reply to this photo with the waifu details in the following format:\n"
        "<code>Name | Rarity | Source/EventTag</code>\n\n"
        "<b>Example:</b>\n"
        "<code>Rem | Mythic | Re:Zero</code>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ForceReply(selective=True)
    )

# ── STEP 2: Handle Reply with Details ────────────────────────────────────────
@app.on_message(filters.reply & filters.user(config.SUDO_USERS + [config.OWNER_ID]) & filters.private)
async def detail_reply_handler(client: Client, message: Message):
    reply = message.reply_to_message
    
    # Check if the reply is to our bot's message asking for details
    if not reply.photo:
        return

    text = message.text or ""
    parts = [p.strip() for p in text.split("|")]
    
    if len(parts) < 2:
        return # Not the format we want or just a random reply

    name = parts[0]
    rarity = parts[1].capitalize()
    event_tag = parts[2] if len(parts) > 2 else "Standard"

    if rarity not in VALID_RARITIES:
        return await message.reply_text(
            f"❌ Invalid rarity: <b>{rarity}</b>\nValid: {', '.join(VALID_RARITIES)}",
            parse_mode=enums.ParseMode.HTML
        )

    # Process the photo from the replied message
    photo = reply.photo
    file_id = photo.file_id
    img_url = file_id # We store file_id as img_url for bot internal use

    await save_waifu(client, message, name, img_url, rarity, event_tag)

# ── AUTO SAVE (Caption ရှိရင်) ──────────────────────────────────────────
async def auto_addwaifu_handler(client: Client, message: Message):
    user = message.from_user
    photo = message.photo
    file_id = photo.file_id
    img_url = file_id

    caption = message.caption or ""
    parts = [p.strip() for p in caption.split("|")]

    if len(parts) < 2:
        return await message.reply_text(
            "❌ Invalid format in caption!\n"
            "Use: <code>Name | Rarity | EventTag</code>",
            parse_mode=enums.ParseMode.HTML
        )

    name = parts[0]
    rarity = parts[1].capitalize()
    event_tag = parts[2] if len(parts) > 2 else "Standard"

    if rarity not in VALID_RARITIES:
        return await message.reply_text(
            f"❌ Invalid rarity: <b>{rarity}</b>\nValid: {', '.join(VALID_RARITIES)}",
            parse_mode=enums.ParseMode.HTML
        )

    await save_waifu(client, message, name, img_url, rarity, event_tag)

# ── CORE SAVE FUNCTION ───────────────────────────────────────────────────────
async def save_waifu(client, message, name, img_url, rarity, event_tag):
    user = message.from_user
    
    # Check duplicate in waifudb (Master database)
    existing = await waifudb.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
    if existing:
        return await message.reply_text(
            f"⚠️ <b>{escape(name)}</b> already exists in database!",
            parse_mode=enums.ParseMode.HTML
        )

    processing = await message.reply_text("⏳ Saving waifu to database...")
    try:
        # Generate a unique ID for the waifu (optional, but good for referencing)
        # For now, we use what's already in the schema
        doc = {
            "name": name,
            "img_url": img_url,
            "rarity": rarity,
            "event_tag": event_tag,
            "added_by": user.first_name,
            "added_by_id": user.id,
            "date": datetime.utcnow().strftime("%d/%m/%Y")
        }
        await waifudb.insert_one(doc)
        await processing.delete()

        emoji = RARITY_EMOJI.get(rarity, "◈")
        await message.reply_photo(
            photo=img_url,
            caption=f"✅ <b>Waifu Added!</b>\n\n📛 <b>{escape(name)}</b>\n{emoji} {rarity} • 🏷 {event_tag}",
            parse_mode=enums.ParseMode.HTML
        )

        # Log to channel
        if config.LOG_CHANNEL:
            try:
                log_caption = build_log_caption(
                    name=name,
                    rarity=rarity,
                    event_tag=event_tag,
                    img_url=img_url, # Note: if it's a file_id, it might not work as a link in log, but works for send_photo
                    added_by_name=user.first_name,
                    added_by_id=user.id,
                )
                await client.send_photo(
                    chat_id=config.LOG_CHANNEL,
                    photo=img_url,
                    caption=log_caption,
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception as e:
                LOGGER.error(f"Logger failed: {e}")

    except Exception as e:
        await processing.edit_text(f"❌ Failed to save waifu: {e}")

# ── ORIGINAL /addwaifu COMMAND (For URL support) ─────────────────────────
@app.on_message(filters.command("addwaifu") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def addwaifu_cmd_handler(client: Client, message: Message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply_text(
            "<b>Usage:</b>\n"
            "1. Send a photo to the bot.\n"
            "2. Or use: <code>/addwaifu Name | img_url | Rarity | [EventTag]</code>",
            parse_mode=enums.ParseMode.HTML
        )
    
    parts = [p.strip() for p in args[1].split("|")]
    if len(parts) < 3:
        return await message.reply_text("❌ Missing arguments! Name | URL | Rarity required.")
    
    name = parts[0]
    img_url = parts[1]
    rarity = parts[2].capitalize()
    event_tag = parts[3] if len(parts) > 3 else "Standard"
    
    if rarity not in VALID_RARITIES:
        return await message.reply_text(f"❌ Invalid rarity. Valid: {', '.join(VALID_RARITIES)}")

    await save_waifu(client, message, name, img_url, rarity, event_tag)
