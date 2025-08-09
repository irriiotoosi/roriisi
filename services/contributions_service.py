from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from storage.json_store import JsonContributionStore


BONUS_PERCENT = 0.05  # 5%


@dataclass
class AwardResult:
    primary_amount: int
    elder_bonus_amount: int
    elder_id: Optional[int]


class ContributionService:
    def __init__(self, store: Optional[JsonContributionStore] = None) -> None:
        self.store = store or JsonContributionStore()

    async def initialize(self) -> None:
        await self.store.initialize()

    async def award_points(
        self,
        *,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str,
        issuer_id: int,
    ) -> AwardResult:
        # Record primary contribution
        await self.store.record_contribution(
            guild_id=guild_id,
            user_id=user_id,
            amount=amount,
            reason=reason,
            issuer_id=issuer_id,
        )
        elder_bonus_amount = 0
        elder_id: Optional[int] = None
        # Apply elder bonus only on positive awards
        if amount > 0:
            elder_id = await self.store.get_elder_for_protege(guild_id=guild_id, protege_id=user_id)
            if elder_id is not None:
                elder_bonus_amount = max(int(amount * BONUS_PERCENT), 0)
                if elder_bonus_amount > 0:
                    await self.store.record_contribution(
                        guild_id=guild_id,
                        user_id=elder_id,
                        amount=elder_bonus_amount,
                        reason=f"Protégé bonus from {user_id}",
                        issuer_id=issuer_id,
                    )
        return AwardResult(primary_amount=amount, elder_bonus_amount=elder_bonus_amount, elder_id=elder_id)