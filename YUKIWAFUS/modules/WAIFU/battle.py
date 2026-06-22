import asyncio
import random
from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb, balancedb

# ── Rarity Power ──────────────────────────────────────────────────────────────
RARITY_POWER = {
    "Common":    100,
    "Uncommon":  200,
    "Rare":      350,
    "Epic":      500,
    "Legendary": 750,
    "Mythic":    1000,
}

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

BATTLE_REWARD = 100
BATTLE_TIMEOUT = 30

# ── Pending battles ───────────────────────────────────────────────────────────
pending_battles: dict = {}  # chat_id → battle data


# ── DB Helpers ────────────────────────────────────────────────────────────────
async def get_best_waifu(user_id: int) -> dict | None:
    """Get user's highest rarity waifu for battle."""
    user = await collectiondb.find_one({"user_id": user_id})
    if not user or not user.get("waifus"):
        return None

    waifus = user["waifus"]
    # Favour fav waifu if set
    favs = user.get("favourites", [])
    if favs:
        fav = next((w for w in waifus if w.get("waifu_id") == favs[0]), None)
        if fav:
            return fav

    # Else pick highest rarity
    return max(waifus, key=lambda w: RARITY_POWER.get(w.get("rarity", "Common"), 0))


async def add_coins(user_id: int, amount: int) -> int:
    result = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    return (result or {}).get("coins", amount)


# ── Battle Logic ──────────────────────────────────────────────────────────────
def calc_power(waifu: dict) -> int:
    base = RARITY_POWER.get(waifu.get("rarity", "Common"), 100)
    variance = random.randint(-20, 20)
    return max(1, base + variance)


def battle_bar(hp: int, max_hp: int, length: int = 10) -> str:
    filled = int((hp / max_hp) * length)
    return "█" * filled + "░" * (length - filled)


