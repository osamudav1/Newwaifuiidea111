from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import onoffdb

WELCOME_KEY = "welcome_photo"
ADMIN_IDS = {int(user_id) for user_id in (config.SUDO_USERS + [config.OWNER_ID]) if int(user_id) > 0}


def _is_admin(message: Message) -> bool:
    user = message.from_user
    return bool(user and user.id in ADMIN_IDS)


async def _current_photo():
    try:
        override = await onoffdb.find_one({"key": WELCOME_KEY})
        if override is not None:
            value = str(override.get("value", "")).strip()
            if value.lower() in {"", "disabled", "none", "off"}:
                return None
            return value
    except Exception as exc:
        LOGGER.exception("Welcome photo lookup failed: %s", exc)
    return None


@app.on_message(filters.command(["setwelcome", "addwelcome", "setwelcomephoto", "welcomephoto"]))
async def set_welcome_photo(client: Client, message: Message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Only the owner or sudo users can change the welcome photo.")

    source = message.reply_to_message or message
    photo = getattr(source, "photo", None)
    if not photo:
        return await message.reply_text(
            "📷 Photo တစ်ပုံကို reply လုပ်ပြီး "
            "<code>/setwelcome</code> ပို့ပါ။\n\n"
            "အသုံးပြုပုံ: photo ကို reply → /setwelcome",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        await onoffdb.update_one(
            {"key": WELCOME_KEY},
            {"$set": {"value": photo.file_id, "updated_by": message.from_user.id}},
            upsert=True,
        )
        await message.reply_text(
            "✅ Welcome photo အသစ်ကို သိမ်းပြီးပါပြီ။ နောက်တစ်ကြိမ် <code>/start</code> မှာ အသစ်ကို သုံးပါမယ်။",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as exc:
        LOGGER.exception("Welcome photo save failed: %s", exc)
        await message.reply_text("❌ Welcome photo သိမ်းမရပါ။ Database ကို စစ်ဆေးပါ။")


@app.on_message(filters.command(["delwelcome", "deletewelcome", "removewelcome"]))
async def delete_welcome_photo(client: Client, message: Message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Only the owner or sudo users can change the welcome photo.")
    try:
        await onoffdb.update_one(
            {"key": WELCOME_KEY},
            {"$set": {"value": "disabled", "updated_by": message.from_user.id}},
            upsert=True,
        )
        await message.reply_text(
            "🗑 Welcome photo ကို ဖျက်ထားပါပြီ။ <code>/start</code> မှာ photo မပါဘဲ text panel ပြပါမယ်။",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as exc:
        LOGGER.exception("Welcome photo delete failed: %s", exc)
        await message.reply_text("❌ Welcome photo ဖျက်မရပါ။ Database ကို စစ်ဆေးပါ။")


@app.on_message(filters.command(["resetwelcome", "defaultwelcome"]))
async def reset_welcome_photo(client: Client, message: Message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Only the owner or sudo users can change the welcome photo.")
    try:
        await onoffdb.delete_one({"key": WELCOME_KEY})
        await message.reply_text(
            "♻️ Welcome photo ကို default config photo သို့ reset လုပ်ပြီးပါပြီ။",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception as exc:
        LOGGER.exception("Welcome photo reset failed: %s", exc)
        await message.reply_text("❌ Welcome photo reset မလုပ်နိုင်ပါ။ Database ကို စစ်ဆေးပါ။")


@app.on_message(filters.command(["welcome", "welcomepreview"]))
async def preview_welcome_photo(client: Client, message: Message):
    if not _is_admin(message):
        return await message.reply_text("⛔ Only the owner or sudo users can view the welcome photo.")
    photo = await _current_photo()
    if photo:
        return await message.reply_photo(photo=photo, caption="🖼 Current custom welcome photo")
    return await message.reply_text(
        "ℹ️ Custom welcome photo မသတ်မှတ်ထားပါ။ <code>/start</code> မှာ config default photo သုံးပါမယ်။",
        parse_mode=enums.ParseMode.HTML,
    )
