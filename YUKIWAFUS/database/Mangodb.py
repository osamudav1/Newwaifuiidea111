from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI

# ✅ FIX 1: import ကို capital L နဲ့ ပြင်ပါ
from YUKIWAFUS.Logging import LOGGER

# ✅ FIX 2: LOGGER(__name__) ကို LOGGER လို့ ပြင်ပါ
LOGGER.info("Connecting to MongoDB...")
try:
    _mongo_ = AsyncIOMotorClient(MONGO_DB_URI)
    mongodb = _mongo_.YUKIWAFUS
    LOGGER.info("Connected to MongoDB ✓")
except Exception as e:
    LOGGER.error(f"MongoDB connection failed: {e}")
    exit()

# ── Collections ───────────────────────────────────────────────────────────────

# Users & Chats
usersdb       = mongodb.users
chatsdb       = mongodb.chats
blockeddb     = mongodb.blocked_users
gbansdb       = mongodb.gbans
sudoersdb     = mongodb.sudoers

# Waifu Core
waifudb       = mongodb.waifus          # all waifu characters
collectiondb  = mongodb.user_collection # user waifu collections
haremdb       = mongodb.harem
favdb         = mongodb.favourites

# Economy
balancedb     = mongodb.balance         # coins, tokens, sakura
shopdb        = mongodb.shop
tradedb       = mongodb.trades
giftdb        = mongodb.gifts

# Games
gamesdb       = mongodb.games           # game state per chat
game_statsdb  = mongodb.game_stats      # points, unlocks per user
leaderdb      = mongodb.leaderboard

# Flex
titlesdb      = mongodb.titles          # purchased titles
badgesdb      = mongodb.badges          # purchased badges
auradb        = mongodb.auras           # purchased auras

# Admin / Settings
onoffdb       = mongodb.onoff
langdb        = mongodb.language
blacklistdb   = mongodb.blacklist_chats
authdb        = mongodb.auth_users
notesdb       = mongodb.notes
filtersdb     = mongodb.filters
