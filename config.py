from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    COMMAND_PREFIX: str = "!"
    DATA_FILE_PATH: str = "data/contributions.json"
    # If set, the bot will do a faster, guild-only app command sync
    DEBUG_GUILD_ID: Optional[int] = (
        int(os.environ["DEBUG_GUILD_ID"]) if os.environ.get("DEBUG_GUILD_ID") else None
    )


settings = Settings()