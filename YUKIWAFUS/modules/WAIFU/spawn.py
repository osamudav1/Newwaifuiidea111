import asyncio
import random
import time

from pyrogram import Client, enums, filters
from pyrogram.types import Message

import config
from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import chatsdb
from YUKIWAFUS.utils.api import get_random_waifu
from YUKIWAFUS.utils.helpers import sc

# ── Config ────────────────────────────────────────────────────────────────────
SPAWN_AFTER   = 20
SPAWN_TIMEOUT = 120
SPAWN_VARY    = 5

# ── Per-user rate limit ───────────────────────────────────────────────────────
RATE_MSG_LIMIT  = 3       # 3 messages
RATE_WINDOW     = 3       # in 3 seconds = spam
RATE_BLOCK_TIME = 300     # blocked 5 min from spawn count

# ── Cooldowns ─────────────────────────────────────────────────────────────────
CHAT_COOLDOWN   = 10      # sec between spawns per chat (mass activity guard)
GLOBAL_COOLDOWN = 2       # sec between any spawn across all groups

# ── Memory leak guard ─────────────────────────────────────────────────────────
MEM_LIMIT = 10_000

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}

# ── In-memory ─────────────────────────────────────────────────────────────────
message_counts:   dict  = {}    # chat_id → count
spawn_targets:    dict  = {}    # chat_id → target count
active_spawns:    dict  = {}    # chat_id → waifu data (imported by guess.py)
_user_timestamps: dict  = {}    # (chat_id, user_id) → [timestamps]
_blocked_users:   dict  = {}    # (chat_id, user_id) → unblock_time
_warned_users:    set   = set() # (chat_id, user_id) already warned this block
_chat_last_spawn: dict  = {}    # chat_id → last spawn timestamp
_last_global_spawn: list = [0]  # mutable container so inner funcs can write


# ── Memory cleanup ────────────────────────────────────────────────────────────
def _maybe_cleanup():
    if len(_user_timestamps) > MEM_LIMIT:
        _user_timestamps.clear()
    if len(_blocked_users) > MEM_LIMIT:
        now = time.time()
        expired = [k for k, v in _blocked_users.items() if now >= v]
        for k in expired:
            _blocked_users.pop(k, None)
            _warned_users.discard(k)
    if len(_warned_users) > MEM_LIMIT:
        _warned_users.clear()


# ── Per-user spam check ───────────────────────────────────────────────────────
def _is_blocked(chat_id: int, user_id: int) -> bool:
    key     = (chat_id, user_id)
    unblock = _blocked_users.get(key)
    if unblock and time.time() < unblock:
        return True
    if unblock:
        _blocked_users.pop(key, None)
        _warned_users.discard(key)
    return False


def _check_rate(chat_id: int, user_id: int) -> bool:
    """Returns True if user just hit spam threshold for the first time."""
    key  = (chat_id, user_id)
    now  = time.time()
    logs = _user_timestamps.get(key, [])
    logs = [t for t in logs if now - t < RATE_WINDOW]
    logs.append(now)
    _user_timestamps[key] = logs

    if len(logs) >= RATE_MSG_LIMIT and key not in _blocked_users:
        _blocked_users[key] = now + RATE_BLOCK_TIME
        _user_timestamps.pop(key, None)
        return True
    return False


# ── DB Helpers ────────────────────────────────────────────────────────────────
async def is_chat_enabled(chat_id: int) -> bool:
    doc = await chatsdb.find_one({"chat_id": chat_id})
    return doc.get("spawn", True) if doc else True


async def set_chat_spawn(chat_id: int, enabled: bool):
    await chatsdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"spawn": enabled}},
        upsert=True,
    )


async def get_next_target(chat_id: int) -> int:
    doc    = await chatsdb.find_one({"chat_id": chat_id})
    custom = doc.get("spawn_after", SPAWN_AFTER) if doc else SPAWN_AFTER
    base   = custom + random.randint(-SPAWN_VARY, SPAWN_VARY)
    return message_counts.get(chat_id, 0) + max(5, base)