# ── /battle Command ───────────────────────────────────────────────────────────
@app.on_message(filters.command("battle") & filters.group)
async def battle_handler(client: Client, message: Message):
    chat_id = message.chat.id
    challenger_id = message.from_user.id

    if chat_id in pending_battles:
        return await message.reply_text("⚔️ A battle is already pending in this group!")

    if not message.reply_to_message:
        return await message.reply_text(
            "❓ Reply to someone to challenge them!\n"
            "Usage: <code>/battle</code> (reply to opponent)",
            parse_mode=enums.ParseMode.HTML,
        )

    opponent = message.reply_to_message.from_user
    if opponent.id == challenger_id:
        return await message.reply_text("🤡 You can't battle yourself!")
    if opponent.is_bot:
        return await message.reply_text("🤖 You can't battle a bot!")

    challenger_waifu = await get_best_waifu(challenger_id)
    if not challenger_waifu:
        return await message.reply_text("❌ You have no waifus! Use /hclaim first.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Accept", callback_data=f"battle_accept:{challenger_id}:{opponent.id}"),
            InlineKeyboardButton("🏃 Decline", callback_data=f"battle_decline:{challenger_id}:{opponent.id}"),
        ]
    ])

    pending_battles[chat_id] = {
        "challenger_id": challenger_id,
        "opponent_id": opponent.id,
        "challenger_waifu": challenger_waifu,
    }

    cr = RARITY_EMOJI.get(challenger_waifu.get("rarity", "Common"), "◈")

    msg = await message.reply_photo(
        photo=challenger_waifu["img_url"],
        caption=(
            f"<blockquote>⚔️ <b>Battle Challenge!</b></blockquote>\n\n"
            f"🔥 <b><a href='tg://user?id={challenger_id}'>{escape(message.from_user.first_name)}</a></b> "
            f"challenges <b><a href='tg://user?id={opponent.id}'>{escape(opponent.first_name)}</a></b>!\n\n"
            f"Challenger's Waifu:\n"
            f"{cr} <b>{challenger_waifu['name']}</b> — {challenger_waifu.get('rarity', 'Common')}\n\n"
            f"⏳ <b>{opponent.first_name}</b>, accept within {BATTLE_TIMEOUT}s!"
        ),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
    )

    # Auto-expire
    await asyncio.sleep(BATTLE_TIMEOUT)
    if chat_id in pending_battles:
        pending_battles.pop(chat_id, None)
        try:
            await msg.edit_caption(
                f"⌛ Battle expired! <b>{escape(opponent.first_name)}</b> didn't respond.",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass


# ── Accept Callback ───────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^battle_accept:"))
async def battle_accept(client: Client, cq: CallbackQuery):
    _, challenger_id, opponent_id = cq.data.split(":")
    challenger_id = int(challenger_id)
    opponent_id = int(opponent_id)
    chat_id = cq.message.chat.id

    if cq.from_user.id != opponent_id:
        return await cq.answer("This challenge isn't for you!", show_alert=True)

    battle = pending_battles.pop(chat_id, None)
    if not battle:
        return await cq.answer("Battle expired!", show_alert=True)

    opponent_waifu = await get_best_waifu(opponent_id)
    if not opponent_waifu:
        await cq.answer("You have no waifus!", show_alert=True)
        return await cq.message.reply_text("❌ Opponent has no waifus!")

    challenger_waifu = battle["challenger_waifu"]
    await cq.answer("Battle started! ⚔️")

    # ── Simulate Battle ───────────────────────────────────────────────────────
    c_power = calc_power(challenger_waifu)
    o_power = calc_power(opponent_waifu)
    c_hp = c_power
    o_hp = o_power
    c_max = c_power
    o_max = o_power

    ce = RARITY_EMOJI.get(challenger_waifu.get("rarity", "Common"), "◈")
    oe = RARITY_EMOJI.get(opponent_waifu.get("rarity", "Common"), "◈")

    challenger_user = await client.get_users(challenger_id)
    opponent_user = await client.get_users(opponent_id)

    rounds = []
    round_num = 0
    while c_hp > 0 and o_hp > 0 and round_num < 10:
        round_num += 1
        c_atk = random.randint(c_power // 4, c_power // 2)
        o_atk = random.randint(o_power // 4, o_power // 2)
        o_hp = max(0, o_hp - c_atk)
        c_hp = max(0, c_hp - o_atk)
        rounds.append((c_atk, o_atk, c_hp, o_hp))

    # ── Determine Winner ──────────────────────────────────────────────────────
    if c_hp > o_hp:
        winner_id = challenger_id
        winner_name = escape(challenger_user.first_name)
        winner_waifu = challenger_waifu
        loser_name = escape(opponent_user.first_name)
    elif o_hp > c_hp:
        winner_id = opponent_id
        winner_name = escape(opponent_user.first_name)
        winner_waifu = opponent_waifu
        loser_name = escape(challenger_user.first_name)
    else:
        winner_id = None
        winner_name = "Draw"
        winner_waifu = None
        loser_name = ""

    new_balance = None
    if winner_id:
        new_balance = await add_coins(winner_id, BATTLE_REWARD)

    # ── Build Result ──────────────────────────────────────────────────────────
    last_round = rounds[-1] if rounds else (0, 0, c_hp, o_hp)
    _, _, final_c_hp, final_o_hp = last_round

    text = (
        f"<blockquote>⚔️ <b>Battle Result!</b></blockquote>\n\n"
        f"{ce} <b>{escape(challenger_waifu['name'])}</b> vs {oe} <b>{escape(opponent_waifu['name'])}</b>\n\n"
        f"<b>{escape(challenger_user.first_name)}</b>\n"
        f"❤️ {battle_bar(final_c_hp, c_max)} {final_c_hp}/{c_max}\n\n"
        f"<b>{escape(opponent_user.first_name)}</b>\n"
        f"❤️ {battle_bar(final_o_hp, o_max)} {final_o_hp}/{o_max}\n\n"
    )

    if winner_id:
        we = RARITY_EMOJI.get(winner_waifu.get("rarity", "Common"), "◈")
        text += (
            f"🏆 <b>{winner_name}</b> wins!\n"
            f"{we} <b>{winner_waifu['name']}</b> is victorious!\n"
            f"🪙 <b>+{BATTLE_REWARD} coins</b> → Balance: <b>{new_balance}</b>"
        )
    else:
        text += "🤝 <b>It's a draw!</b> No coins awarded."

    photo = winner_waifu["img_url"] if winner_waifu else challenger_waifu["img_url"]

    try:
        await cq.message.edit_media(
            media=__import__("pyrogram.types", fromlist=["InputMediaPhoto"]).InputMediaPhoto(
                photo, caption=text, parse_mode=enums.ParseMode.HTML
            )
        )
    except Exception:
        await cq.message.reply_photo(photo=photo, caption=text, parse_mode=enums.ParseMode.HTML)


# ── Decline Callback ──────────────────────────────────────────────────────────
@app.on_callback_query(filters.regex(r"^battle_decline:"))
async def battle_decline(client: Client, cq: CallbackQuery):
    _, challenger_id, opponent_id = cq.data.split(":")
    opponent_id = int(opponent_id)
    chat_id = cq.message.chat.id

    if cq.from_user.id != opponent_id:
        return await cq.answer("This isn't your battle!", show_alert=True)

    pending_battles.pop(chat_id, None)
    await cq.answer("Battle declined.")
    await cq.message.edit_caption(
        "🏃 Battle was declined!",
        parse_mode=enums.ParseMode.HTML,
    )
