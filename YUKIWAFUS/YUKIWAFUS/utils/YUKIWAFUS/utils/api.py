import aiohttp
from config import WAIFU_API_URL
from YUKIWAFUS.logging import LOGGER

BASE_URL = WAIFU_API_URL

# ── Session ───────────────────────────────────────────────────────────────────
_session: aiohttp.ClientSession = None

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


# ── Core Requests ─────────────────────────────────────────────────────────────
async def _get(endpoint: str, params: dict = None) -> dict | None:
    try:
        session = await get_session()
        async with session.get(f"{BASE_URL}{endpoint}", params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            LOGGER(__name__).error(f"API GET error {resp.status} → {endpoint}")
            return None
    except Exception as e:
        LOGGER(__name__).error(f"API GET failed: {e}")
        return None


async def _post(endpoint: str, json: dict, api_key: str) -> dict | None:
    try:
        session = await get_session()
        headers = {"x-api-key": api_key}
        async with session.post(f"{BASE_URL}{endpoint}", json=json, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            LOGGER(__name__).error(f"API POST error {resp.status} → {endpoint}")
            return None
    except Exception as e:
        LOGGER(__name__).error(f"API POST failed: {e}")
        return None


async def _put(endpoint: str, params: dict, json: dict, api_key: str) -> dict | None:
    try:
        session = await get_session()
        headers = {"x-api-key": api_key}
        async with session.put(f"{BASE_URL}{endpoint}", params=params, json=json, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            LOGGER(__name__).error(f"API PUT error {resp.status} → {endpoint}")
            return None
    except Exception as e:
        LOGGER(__name__).error(f"API PUT failed: {e}")
        return None


async def _delete(endpoint: str, params: dict, api_key: str) -> dict | None:
    try:
        session = await get_session()
        headers = {"x-api-key": api_key}
        async with session.delete(f"{BASE_URL}{endpoint}", params=params, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            LOGGER(__name__).error(f"API DELETE error {resp.status} → {endpoint}")
            return None
    except Exception as e:
        LOGGER(__name__).error(f"API DELETE failed: {e}")
        return None


# ── Public Endpoints ──────────────────────────────────────────────────────────

async def ping() -> bool:
    """Check if API is alive."""
    data = await _get("/Ping")
    return data is not None


async def get_api_key() -> str | None:
    """Generate a new API key."""
    data = await _get("/")
    if data and data.get("status") == "success":
        return data.get("api_key")
    return None


async def get_stats() -> dict | None:
    """Get total waifu count in DB."""
    data = await _get("/Stats")
    if data and data.get("status") == "success":
        return {
            "total": data.get("total_records"),
            "database": data.get("database"),
        }
    return None


async def get_random_waifu() -> dict | None:
    """Fetch one random waifu."""
    data = await _get("/Random")
    if data and data.get("status") == "success":
        return data["data"]
    return None


async def find_waifu(name: str) -> list | None:
    """Search waifu by name (partial, case-insensitive)."""
    data = await _get("/Find", params={"name": name})
    if data and data.get("status") == "success":
        return data.get("data", [])
    return None


async def get_waifu_list(skip: int = 0, limit: int = 50) -> list | None:
    """Get paginated waifu list."""
    data = await _get("/List", params={"skip": skip, "limit": limit})
    if data and data.get("status") == "success":
        return data.get("data", [])
    return None


# ── Protected Endpoints ───────────────────────────────────────────────────────

async def add_waifu(
    api_key: str,
    name: str,
    img_url: str,
    rarity: str,
    event_tag: str = "Standard",
    source_message_id: int = 0,
    added_by: str = "YUKIWAFUS",
) -> dict | None:
    """Add a new waifu to the database."""
    payload = {
        "name": name,
        "img_url": img_url,
        "rarity": rarity,
        "event_tag": event_tag,
        "source_message_id": source_message_id,
        "added_by": added_by,
    }
    data = await _post("/Waifuadd", json=payload, api_key=api_key)
    if data and data.get("status") == "success":
        return data
    return None


async def update_waifu(
    api_key: str,
    name: str,
    fields: dict,
) -> dict | None:
    """Update fields of an existing waifu by name."""
    data = await _put("/Update", params={"name": name}, json=fields, api_key=api_key)
    if data and data.get("status") == "success":
        return data
    return None


async def delete_waifu(api_key: str, name: str) -> dict | None:
    """Delete a waifu by name."""
    data = await _delete("/Rmwafus", params={"name": name}, api_key=api_key)
    if data and data.get("status") == "success":
        return data
    return None


# ── Session Cleanup ───────────────────────────────────────────────────────────
async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        LOGGER(__name__).info("API session closed.")
      
