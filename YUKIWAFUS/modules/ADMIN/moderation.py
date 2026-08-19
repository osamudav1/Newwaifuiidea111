from pyrogram import Client, filters, enums
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import gbansdb
from YUKIWAFUS.utils.helpers import sc


_ADMIN_IDS = config.SUDO_USERS + [config.OWNER_ID]


def _target_user_id(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    if len(message.command) > 1:
        try:
            return int(message.command[1])
        except (TypeError, ValueError):
            return None
    return None


@app.on_message(filters.command("gban") & filters.user(_ADMIN_IDS))
async def gban_handler(client: Client, message: Message):
    user_id = _target_user_id(message)
    if not user_id:
        return await message.reply_text(
            f"❌ {sc('Reply to a user or use /gban <user_id>.')}"
        )
    if user_id == config.OWNER_ID:
        return await message.reply_text(f"👑 {sc('The owner cannot be globally banned.')}")

    try:
        await gbansdb.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "banned_by": message.from_user.id}},
            upsert=True,
        )
    except Exception as exc:
        LOGGER.exception("/gban database update failed: %s", exc)
        return await message.reply_text(f"❌ {sc('Global ban failed because the database is unavailable.')}")

    await message.reply_text(f"🚫 {sc('User globally banned')}: <code>{user_id}</code>", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("ungban") & filters.user(_ADMIN_IDS))
async def ungban_handler(client: Client, message: Message):
    user_id = _target_user_id(message)
    if not user_id:
        return await message.reply_text(
            f"❌ {sc('Reply to a user or use /ungban <user_id>.')}"
        )

    try:
        result = await gbansdb.delete_one({"user_id": user_id})
    except Exception as exc:
        LOGGER.exception("/ungban database delete failed: %s", exc)
        return await message.reply_text(f"❌ {sc('Global unban failed because the database is unavailable.')}")
    status = sc("User globally unbanned") if result.deleted_count else sc("User was not globally banned")
    await message.reply_text(f"✅ {status}: <code>{user_id}</code>", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.all, group=-100)
async def global_ban_guard(client: Client, message: Message):
    user = message.from_user
    if not user or not await gbansdb.find_one({"user_id": user.id}):
        return
    try:
        await message.delete()
    except Exception:
        pass
