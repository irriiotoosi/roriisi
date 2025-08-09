from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from config import settings


@dataclass
class ContributionEntry:
    guild_id: int
    user_id: int
    issuer_id: int
    amount: int
    reason: str
    timestamp: int  # epoch seconds UTC


class JsonContributionStore:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path: str = file_path or settings.DATA_FILE_PATH
        self._lock: asyncio.Lock = asyncio.Lock()
        self._initialized: bool = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        if not os.path.exists(self.file_path):
            async with aiofiles.open(self.file_path, mode="w", encoding="utf-8") as f:
                await f.write(json.dumps({"guilds": {}}, ensure_ascii=False))
        self._initialized = True

    async def _read(self) -> Dict[str, Any]:
        async with aiofiles.open(self.file_path, mode="r", encoding="utf-8") as f:
            raw = await f.read()
            return json.loads(raw or "{}")

    async def _write(self, data: Dict[str, Any]) -> None:
        async with aiofiles.open(self.file_path, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False))

    async def record_contribution(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str,
        issuer_id: int,
        timestamp: Optional[int] = None,
    ) -> None:
        if not self._initialized:
            await self.initialize()
        ts = timestamp or int(datetime.now(timezone.utc).timestamp())
        entry = ContributionEntry(
            guild_id=guild_id,
            user_id=user_id,
            issuer_id=issuer_id,
            amount=amount,
            reason=reason,
            timestamp=ts,
        )
        async with self._lock:
            data = await self._read()
            guilds = data.setdefault("guilds", {})
            guild = guilds.setdefault(str(guild_id), {})
            history: List[Dict[str, Any]] = guild.setdefault("history", [])
            history.append(entry.__dict__)
            await self._write(data)

    async def get_user_total(self, guild_id: int, user_id: int, since_ts: Optional[int] = None) -> int:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        history: List[Dict[str, Any]] = guild.get("history", [])
        total = 0
        for item in history:
            if item.get("user_id") != user_id:
                continue
            if since_ts is not None and int(item.get("timestamp", 0)) < since_ts:
                continue
            total += int(item.get("amount", 0))
        return total

    async def get_leaderboard(
        self,
        guild_id: int,
        since_ts: Optional[int] = None,
        limit: int = 10,
    ) -> List[Tuple[int, int]]:
        if not self._initialized:
            await self.initialize()
        async with self._lock:
            data = await self._read()
        guild = data.get("guilds", {}).get(str(guild_id), {})
        history: List[Dict[str, Any]] = guild.get("history", [])
        totals: Dict[int, int] = {}
        for item in history:
            if since_ts is not None and int(item.get("timestamp", 0)) < since_ts:
                continue
            user_id = int(item.get("user_id"))
            totals[user_id] = totals.get(user_id, 0) + int(item.get("amount", 0))
        # Sort by total desc, then user_id asc for stability
        sorted_items = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        return sorted_items[:limit]