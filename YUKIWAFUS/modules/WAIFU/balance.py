from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import balancedb, usersdb
from YUKIWAFUS.utils.helpers import sc

CURRENCY      = "Sakura"
CURRENCY_ICON = "🌸"

pay_lock: set = set()


async def get_balance(user_id: int) -> int:
    doc = await balancedb.find_one({"user_id": user_id})
    return doc.get("coins", 0) if doc else 0


async def add_coins(user_id: int, amount: int) -> int:
    result = await balancedb.find_one_and_update(
        {"user_id": user_id},
        {"$inc": {"coins": amount}},
        upsert=True,
        return_document=True,
    )
    return (result or {}).get("coins", amount)


async def set_coins(user_id: int, amount: int) -> int:
    await balancedb.update_one(
        {"user_id": user_id},
        {"$set": {"coins": amount}},
        upsert=True,
    )
    return amount


def fmt(amount: int) -> str:
    return f"{amount:,} {CURRENCY_ICON} <b>{CURRENCY}</b>"


def mention(user) -> str:
    return f"<a href='tg://user?id={user.id}'>{escape(user.first_name)}</a>"


@app.on_message(filters.command(["balance", "bal"]))
async def balance_cmd(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user

    coins   = await get_balance(target.id)
    ref     = mention(target)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"{CURRENCY_ICON} {sc('Top Players')}",
            callback_data=f"bal_top",
        ),
        InlineKeyboardButton(
            f"🌸 {sc('My Harem')}",
            switch_inline_query_current_chat=f"col.{target.id}",
        ),
    ]])

    await message.reply_photo(
        photo=config.WAIFU_PICS[0],
        caption=(
            f"<blockquote>"
            f"<emoji id='6291837599254322363'>🌸</emoji> "
            f"<b>{sc('Wallet')} — {ref}</b>"
            f"</blockquote>\n\n"
            f"<b>{CURRENCY_ICON} {sc('Balance')} :</b>  {fmt(coins)}\n\n"
            f"<i>{sc('Earn more by guessing waifus, battling & daily claims')}~</i>"
        ),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
        has_spoiler=True,
    )


