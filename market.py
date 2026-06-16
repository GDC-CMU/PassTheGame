from __future__ import annotations

from dataclasses import dataclass
import random

from settings import (
    MARKET_EVERBLOOM_UNLOCK_COST,
    MARKET_RARE_SEED_CHANCE,
    MARKET_RARE_SEED_ROTATE_DAYS,
    TOOL_UNLOCK_COSTS,
)


TOOL_COMPOST = "compost"
TOOL_SCARECROW = "scarecrow"
TOOL_LIGHTNING_ROD = "lightning_rod"
TOOL_BELL = "bell"

THREAT_GROUND_CRITTER = "ground_critter"
THREAT_FLYING_CROW = "flying_crow"
THREAT_LIGHTNING = "lightning"
THREAT_CROP_DEATH = "crop_death"

TOOL_TRIGGER_FLAGS = {
    TOOL_COMPOST: THREAT_CROP_DEATH,
    TOOL_SCARECROW: THREAT_GROUND_CRITTER,
    TOOL_LIGHTNING_ROD: THREAT_LIGHTNING,
    TOOL_BELL: THREAT_FLYING_CROW,
}

TOOL_LABELS = {
    TOOL_COMPOST: "Compost",
    TOOL_SCARECROW: "Scarecrow",
    TOOL_LIGHTNING_ROD: "Lightning Rod",
    TOOL_BELL: "Bell",
}


@dataclass(frozen=True)
class MarketOffer:
    kind: str
    item_id: str
    label: str
    cost: int
    reason: str


class MarketState:
    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self.featured_rare_seed: str | None = None
        self.featured_day: int = -1
        self.threat_flags: set[str] = set()

    def to_dict(self) -> dict:
        return {
            "featured_rare_seed": self.featured_rare_seed,
            "featured_day": int(self.featured_day),
            "threat_flags": sorted(self.threat_flags),
        }

    def from_dict(self, data: dict | None) -> None:
        data = data or {}
        seed = data.get("featured_rare_seed")
        self.featured_rare_seed = str(seed) if seed else None
        self.featured_day = int(data.get("featured_day", -1))
        self.threat_flags = {str(flag) for flag in data.get("threat_flags", [])}

    def mark_threat(self, flag: str) -> None:
        if flag:
            self.threat_flags.add(str(flag))

    def force_featured_seed(self, seed_name: str | None) -> None:
        self.featured_rare_seed = str(seed_name) if seed_name else None

    def roll_daily_stock(self, day_index: int, seeds, unlocked_seed_names: set[str]) -> None:
        cadence = max(1, int(MARKET_RARE_SEED_ROTATE_DAYS))
        if self.featured_day >= 0 and day_index - self.featured_day < cadence:
            return
        self.featured_day = int(day_index)
        candidates = [
            type(seed).__name__
            for seed in seeds
            if type(seed).__name__ not in unlocked_seed_names
            and int(getattr(seed, "unlock_at", 0)) > 0
            and not getattr(seed, "legacy_quest_seed", False)
        ]
        if candidates and self._rng.random() < float(MARKET_RARE_SEED_CHANCE):
            self.featured_rare_seed = self._rng.choice(candidates)
        else:
            self.featured_rare_seed = None

    def seed_offers(
        self,
        seeds,
        unlocked_seed_names: set[str],
        total_earned: int,
        everbloom_ready: bool,
    ) -> list[MarketOffer]:
        offers: list[MarketOffer] = []
        offered: set[str] = set()
        for seed in seeds:
            name = type(seed).__name__
            if name in unlocked_seed_names:
                continue
            if getattr(seed, "legacy_quest_seed", False):
                if everbloom_ready:
                    offers.append(MarketOffer(
                        "seed", name, getattr(seed, "name", name),
                        int(MARKET_EVERBLOOM_UNLOCK_COST), "Everbloom quest",
                    ))
                    offered.add(name)
                continue
            unlock_cost = int(getattr(seed, "unlock_at", 0))
            if unlock_cost > 0 and int(total_earned) >= unlock_cost:
                offers.append(MarketOffer(
                    "seed", name, getattr(seed, "name", name), unlock_cost, "Earned license",
                ))
                offered.add(name)

        featured = self.featured_rare_seed
        if featured and featured not in unlocked_seed_names and featured not in offered:
            seed = next((s for s in seeds if type(s).__name__ == featured), None)
            if seed is not None:
                cost = int(getattr(seed, "unlock_at", 0))
                if cost > 0:
                    offers.insert(0, MarketOffer(
                        "seed", featured, getattr(seed, "name", featured), cost, "Featured rare seed",
                    ))
        return offers

    def tool_offers(self, unlocked_tools: set[str]) -> list[MarketOffer]:
        offers: list[MarketOffer] = []
        for tool_id in (TOOL_SCARECROW, TOOL_BELL, TOOL_LIGHTNING_ROD, TOOL_COMPOST):
            if tool_id in unlocked_tools:
                continue
            flag = TOOL_TRIGGER_FLAGS.get(tool_id)
            if flag not in self.threat_flags:
                continue
            offers.append(MarketOffer(
                "tool", tool_id, TOOL_LABELS.get(tool_id, tool_id),
                int(TOOL_UNLOCK_COSTS.get(tool_id, 0)), "Tool unlock",
            ))
        return offers

    def offers(
        self,
        seeds,
        unlocked_seed_names: set[str],
        unlocked_tools: set[str],
        total_earned: int,
        everbloom_ready: bool,
    ) -> list[MarketOffer]:
        return self.tool_offers(unlocked_tools) + self.seed_offers(
            seeds, unlocked_seed_names, total_earned, everbloom_ready
        )
