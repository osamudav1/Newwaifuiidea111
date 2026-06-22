from html import escape

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import sudoersdb
from YUKIWAFUS.utils.helpers import sc


# ── DB Helpers ────────────────────────────────────────────────────────────────
async def get_sudoers() -> list:
    data = await sudoersdb.find_one({"sudo": "sudo"})
    return data["sudoers"] if data else []


async def add_sudo(user_id: int):
    sudoers = await get_sudoers()
    if user_id not in sudoers:
        sudoers.append(user_id)
        await sudoersdb.update_one(
            {"sudo": "sudo"},
            {"$set": {"sudoers": sudoers}},
            upsert=True,
        )
        config.SUDO_USERS.append(user_id)


async def remove_sudo(user_id: int):
    sudoers = await get_sudoers()
    if user_id in sudoers:
        sudoers.remove(user_id)
        await sudoersdb.update_one(
            {"sudo": "sudo"},
            {"$set": {"sudoers": sudoers}},
        )
        if user_id in config.SUDO_USERS:
            config.SUDO_USERS.remove(user_id)


# ── /addsudo ──────────────────────────────────────────────────────────────────
@app.on_message(filters.command(["addsudo", "addsudo"]) & filters.user(config.OWNER_ID))
async def addsudo_handler(client: Client, message: Message):
    user_id = None
    name = None

    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        name = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            name = user.first_name
        except Exception:
            return await message.reply_text(f"❌ {sc('Invalid user id.')}")
    else:
        return await message.reply_text(
            f"❌ {sc('Usage')}: <code>/addsudo &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    if user_id == config.OWNER_ID:
        return await message.reply_text(f"👑 {sc('Thats the owner!')}")

    if user_id in config.SUDO_USERS:
        return await message.reply_text(
            f"⚠️ <b>{escape(name)}</b> {sc('is already a sudo user.')}",
            parse_mode=enums.ParseMode.HTML,
        )

    await add_sudo(user_id)
    await message.reply_text(
        f"✅ <b><a href='tg://user?id={user_id}'>{escape(name)}</a></b> {sc('added as sudo user.')}",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /rmsudo ───────────────────────────────────────────────────────────────────
@app.on_message(filters.command("rmsudo") & filters.user(config.OWNER_ID))
async def rmsudo_handler(client: Client, message: Message):
    user_id = None
    name = None

    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        name = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            name = user.first_name
        except Exception:
            return await message.reply_text(f"❌ {sc('Invalid user id.')}")
    else:
        return await message.reply_text(
            f"❌ {sc('Usage')}: <code>/rmsudo &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    if user_id == config.OWNER_ID:
        return await message.reply_text(f"👑 {sc('Cannot remove the owner!')}")

    if user_id not in config.SUDO_USERS:
        return await message.reply_text(
            f"⚠️ <b>{escape(name)}</b> {sc('is not a sudo user.')}",
            parse_mode=enums.ParseMode.HTML,
        )

    await remove_sudo(user_id)
    await message.reply_text(
        f"✅ <b><a href='tg://user?id={user_id}'>{escape(name)}</a></b> {sc('removed from sudo.')}",
        parse_mode=enums.ParseMode.HTML,
    )


# ── /sudolist ─────────────────────────────────────────────────────────────────
@app.on_message(filters.command("sudolist") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def sudolist_handler(client: Client, message: Message):
    text = f"<blockquote>👑 <b>{sc('Yukiwafus Sudo Users')}</b></blockquote>\n\n"

    # Owner
    try:
        owner = await client.get_users(config.OWNER_ID)
        text += f"👑 <b>{sc('Owner')}:</b>\n"
        text += f"  ◈ <a href='tg://user?id={config.OWNER_ID}'>{escape(owner.first_name)}</a> (<code>{config.OWNER_ID}</code>)\n\n"
    except Exception:
        text += f"👑 <b>{sc('Owner')}:</b> <code>{config.OWNER_ID}</code>\n\n"

    # Sudo users
    sudoers = await get_sudoers()
    if not sudoers:
        text += f"🛡 <b>{sc('Sudo Users')}:</b> {sc('None')}"
    else:
        text += f"🛡 <b>{sc('Sudo Users')}:</b>\n"
        for uid in sudoers:
            try:
                u = await client.get_users(uid)
                text += f"  ◈ <a href='tg://user?id={uid}'>{escape(u.first_name)}</a> (<code>{uid}</code>)\n"
            except Exception:
                text += f"  ◈ <code>{uid}</code>\n"

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
