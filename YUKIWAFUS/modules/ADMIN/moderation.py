import asyncio
import time
from datetime import datetime, timedelta, timezone
from html import escape

from pyrogram import Client, StopPropagation, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import gbansdb
from YUKIWAFUS.utils.helpers import sc


# Global-ban administration is intentionally owner-only.
_OWNER_FILTER = filters.user(config.OWNER_ID)
_PENDING_GBANS: dict[tuple[int, int], dict] = {}
_PENDING_TTL_SECONDS = 15 * 60
_EXPIRY_TASK: asyncio.Task | None = None


async def _expired_ban_worker() -> None:
    """Remove temporary bans automatically when their expiry time is reached."""
    while True:
        try:
            await asyncio.sleep(30)
            now = datetime.now(timezone.utc)
            cursor = gbansdb.find({"expires_at": {"$exists": True, "$ne": None, "$lte": now}})
            expired_ids = [record.get("user_id") async for record in cursor if record.get("user_id")]
            if expired_ids:
                await gbansdb.delete_many({"user_id": {"$in": expired_ids}})
                LOGGER.info("Automatically expired %d global ban(s)", len(expired_ids))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("Global ban expiry worker failed: %s", exc)


def _ensure_expiry_worker() -> None:
    global _EXPIRY_TASK
    if _EXPIRY_TASK is None or _EXPIRY_TASK.done():
        _EXPIRY_TASK = asyncio.create_task(_expired_ban_worker())


def _target_user_id(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    if len(message.command or []) > 1:
        try:
            return int(message.command[1])
        except (TypeError, ValueError):
            return None
    return None


def _command_name(message: Message) -> str:
    command = (message.command or [""])[0]
    return command.split("@", 1)[0].lower()


def _ban_status(record: dict) -> tuple[bool, str]:
    expires_at = record.get("expires_at")
    if not expires_at:
        return True, "permanent"
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return False, "expired"
    return True, expires_at.strftime("%Y-%m-%d %H:%M UTC")


def _status_text(user_id: int, record: dict, expiry_label: str) -> str:
    reason = escape(str(record.get("reason") or "Not provided"))
    if record.get("permanent") or not record.get("expires_at"):
        duration = "Permanent — Owner /ungban only"
    else:
        duration = f"Until: {escape(expiry_label)}"
    return (
        "🚫 <b>GLOBAL BAN ACTIVE</b>\n\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"⏳ {duration}\n"
        f"📝 Reason: {reason}\n\n"
        "⚠️ This user cannot use bot commands. Only <code>/check</code> is available."
    )


@app.on_message(filters.command("gban") & _OWNER_FILTER)
async def gban_handler(client: Client, message: Message):
    user_id = _target_user_id(message)
    if not user_id:
        return await message.reply_text(
            f"❌ {sc('Reply to a user or use /gban <user_id>.')}"
        )
    if user_id == config.OWNER_ID:
        return await message.reply_text(f"👑 {sc('The owner cannot be globally banned.')}")

    key = (message.chat.id, message.from_user.id)
    _PENDING_GBANS[key] = {
        "user_id": user_id,
        "created_at": time.monotonic(),
    }
    await message.reply_text(
        "🚫 <b>Global ban setup</b>\n\n"
        f"User: <code>{user_id}</code>\n\n"
        "⏳ Send the ban duration in <b>days</b>.\n"
        "Send <code>0</code> for a permanent ban.\n"
        "Permanent bans can only be removed by the Owner with <code>/ungban</code>."
    , parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.user(config.OWNER_ID) & filters.text & ~filters.command(["gban", "ungban"]))
async def gban_setup_handler(client: Client, message: Message):
    key = (message.chat.id, message.from_user.id)
    pending = _PENDING_GBANS.get(key)
    if not pending:
        return
    if time.monotonic() - pending["created_at"] > _PENDING_TTL_SECONDS:
        _PENDING_GBANS.pop(key, None)
        await message.reply_text("⌛ Global ban setup expired. Start again with /gban <user_id>.")
        raise StopPropagation

    text = (message.text or "").strip()
    if text.lower() in {"/cancel", "cancel"}:
        _PENDING_GBANS.pop(key, None)
        await message.reply_text("✅ Global ban cancelled.")
        raise StopPropagation

    if pending.get("days") is None:
        try:
            days = int(text)
        except ValueError:
            await message.reply_text("❌ Send a whole number of days. Use <code>0</code> for permanent.", parse_mode=enums.ParseMode.HTML)
            raise StopPropagation
        if days < 0:
            await message.reply_text("❌ Days cannot be negative. Use <code>0</code> for permanent.", parse_mode=enums.ParseMode.HTML)
            raise StopPropagation
        pending["days"] = days
        pending["created_at"] = time.monotonic()
        mode = "Permanent — Owner /ungban only" if days == 0 else f"{days} day(s)"
        await message.reply_text(
            f"✅ Duration: <b>{mode}</b>\n\n"
            "📝 Now send the <b>reason</b> for this global ban.\n"
            "The ban will start only after the reason is received.",
            parse_mode=enums.ParseMode.HTML,
        )
        raise StopPropagation

    reason = text
    if not reason:
        await message.reply_text("❌ Reason is required. Send a reason, or use /cancel.")
        raise StopPropagation
    user_id = pending["user_id"]
    days = pending["days"]
    now = datetime.now(timezone.utc)
    expires_at = None if days == 0 else now + timedelta(days=days)
    record = {
        "user_id": user_id,
        "banned_by": message.from_user.id,
        "banned_at": now,
        "duration_days": days,
        "expires_at": expires_at,
        "permanent": days == 0,
        "reason": reason,
    }
    try:
        await gbansdb.update_one({"user_id": user_id}, {"$set": record}, upsert=True)
        _ensure_expiry_worker()
    except Exception as exc:
        LOGGER.exception("/gban database update failed: %s", exc)
        _PENDING_GBANS.pop(key, None)
        return await message.reply_text("❌ Global ban failed because the database is unavailable.")

    _PENDING_GBANS.pop(key, None)
    expiry_label = "permanent" if days == 0 else (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M UTC")
    await message.reply_text(
        "✅ <b>Global ban started</b>\n\n" + _status_text(user_id, record, expiry_label),
        parse_mode=enums.ParseMode.HTML,
    )
    raise StopPropagation


@app.on_message(filters.command("ungban") & _OWNER_FILTER)
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
        return await message.reply_text("❌ Global unban failed because the database is unavailable.")
    status = sc("User globally unbanned") if result.deleted_count else sc("User was not globally banned")
    await message.reply_text(f"✅ {status}: <code>{user_id}</code>", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.all, group=-100)
async def global_ban_guard(client: Client, message: Message):
    user = message.from_user
    if not user:
        return
    try:
        record = await gbansdb.find_one({"user_id": user.id})
    except Exception as exc:
        LOGGER.warning("Global ban check failed: %s", exc)
        return
    if not record:
        return

    active, expiry_label = _ban_status(record)
    if not active:
        try:
            await gbansdb.delete_one({"user_id": user.id})
        except Exception:
            LOGGER.warning("Expired global ban cleanup failed for %s", user.id)
        return
    if _command_name(message) == "check":
        return

    try:
        await message.reply_text(
            _status_text(user.id, record, expiry_label),
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass
    try:
        await message.delete()
    except Exception:
        pass
    raise StopPropagation
