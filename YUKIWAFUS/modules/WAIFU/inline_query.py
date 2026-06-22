import time
from html import escape

from cachetools import TTLCache
from pyrogram import Client, enums
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
)

from YUKIWAFUS import app
from YUKIWAFUS.database.Mangodb import collectiondb
from YUKIWAFUS.utils.api import find_waifu, get_waifu_list

RESULTS_PER_PAGE  = 30
CACHE_TTL_GLOBAL  = 120
CACHE_TTL_USER    = 30

_global_cache: TTLCache = TTLCache(maxsize=500,  ttl=CACHE_TTL_GLOBAL)
_user_cache:   TTLCache = TTLCache(maxsize=5000, ttl=CACHE_TTL_USER)

RARITY_EMOJI = {
    "Common":    "⚪",
    "Uncommon":  "🟢",
    "Rare":      "🔵",
    "Epic":      "🟣",
    "Legendary": "🟡",
    "Mythic":    "🔴",
}


async def _get_user_waifus(user_id: int) -> list:
    key = f"u:{user_id}"
    if key in _user_cache:
        return _user_cache[key]
    doc = await collectiondb.find_one({"user_id": user_id})
    waifus = doc.get("waifus", []) if doc else []
    _user_cache[key] = waifus
    return waifus


async def _search_global(name: str) -> list:
    key = f"g:{name.lower()}"
    if key in _global_cache:
        return _global_cache[key]
    results = await find_waifu(name) or []
    _global_cache[key] = results
    return results


async def _get_all_global() -> list:
    key = "g:all"
    if key in _global_cache:
        return _global_cache[key]
    results = await get_waifu_list(skip=0, limit=100) or []
    _global_cache[key] = results
    return results


def _build_collection_caption(waifu: dict, owner_name: str, count: int) -> str:
    rarity   = waifu.get("rarity", "Common")
    emoji    = RARITY_EMOJI.get(rarity, "◈")
    waifu_id = waifu.get("waifu_id", "N/A")
    return (
        f"<blockquote>"
        f"<b>🌸 {escape(owner_name)}'s Collection</b>"
        f"</blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(waifu.get('name', '?'))}\n"
        f"<b>{emoji} Rarity :</b> {rarity}\n"
        f"<b>🏷 Tag :</b> {waifu.get('event_tag', 'Standard')}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>\n"
        f"<b>✖ Count :</b> ×{count}"
    )


def _build_global_caption(waifu: dict) -> str:
    rarity   = waifu.get("rarity", "Common")
    emoji    = RARITY_EMOJI.get(rarity, "◈")
    waifu_id = waifu.get("waifu_id", "N/A")
    return (
        f"<blockquote>"
        f"<b>🌸 Waifu Info</b>"
        f"</blockquote>\n\n"
        f"<b>📛 Name :</b> {escape(waifu.get('name', '?'))}\n"
        f"<b>{emoji} Rarity :</b> {rarity}\n"
        f"<b>🏷 Tag :</b> {waifu.get('event_tag', 'Standard')}\n"
        f"<b>🆔 ID :</b> <code>{waifu_id}</code>"
    )


def _dedupe_count(waifus: list) -> tuple[list, dict]:
    seen   = {}
    counts = {}
    for w in waifus:
        wid = w.get("waifu_id") or w.get("name", "")
        counts[wid] = counts.get(wid, 0) + 1
        if wid not in seen:
            seen[wid] = w
    return list(seen.values()), counts


def _empty_result() -> list:
    return [
        InlineQueryResultArticle(
            title="🌸 Search waifus...",
            description="Type a name to search globally, or use col.<user_id> for a collection",
            input_message_content=InputTextMessageContent(
                "<blockquote><b>🌸 Use inline search to find waifus!</b></blockquote>",
                parse_mode=enums.ParseMode.HTML,
            ),
        )
    ]


@app.on_inline_query()
async def inline_handler(client: Client, query: InlineQuery):
    raw     = query.query.strip()
    offset  = int(query.offset) if query.offset else 0
    results = []

    try:
        if raw.startswith("col."):
            parts      = raw.split(" ", 1)
            uid_part   = parts[0][4:]
            search_str = parts[1].lower() if len(parts) > 1 else ""

            if not uid_part.lstrip("-").isdigit():
                return await query.answer(_empty_result(), cache_time=5)

            user_id    = int(uid_part)
            all_waifus = await _get_user_waifus(user_id)

            if search_str:
                all_waifus = [
                    w for w in all_waifus
                    if search_str in w.get("name", "").lower()
                    or search_str in w.get("rarity", "").lower()
                    or search_str in w.get("event_tag", "").lower()
                ]

            unique, counts = _dedupe_count(all_waifus)
            page           = unique[offset: offset + RESULTS_PER_PAGE]
            next_offset    = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            try:
                user       = await client.get_users(user_id)
                owner_name = user.first_name
            except Exception:
                owner_name = "User"

            for w in page:
                if not w.get("img_url"):
                    continue
                wid     = w.get("waifu_id") or w.get("name", "")
                count   = counts.get(wid, 1)
                caption = _build_collection_caption(w, owner_name, count)
                results.append(
                    InlineQueryResultPhoto(
                        photo_url=w["img_url"],
                        thumb_url=w["img_url"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        title=w.get("name", "?"),
                        description=f"{w.get('rarity', '')} · ×{count}",
                    )
                )

        elif raw:
            waifus      = await _search_global(raw)
            page        = waifus[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            for w in page:
                if not w.get("img_url"):
                    continue
                caption = _build_global_caption(w)
                results.append(
                    InlineQueryResultPhoto(
                        photo_url=w["img_url"],
                        thumb_url=w["img_url"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        title=w.get("name", "?"),
                        description=f"{RARITY_EMOJI.get(w.get('rarity',''), '◈')} {w.get('rarity', '')} · {w.get('event_tag', 'Standard')}",
                    )
                )

        else:
            waifus      = await _get_all_global()
            page        = waifus[offset: offset + RESULTS_PER_PAGE]
            next_offset = str(offset + len(page)) if len(page) == RESULTS_PER_PAGE else ""

            for w in page:
                if not w.get("img_url"):
                    continue
                caption = _build_global_caption(w)
                results.append(
                    InlineQueryResultPhoto(
                        photo_url=w["img_url"],
                        thumb_url=w["img_url"],
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        title=w.get("name", "?"),
                        description=f"{RARITY_EMOJI.get(w.get('rarity',''), '◈')} {w.get('rarity', '')}",
                    )
                )

        if not results and offset == 0:
            results = _empty_result()
            next_offset = ""

        await query.answer(
            results,
            cache_time=5,
            next_offset=next_offset,
            is_personal=raw.startswith("col."),
        )

    except Exception:
        await query.answer(_empty_result(), cache_time=5)
            
