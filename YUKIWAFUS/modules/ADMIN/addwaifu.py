from datetime import datetime
from html import escape
from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import collectiondb  # ✅ ဒီ line ရှိနေရမယ်

log = LOGGER

# ... (ကျန်တဲ့ Code) ...

@app.on_message(filters.command("addwaifu") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def addwaifu_handler(client: Client, message: Message):
    # ... (အစပိုင်း) ...

    # ── PHOTO REPLY MODE (Telegram File ID နဲ့ တိုက်ရိုက်သိမ်းမယ်) ───────────
    if message.reply_to_message and message.reply_to_message.photo:
        # ... (photo က download လုပ်ပြီး img_url ရယူမယ်) ...

    # ── NORMAL MODE (URL တိုက်ရိုက်ပေးရင်) ──────────────────────────────────
    else:
        # ... (URL ကို ယူမယ်) ...

    # ── Validation ──────────────────────────────────────────────────────────────
    # ... (rarity နဲ့ URL ကို စစ်မယ်) ...

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
        await collectiondb.insert_one(doc)  # ✅ ဒီ line ကို run သွားမယ်
        await processing.delete()

        # ... (Success reply နဲ့ Log ပို့မယ်) ...

    except Exception as e:
        await processing.edit_text(f"❌ Failed to save waifu: {e}")  # ✅ Error ကို ပြန်ပြမယ်