# ── Message Counter ───────────────────────────────────────────────────────────
@app.on_message(filters.group & ~filters.bot & ~filters.service, group=1)
async def count_messages(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    _maybe_cleanup()

    if not await is_chat_enabled(chat_id):
        return

    # ── Per-user spam gate ────────────────────────────────────────────────────
    if user_id:
        just_blocked = _check_rate(chat_id, user_id)

        if just_blocked:
            key = (chat_id, user_id)
            if key not in _warned_users:
                _warned_users.add(key)
                name = message.from_user.first_name or "User"
                warn = await message.reply_text(
                    f"<blockquote>"
                    f"<emoji id='6001602353843672777'>⚠️</emoji> "
                    f"<b>{sc('Hey')} {name}, {sc('slow down')}!</b>\n\n"
                    f"{sc('You are sending messages too fast')}.\n"
                    f"{sc('Your messages will')} <b>{sc('not count')}</b> "
                    f"{sc('toward waifu spawns for the next')} <b>5 {sc('minutes')}</b>.\n\n"
                    f"<i>{sc('Spamming will not make waifus spawn faster')} — "
                    f"{sc('it will only delay them for you')}.</i>"
                    f"</blockquote>",
                    parse_mode=enums.ParseMode.HTML,
                )
                asyncio.create_task(_delete_later(warn, 30))
            return

        if _is_blocked(chat_id, user_id):
            return

    # ── Chat-level cooldown ───────────────────────────────────────────────────
    now = time.time()
    if now - _chat_last_spawn.get(chat_id, 0) < CHAT_COOLDOWN:
        return

    # ── Normal count ──────────────────────────────────────────────────────────
    if chat_id not in message_counts:
        message_counts[chat_id] = 0
        spawn_targets[chat_id]  = await get_next_target(chat_id)

    message_counts[chat_id] += 1

    if chat_id in active_spawns:
        return

    if message_counts[chat_id] >= spawn_targets.get(chat_id, SPAWN_AFTER):
        # ── Global cooldown ───────────────────────────────────────────────────
        if now - _last_global_spawn[0] < GLOBAL_COOLDOWN:
            return

        message_counts[chat_id] = 0
        spawn_targets[chat_id]  = await get_next_target(chat_id)
        _chat_last_spawn[chat_id] = now
        _last_global_spawn[0]     = now
        asyncio.create_task(spawn_waifu(client, chat_id))


async def _delete_later(msg, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


# ── Spawn Logic ───────────────────────────────────────────────────────────────
async def spawn_waifu(client: Client, chat_id: int):
    waifu = await get_random_waifu()
    if not waifu:
        return

    try:
        from YUKIWAFUS.modules.WAIFU.guess import guessed_chats
        guessed_chats.discard(chat_id)
    except Exception:
        pass

    rarity = waifu.get("rarity", "Common")
    emoji  = RARITY_EMOJI.get(rarity, "◈")

    caption = (
        f"<blockquote>"
        f"{emoji} <b>{sc('A wild waifu has appeared')}!</b>\n"
        f"🏷 {sc('Rarity')}: <b>{rarity}</b>"
        f"</blockquote>\n\n"
        f"<i>{sc('Can you guess her name?')}</i>\n"
        f"<code>/guess &lt;name&gt;</code>"
    )

    try:
        msg = await client.send_photo(
            chat_id=chat_id,
            photo=waifu["img_url"],
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
        )

        active_spawns[chat_id] = {
            **waifu,
            "message_id": msg.id,
            "chat_id":    chat_id,
        }

        await asyncio.sleep(SPAWN_TIMEOUT)

        if chat_id in active_spawns and active_spawns[chat_id].get("message_id") == msg.id:
            active_spawns.pop(chat_id, None)
            try:
                await msg.edit_caption(
                    f"💨 <b>{sc('The waifu ran away')}!</b>\n"
                    f"<i>{sc('Nobody guessed in time')}~</i>",
                    parse_mode=enums.ParseMode.HTML,
                )
            except Exception:
                pass

    except Exception:
        active_spawns.pop(chat_id, None)


# ── /spawnon & /spawnoff ──────────────────────────────────────────────────────
@app.on_message(filters.command("spawnon") & filters.group)
async def spawnon_handler(client: Client, message: Message):
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status.value not in ("administrator", "creator"):
        return await message.reply_text(f"❌ {sc('Admins only!')}")

    await set_chat_spawn(message.chat.id, True)
    await message.reply_text(f"✅ {sc('Waifu spawn enabled in this group!')}")


@app.on_message(filters.command("spawnoff") & filters.group)
async def spawnoff_handler(client: Client, message: Message):
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status.value not in ("administrator", "creator"):
        return await message.reply_text(f"❌ {sc('Admins only!')}")

    await set_chat_spawn(message.chat.id, False)
    active_spawns.pop(message.chat.id, None)
    await message.reply_text(f"✅ {sc('Waifu spawn disabled in this group!')}")


# ── /fspawn (force spawn - sudo only) ────────────────────────────────────────
@app.on_message(filters.command("fspawn") & filters.user(config.SUDO_USERS + [config.OWNER_ID]))
async def fspawn_handler(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in active_spawns:
        return await message.reply_text(f"⚠️ {sc('A waifu is already active here!')}")

    try:
        await message.delete()
    except Exception:
        pass

    asyncio.create_task(spawn_waifu(client, chat_id))


# ── /setspawn ─────────────────────────────────────────────────────────────────
@app.on_message(filters.command("setspawn") & filters.group)
async def setspawn_handler(client: Client, message: Message):
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status.value not in ("administrator", "creator"):
        return await message.reply_text(f"❌ {sc('Admins only!')}")

    if len(message.command) < 2:
        current = SPAWN_AFTER
        doc = await chatsdb.find_one({"chat_id": message.chat.id})
        if doc and doc.get("spawn_after"):
            current = doc["spawn_after"]
        return await message.reply_text(
            f"ℹ️ {sc('Current spawn rate')}: <b>{current} {sc('messages')}</b>\n\n"
            f"{sc('Usage')}: <code>/setspawn &lt;number&gt;</code>\n"
            f"{sc('Example')}: <code>/setspawn 30</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    try:
        count = int(message.command[1])
        if count < 5:
            return await message.reply_text(f"❌ {sc('Minimum is 5 messages.')}")
        if count > 500:
            return await message.reply_text(f"❌ {sc('Maximum is 500 messages.')}")
    except ValueError:
        return await message.reply_text(f"❌ {sc('Enter a valid number.')}")

    await chatsdb.update_one(
        {"chat_id": message.chat.id},
        {"$set": {"spawn_after": count}},
        upsert=True,
    )

    spawn_targets[message.chat.id] = message_counts.get(message.chat.id, 0) + count

    await message.reply_text(
        f"✅ {sc('Spawn rate set to')} <b>{count} {sc('messages')}</b>!",
        parse_mode=enums.ParseMode.HTML,
    )
    