@app.on_message(filters.command("pay"))
async def pay_cmd(client: Client, message: Message):
    sender = message.from_user

    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Reply to a user to pay them')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/pay &lt;amount&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    if len(message.command) < 2:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Amount not specified')}.</b>"
            f"</blockquote>\n\n"
            f"<b>{sc('Usage')} :</b> <code>/pay &lt;amount&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    receiver = message.reply_to_message.from_user

    if receiver.id == sender.id:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('You cannot pay yourself')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if receiver.is_bot:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='5998834801472182366'>❌</emoji> "
            f"<b>{sc('You cannot pay bots')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        amount = int(message.command[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.reply_text(
            f"<blockquote>"
            f"<emoji id='6001602353843672777'>⚠️</emoji> "
            f"<b>{sc('Invalid amount. Enter a positive number')}.</b>"
            f"</blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    if sender.id in pay_lock:
        return await message.reply_text(
            f"<blockquote>⏳ <b>{sc('Transaction in progress, please wait')}.</b></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )

    pay_lock.add(sender.id)
    try:
        sender_bal = await get_balance(sender.id)

        if sender_bal < amount:
            return await message.reply_text(
                f"<blockquote>"
                f"<emoji id='5998834801472182366'>❌</emoji> "
                f"<b>{sc('Insufficient balance')}!</b>"
                f"</blockquote>\n\n"
                f"<b>{sc('Your balance')} :</b> {fmt(sender_bal)}\n"
                f"<b>{sc('Required')} :</b> {fmt(amount)}",
                parse_mode=enums.ParseMode.HTML,
            )

        new_sender_bal   = await add_coins(sender.id,    -amount)
        new_receiver_bal = await add_coins(receiver.id,  +amount)

        await message.reply_photo(
            photo=config.WAIFU_PICS[0],
            caption=(
                f"<blockquote>"
                f"<emoji id='6291837599254322363'>🌸</emoji> "
                f"<b>{sc('Transfer Successful')}!</b>"
                f"</blockquote>\n\n"
                f"<b>{sc('From')} :</b> {mention(sender)}\n"
                f"<b>{sc('To')} :</b>   {mention(receiver)}\n"
                f"<b>{sc('Amount')} :</b> {fmt(amount)}\n\n"
                f"<b>{sc('Your new balance')} :</b> {fmt(new_sender_bal)}"
            ),
            parse_mode=enums.ParseMode.HTML,
            has_spoiler=True,
        )

        try:
            await client.send_message(
                receiver.id,
                f"<blockquote>"
                f"<emoji id='6291837599254322363'>🌸</emoji> "
                f"<b>{sc('You received')} {fmt(amount)}!</b>"
                f"</blockquote>\n\n"
                f"<b>{sc('From')} :</b> {mention(sender)}\n"
                f"<b>{sc('New Balance')} :</b> {fmt(new_receiver_bal)}",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass

    finally:
        pay_lock.discard(sender.id)


@app.on_message(
    filters.command("addcoins")
    & filters.user(config.SUDO_USERS + [config.OWNER_ID])
)
async def addcoins_cmd(client: Client, message: Message):
    target_user = None
    amount      = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if len(message.command) >= 2:
            try:
                amount = int(message.command[1])
            except ValueError:
                pass
    elif len(message.command) >= 3:
        try:
            uid    = int(message.command[1])
            amount = int(message.command[2])
            target_user = await client.get_users(uid)
        except Exception:
            pass

    if not target_user or amount is None:
        return await message.reply_text(
            f"<b>{sc('Usage')} :</b>\n"
            f"Reply + <code>/addcoins &lt;amount&gt;</code>\n"
            f"or <code>/addcoins &lt;user_id&gt; &lt;amount&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    new_bal = await add_coins(target_user.id, amount)
    await message.reply_text(
        f"<blockquote>"
        f"<emoji id='6001483331709966655'>✅</emoji> "
        f"<b>{sc('Coins Added')}!</b>"
        f"</blockquote>\n\n"
        f"<b>{sc('User')} :</b> {mention(target_user)}\n"
        f"<b>{sc('Added')} :</b> {fmt(amount)}\n"
        f"<b>{sc('New Balance')} :</b> {fmt(new_bal)}",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_message(
    filters.command("deduct")
    & filters.user(config.SUDO_USERS + [config.OWNER_ID])
)
async def deduct_cmd(client: Client, message: Message):
    target_user = None
    amount      = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        if len(message.command) >= 2:
            try:
                amount = int(message.command[1])
            except ValueError:
                pass
    elif len(message.command) >= 3:
        try:
            uid    = int(message.command[1])
            amount = int(message.command[2])
            target_user = await client.get_users(uid)
        except Exception:
            pass

    if not target_user or amount is None:
        return await message.reply_text(
            f"<b>{sc('Usage')} :</b>\n"
            f"Reply + <code>/deduct &lt;amount&gt;</code>\n"
            f"or <code>/deduct &lt;user_id&gt; &lt;amount&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    current = await get_balance(target_user.id)
    deduct  = min(amount, current)
    new_bal = await add_coins(target_user.id, -deduct)

    await message.reply_text(
        f"<blockquote>"
        f"<emoji id='5998834801472182366'>❌</emoji> "
        f"<b>{sc('Coins Deducted')}!</b>"
        f"</blockquote>\n\n"
        f"<b>{sc('User')} :</b> {mention(target_user)}\n"
        f"<b>{sc('Deducted')} :</b> {fmt(deduct)}\n"
        f"<b>{sc('New Balance')} :</b> {fmt(new_bal)}",
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex("^bal_top$"))
async def bal_top_cb(client: Client, cq):
    cursor  = balancedb.find({}, {"user_id": 1, "coins": 1}).sort("coins", -1).limit(10)
    top     = await cursor.to_list(length=10)

    if not top:
        return await cq.answer(sc("No data yet!"), show_alert=True)

    text = (
        f"<blockquote>"
        f"<emoji id='6291837599254322363'>🌸</emoji> "
        f"<b>{sc('Top Sakura Holders')}</b>"
        f"</blockquote>\n\n"
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, doc in enumerate(top, 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        try:
            u    = await client.get_users(doc["user_id"])
            name = escape(u.first_name)
        except Exception:
            name = str(doc["user_id"])
        text += f"{medal} <b>{name}</b> — {doc['coins']:,} {CURRENCY_ICON}\n"

    await cq.message.reply_text(text, parse_mode=enums.ParseMode.HTML)
    await cq.answer()
