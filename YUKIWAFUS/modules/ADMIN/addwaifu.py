from datetime import datetime
from html import escape
from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import collectiondb  # ✅ MongoDB တိုက်ရိုက်

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

@app.on_message(filters.command("addwaifu") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def addwaifu_handler(client: Client, message: Message):
    user = message.from_user
    args_raw = " ".join(message.command[1:]).strip()
    parts = [p.strip() for p in args_raw.split("|")]

    # ── PHOTO REPLY MODE (Telegram File ID နဲ့ တိုက်ရိုက်သိမ်းမယ်) ───────────
    if message.reply_to_message and message.reply_to_message.photo:
        if len(parts) < 2:
            return await message.reply_text(
                "Usage (reply to image):\n<code>/addwaifu Name | Rarity | [EventTag]</code>",
                parse_mode=enums.ParseMode.HTML
            )
        name = parts[0]
        rarity = parts[1].capitalize()
        event_tag = parts[2] if len(parts) > 2 else "Standard"

        processing = await message.reply_text("⏳ Processing photo...")
        try:
            photo = message.reply_to_message.photo
            file_id = photo.file_id
            
            # ✅ Telegram file ID ကို URL ပုံစံပြောင်းပြီး img_url အဖြစ် သိမ်းမယ်
            img_url = f"tg://file?id={file_id}"
            
            await processing.delete()
        except Exception as e:
            return await processing.edit_text(f"❌ Error: {e}")

    # ── NORMAL MODE (URL တိုက်ရိုက်ပေးရင်) ──────────────────────────────────
    else:
        if len(parts) < 3:
            return await message.reply_text(
                "Usage:\n<code>/addwaifu Name | img_url | Rarity | [EventTag]</code>",
                parse_mode=enums.ParseMode.HTML
            )
        name = parts[0]
        img_url = parts[1]
        rarity = parts[2].capitalize()
        event_tag = parts[3] if len(parts) > 3 else "Standard"

    # ── Validation ──────────────────────────────────────────────────────────────
    if rarity not in VALID_RARITIES:
        return await message.reply_text(
            f"❌ Invalid rarity: <b>{rarity}</b>\nValid: {', '.join(VALID_RARITIES)}",
            parse_mode=enums.ParseMode.HTML
        )
    if img_url and not img_url.startswith(("http://", "https://")) and not img_url.startswith("tg://"):
        return await message.reply_text("❌ Invalid image URL/File ID!")

    # ── CHECK DUPLICATE (MongoDB တိုက်ရိုက်) ──────────────────────────────
    existing = await collectiondb.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}})
    if existing:
        return await message.reply_text(
            f"⚠️ <b>{escape(name)}</b> already exists in database!",
            parse_mode=enums.ParseMode.HTML
        )

    # ── SAVE TO MONGODB DIRECTLY (API မသုံးတော့ဘူး) ────────────────────────
    processing = await message.reply_text("⏳ Saving waifu to database...")
    try:
        doc = {
            "name": name,
            "img_url": img_url,
            "rarity": rarity,
            "event_tag": event_tag,
            "source_message_id": message.id,
            "added_by": user.first_name,
            "Date": datetime.utcnow().strftime("%d/%m/%Y")
        }
        await collectiondb.insert_one(doc)
        await processing.delete()

        # ── Success reply ──────────────────────────────────────────────────────
        emoji = RARITY_EMOJI.get(rarity, "◈")
        await message.reply_photo(
            photo=img_url,
            caption=f"✅ <b>Waifu Added!</b>\n\n📛 <b>{escape(name)}</b>\n{emoji} {rarity} • 🏷 {event_tag}",
            parse_mode=enums.ParseMode.HTML
        )

        # ── Log to channel ─────────────────────────────────────────────────────
        try:
            log_caption = build_log_caption(
                name=name,
                rarity=rarity,
                event_tag=event_tag,
                img_url=img_url,
                added_by_name=user.first_name,
                added_by_id=user.id,
                source_msg_id=message.id,
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
