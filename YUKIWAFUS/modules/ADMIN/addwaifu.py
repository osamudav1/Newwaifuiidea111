from datetime import datetime
from html import escape
import aiohttp
from pyrogram import Client, enums, filters
from pyrogram.types import Message
import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.utils.api import add_waifu, find_waifu

log = LOGGER

RARITY_EMOJI = {
    "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵",
    "Epic": "🟣", "Legendary": "🟡", "Mythic": "🔴",
}
VALID_RARITIES = list(RARITY_EMOJI.keys())

# ── Catbox upload helper (photo reply mode အတွက်) ──────────────────────────
async def upload_to_catbox(data: bytes, filename: str) -> str | None:
    CATBOX_URL = "https://catbox.moe/user/api.php"
    CATBOX_HASH = getattr(config, "CATBOX_HASH", "")
    try:
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        if CATBOX_HASH: form.add_field("userhash", CATBOX_HASH)
        form.add_field("fileToUpload", data, filename=filename, content_type="image/jpeg")
        async with aiohttp.ClientSession() as session:
            async with session.post(CATBOX_URL, data=form) as resp:
                if resp.status == 200:
                    url = await resp.text()
                    if url.startswith("https://"): return url.strip()
        return None
    except Exception as e:
        LOGGER.error(f"Catbox upload failed: {e}")
        return None

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

    # ── PHOTO REPLY MODE (ပုံကို reply လုပ်ပြီး command ပေးရင်) ──────────────
    if message.reply_to_message and message.reply_to_message.photo:
        if len(parts) < 2:
            return await message.reply_text("Usage (reply to image):\n<code>/addwaifu Name | Rarity | [EventTag]</code>", parse_mode=enums.ParseMode.HTML)
        name = parts[0]
        rarity = parts[1].capitalize()
        event_tag = parts[2] if len(parts) > 2 else "Standard"

        processing = await message.reply_text("⏳ Downloading & uploading photo...")
        try:
            photo = message.reply_to_message.photo
            file = await client.download_media(photo.file_id, in_memory=True)
            file.seek(0)
            data = file.read()
            await processing.edit_text("⏳ Uploading to Catbox...")
            img_url = await upload_to_catbox(data, f"waifu_{message.id}.jpg")
            if not img_url:
                return await processing.edit_text("❌ Upload failed. Try with direct URL instead.")
            await processing.delete()
        except Exception as e:
            return await processing.edit_text(f"❌ Error: {e}")

    # ── NORMAL MODE (URL တိုက်ရိုက်ပေးရင်) ──────────────────────────────────
    else:
        if len(parts) < 3:
            return await message.reply_text("Usage:\n<code>/addwaifu Name | img_url | Rarity | [EventTag]</code>", parse_mode=enums.ParseMode.HTML)
        name = parts[0]
        img_url = parts[1]
        rarity = parts[2].capitalize()
        event_tag = parts[3] if len(parts) > 3 else "Standard"

    # ── Validation ──────────────────────────────────────────────────────────────
    if rarity not in VALID_RARITIES:
        return await message.reply_text(f"❌ Invalid rarity: <b>{rarity}</b>\nValid: {', '.join(VALID_RARITIES)}", parse_mode=enums.ParseMode.HTML)
    if img_url and not img_url.startswith(("http://", "https://")):
        return await message.reply_text("❌ Invalid image URL!")

    existing = await find_waifu(name)
    if existing:
        exact = [w for w in existing if w["name"].lower() == name.lower()]
        if exact:
            return await message.reply_text(f"⚠️ <b>{escape(name)}</b> already exists in database!", parse_mode=enums.ParseMode.HTML)

    # ── Add via API ───────────────────────────────────────────────────────────
    processing = await message.reply_text("⏳ Adding waifu via API...")
    result = await add_waifu(
        api_key=config.WAIFU_API_KEY,
        name=name,
        img_url=img_url,
        rarity=rarity,
        event_tag=event_tag,
        source_message_id=message.id,
        added_by=user.first_name,
    )

    if not result:
        return await processing.edit_text("❌ Failed to add waifu. Check API or try again.")

    await processing.delete()
    emoji = RARITY_EMOJI.get(rarity, "◈")
    await message.reply_photo(photo=img_url, caption=f"✅ <b>Waifu Added!</b>\n\n📛 <b>{escape(name)}</b>\n{emoji} {rarity} • 🏷 {event_tag}", parse_mode=enums.ParseMode.HTML)

    try:
        log_caption = build_log_caption(name, rarity, event_tag, img_url, user.first_name, user.id, message.id)
        await client.send_photo(chat_id=config.LOG_CHANNEL, photo=img_url, caption=log_caption, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Logger failed: {e}")
