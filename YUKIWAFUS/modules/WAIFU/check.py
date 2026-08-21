from html import escape

from bson import ObjectId
from pyrogram import Client, enums, filters
from pyrogram.types import Message

from YUKIWAFUS import app
from YUKIWAFUS.Logging import LOGGER
from YUKIWAFUS.database.Mangodb import collectiondb, waifudb
from YUKIWAFUS.utils.api import get_waifu_list

RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
    "Mythic": "🔴",
    "Supreme": "🪞",
}


def _id_values(raw_id: str) -> list:
    values = [raw_id]
    if raw_id.isdigit():
        values.append(int(raw_id))
    return values


async def _find_waifu(raw_id: str) -> dict | None:
    values = _id_values(raw_id)
    conditions = [{"waifu_id": value} for value in values]
    conditions.extend({"id": value} for value in values)
    if ObjectId.is_valid(raw_id):
        conditions.append({"_id": ObjectId(raw_id)})

    try:
        waifu = await waifudb.find_one({"$or": conditions})
        if waifu:
            return waifu
    except Exception as exc:
        LOGGER.warning("Local /check lookup failed: %s", exc)

    # Check active spawn snapshots before querying user collections.
    try:
        from YUKIWAFUS.modules.WAIFU.spawn import active_spawns
        for card in active_spawns.values():
            if str(card.get("waifu_id", "")) in {str(value) for value in values}:
                return card
            if str(card.get("id", "")) in {str(value) for value in values}:
                return card
    except Exception as exc:
        LOGGER.debug("Active spawn /check lookup skipped: %s", exc)

    # A guessed card is stored in user collections. This fallback makes
    # `/check` work even when the public API list is paginated or unavailable.
    try:
        async for user in collectiondb.find({"waifus": {"$exists": True}}):
            for card in user.get("waifus", []):
                if str(card.get("waifu_id", "")) in {str(value) for value in values}:
                    return card
                if str(card.get("id", "")) in {str(value) for value in values}:
                    return card
    except Exception as exc:
        LOGGER.warning("Collection /check lookup failed: %s", exc)

    # Fallback for cards supplied by the public waifu API.
    try:
        cards = await get_waifu_list(skip=0, limit=1000) or []
        for card in cards:
            card_id = card.get("waifu_id", card.get("id"))
            if str(card_id) == raw_id:
                return card
    except Exception as exc:
        LOGGER.warning("API /check lookup failed: %s", exc)
    return None


def _card_matches(card: dict, raw_id: str, waifu: dict) -> bool:
    ids = {str(card.get("waifu_id", "")), str(card.get("id", ""))}
    if raw_id in ids:
        return True
    # Older collection snapshots may not have an ID but retain the card name.
    return not card.get("waifu_id") and not card.get("id") and card.get("name") == waifu.get("name")


async def _catcher_stats(raw_id: str, waifu: dict) -> tuple[int, list[tuple[str, int]]]:
    counts: dict[str, dict] = {}
    try:
        async for user in collectiondb.find({"waifus": {"$exists": True}}):
            for card in user.get("waifus", []):
                if not _card_matches(card, raw_id, waifu):
                    continue
                user_id = str(user.get("user_id", "0"))
                entry = counts.setdefault(
                    user_id,
                    {
                        "name": user.get("first_name") or user.get("username") or f"Unknown User ({user_id})",
                        "count": 0,
                    },
                )
                entry["count"] += 1
    except Exception as exc:
        LOGGER.exception("/check collection aggregation failed: %s", exc)
        raise

    ranking = sorted(counts.values(), key=lambda item: (-item["count"], item["name"].lower()))
    top_ten = [(str(item["name"]), int(item["count"])) for item in ranking[:10]]
    return sum(item["count"] for item in ranking), top_ten


def _check_caption(waifu: dict, raw_id: str, total: int, top_ten: list[tuple[str, int]]) -> str:
    name = waifu.get("name", waifu.get("character_name", "Unknown"))
    anime = waifu.get("anime_name", waifu.get("anime", ""))
    anime = str(anime).strip() if anime is not None else ""
    if anime.lower() in {"unknown", "unknown anime", "none", "n/a", "-"}:
        anime = ""
    rarity = waifu.get("rarity", "Common")
    event = waifu.get("event", waifu.get("event_tag", "Standard"))
    emoji = RARITY_EMOJI.get(rarity, "◈")
    video = waifu.get("video") or waifu.get("video_id") or waifu.get("video_url") or waifu.get("animation")
    name_marker = " [🎞️]" if video else ""
    lines = [
        "◈<b>OwO! Check out this character</b>◈",
        "",
        f"🎬 <b>{escape(anime)}</b>" if anime else None,
        f"<code>{escape(str(raw_id))}</code>: <b>{escape(str(name))}{name_marker}</b>",
        f"(🪞 <b>RARITY: {escape(str(rarity))}</b>)",
        "",
        f"{emoji} <b>{escape(str(event))}</b> {emoji}",
        "",
        f"🌎 <b>CAUGHT GLOBALLY: {total} TIMES</b>",
        "",
        "⛩️ <b>TOP 10 CATCHERS OF THIS CHARACTER!</b>",
    ]
    if top_ten:
        lines.extend(f"➥ {escape(name)} x{count}" for name, count in top_ten)
    else:
        lines.append("➥ No one has caught this character yet.")
    return "\n".join(line for line in lines if line is not None)


@app.on_message(filters.command("check"))
async def check_waifu(client: Client, message: Message):
    if len(message.command) < 2 or not message.command[1].strip():
        return await message.reply_text(
            "🔎 <b>Usage:</b> <code>/check &lt;waifu_id&gt;</code>\n\n"
            "Example: <code>/check 4789</code>",
            parse_mode=enums.ParseMode.HTML,
        )

    raw_id = message.command[1].strip()
    if len(raw_id) > 64:
        return await message.reply_text("❌ Invalid waifu ID.")

    try:
        waifu = await _find_waifu(raw_id)
        if not waifu:
            return await message.reply_text(
                f"❌ Waifu ID <code>{escape(raw_id)}</code> မတွေ့ပါ။",
                parse_mode=enums.ParseMode.HTML,
            )
        total, top_ten = await _catcher_stats(raw_id, waifu)
        caption = _check_caption(waifu, raw_id, total, top_ten)
        video = waifu.get("video") or waifu.get("video_id") or waifu.get("video_url") or waifu.get("animation")
        if video:
            try:
                return await message.reply_video(video=video, caption=caption, parse_mode=enums.ParseMode.HTML)
            except Exception:
                LOGGER.warning("/check video send failed for id %s; trying photo/text", raw_id)
        photo = waifu.get("img_url") or waifu.get("image") or waifu.get("photo")
        if photo:
            return await message.reply_photo(photo=photo, caption=caption, parse_mode=enums.ParseMode.HTML)
        return await message.reply_text(caption, parse_mode=enums.ParseMode.HTML)
    except Exception:
        LOGGER.exception("/check failed for id %s", raw_id)
        return await message.reply_text("❌ Check မလုပ်နိုင်ပါ။ Database/API ကို စစ်ဆေးပါ။")
