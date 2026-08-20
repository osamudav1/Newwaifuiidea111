from datetime import datetime
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb, balancedb
from YUKIWAFUS.utils.api import get_random_waifu
from YUKIWAFUS.utils.helpers import sc
from YUKIWAFUS.utils.safe_photo import safe_reply_photo

CLAIM_COOLDOWN = config.CLAIM_COOLDOWN  # 86400 = 24h
CLAIM_COINS    = 50

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

# ── Prevent spam ──────────────────────────────────────────────────────────────
claim_lock: set = set()


# ── Helpers ───────────────────────────────────────────────────────────────────
def format_time(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts) or "0s"


async def get_last_claim(user_id: int) -> datetime | None:
    user = await collectiondb.find_one({"user_id": user_id})
    return user.get("last_claim") if user else None


async def set_last_claim(user_id: int, username: str, first_name: str, waifu: dict):
    await collectiondb.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username":   username,
                "first_name": first_name,
                "last_claim": datetime.utcnow(),
            },
            "$push": {"waifus": waifu},
        },
        upsert=True,
    )


async def add_coins(user_id: int, amount: int) -> int:
    result = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    return (result or {}).get("coins", amount)


# ── /hclaim ───────────────────────────────────────────────────────────────────
@app.on_message(filters.command(["hclaim", "claim", "daily"]))
async def hclaim_handler(client: Client, message: Message):
    user_id   = message.from_user.id
    username  = message.from_user.username or ""
    name      = message.from_user.first_name
    mention   = f"<a href='tg://user?id={user_id}'>{escape(name)}</a>"

    # ── Spam lock ─────────────────────────────────────────────────────────────
    if user_id in claim_lock:
        return await message.reply_text(f"⏳ {sc('Your claim is being processed...')}")

    claim_lock.add(user_id)

    try:
        # ── Cooldown check ────────────────────────────────────────────────────
        last_claim = await get_last_claim(user_id)
        if last_claim:
            diff = (datetime.utcnow() - last_claim).total_seconds()
            if diff < CLAIM_COOLDOWN:
                remaining = int(CLAIM_COOLDOWN - diff)
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        f"⏰ {sc('Come back in')} {format_time(remaining)}",
                        callback_data="claim_cooldown"
                    )]
                ])
                return await message.reply_text(
                    f"<blockquote>⏳ <b>{mention} {sc('already claimed today')}!</b></blockquote>\n\n"
                    f"🕐 {sc('Next claim in')}: <b>{format_time(remaining)}</b>",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard,
                )

        # ── Fetch waifu from API ──────────────────────────────────────────────
        processing = await message.reply_text(f"🎴 {sc('Fetching your daily waifu')}...")
        waifu = await get_random_waifu()

        if not waifu:
            await processing.delete()
            return await message.reply_text(f"❌ {sc('No waifu available right now. Try again later!')}")

        # ── Save to DB ────────────────────────────────────────────────────────
        await set_last_claim(user_id, username, name, waifu)
        new_balance = await add_coins(user_id, CLAIM_COINS)
        await processing.delete()

        # ── Send result ───────────────────────────────────────────────────────
        rarity = waifu.get("rarity", "Common")
        emoji  = RARITY_EMOJI.get(rarity, "◈")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🌸 {sc('My Harem')}", switch_inline_query_current_chat=f"col.{user_id}"),
                InlineKeyboardButton(f"⚔️ {sc('Battle')}", switch_inline_query_current_chat=f"battle.{user_id}"),
            ]
        ])

        await safe_reply_photo(
            message,
            photo=waifu["img_url"],
            caption=(
                f"<blockquote>🎊 <b>{sc('Daily Claim')}!</b></blockquote>\n\n"
                f"🎉 {mention} {sc('got a new waifu')}!\n\n"
                f"📛 <b>{sc('Name')}:</b> {escape(waifu['name'])}\n"
                f"🎬 <b>{sc('Anime')}:</b> {escape(waifu.get('anime_name', waifu.get('anime', 'Unknown')))}\n"
                f"{emoji} <b>{sc('Rarity')}:</b> {rarity}\n"
                f"🏷 <b>{sc('Event')}:</b> {waifu.get('event', waifu.get('event_tag', 'Standard'))}\n\n"
                f"🪙 <b>+{CLAIM_COINS} {sc('coins')}</b> → {sc('Balance')}: <b>{new_balance}</b>\n\n"
                f"<i>{sc('Come back tomorrow for another claim')}~</i>"
            ),
            reply_markup=keyboard,
        )

    except Exception:
        await message.reply_text(f"❌ {sc('Something went wrong. Try again!')}")

    finally:
        claim_lock.discard(user_id)


# ── Cooldown button answer ────────────────────────────────────────────────────
@app.on_callback_query(filters.regex("^claim_cooldown$"))
async def claim_cooldown_cb(client, cq):
    await cq.answer(sc("You already claimed today! Come back later."), show_alert=True)
