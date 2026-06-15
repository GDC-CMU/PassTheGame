"""The Almanac - a cozy, optional, reward-only progression spine.

A small manager object owned by Game. It records progress toward per-season
goals and a once-per-year capstone, and *queues* rewards/celebrations that Game
drains and applies. It never mutates Game state directly (no circular coupling),
which keeps save/pause handling trivial.

Design notes:
- A "Year" = 4 in-game weeks = the 4 seasons cycling once (~28 min).
- Goals are season-scoped ("...this Spring"): progress only counts while that
  season is active. Missing a goal costs nothing (cozy, reward-only).
- The year capstone fires on the time boundary regardless of goals; completing
  goals only scales the payoff up ("Perfect Year").
"""

from __future__ import annotations

from dataclasses import dataclass, field


class GoalKind:
    HARVEST_CROP = "harvest_crop"   # a crop product harvested (counts harvest_yield)
    EARN_MONEY = "earn_money"       # money gained from selling, this season
    SELL_ITEM = "sell_item"         # count of a specific item sold
    BLOCK_BOSS = "block_boss"       # successful cloud blocks of a boss strike
    SURVIVE_BOSS = "survive_boss"   # a boss visit ends (defeated/retreated)
    PLANT_COUNT = "plant_count"     # seeds committed to soil
    COEXIST_SUN_SHADE = "coexist_sun_shade"  # a sun-lover and a shade-lover healthy at once


@dataclass(frozen=True)
class Reward:
    money: int = 0
    item_name: str | None = None
    item_count: int = 0
    unlock_seed: str | None = None   # PlantType subclass name, e.g. "Cactus"
    label: str = ""                  # shown in the journal + completion toast


@dataclass(frozen=True)
class GoalDef:
    """Authored, immutable goal definition."""
    id: str
    description: str
    kind: str
    target: int
    product: str | None = None       # crop product / item / boss id; None = "any"
    reward: Reward = Reward()


@dataclass
class GoalState:
    """Mutable per-playthrough progress (this is what gets saved)."""
    id: str
    progress: int = 0
    completed: bool = False
    reward_claimed: bool = False


@dataclass(frozen=True)
class GoalCompletion:
    goal_id: str
    reward: Reward


@dataclass(frozen=True)
class YearCapstone:
    year: int
    money: int
    new_difficulty: int
    perfect: bool
    crops: int = 0
    gold: int = 0
    titans: int = 0
    goals_done: int = 0
    goals_total: int = 0
    grade: str = "C"


# ── Authored content ─────────────────────────────────────────────────────────
# Seasons: 0 Spring, 1 Summer, 2 Fall, 3 Winter. Targets are comfortably
# reachable in one in-game week but never required.
SEASON_GOALS: dict[int, list[GoalDef]] = {
    0: [
        GoalDef("spring_first_planting", "Tuck 8 seeds into fresh soil.",
                GoalKind.PLANT_COUNT, 8, None,
                Reward(money=15, item_name="Compost", item_count=2, label="$15 + Compost x2")),
        GoalDef("spring_carrot_basket", "Bring in a dozen Carrots.",
                GoalKind.HARVEST_CROP, 12, "Carrot",
                Reward(money=20, label="$20")),
        GoalDef("spring_first_market", "Earn $100 at market this Spring.",
                GoalKind.EARN_MONEY, 100, None,
                Reward(money=10, unlock_seed="Cactus", label="Unlock Cactus + $10")),
        GoalDef("spring_sun_and_shade", "Keep a sun-lover and a shade-lover happy at the same time.",
                GoalKind.COEXIST_SUN_SHADE, 1, None,
                Reward(money=20, item_name="Compost", item_count=1, label="$20 + Compost")),
    ],
    1: [
        GoalDef("summer_cactus_harvest", "Harvest 8 Cactus Fruit under the blazing sun.",
                GoalKind.HARVEST_CROP, 8, "Cactus Fruit",
                Reward(money=30, label="$30")),
        GoalDef("summer_sun_sales", "Sell 6 Cactus Fruit to the market.",
                GoalKind.SELL_ITEM, 6, "Cactus Fruit",
                Reward(money=10, item_name="Compost", item_count=3, label="$10 + Compost x3")),
        GoalDef("summer_storm_shield", "Shield the farm: block 3 lightning strikes.",
                GoalKind.BLOCK_BOSS, 3, None,
                Reward(money=15, unlock_seed="Pumpkin", label="Unlock Pumpkin + $15")),
    ],
    2: [
        GoalDef("fall_pumpkin_patch", "Grow 6 plump Pumpkins.",
                GoalKind.HARVEST_CROP, 6, "Pumpkin",
                Reward(money=40, label="$40")),
        GoalDef("fall_orchard", "Pick 15 Apples from the orchard.",
                GoalKind.HARVEST_CROP, 15, "Apple",
                Reward(money=20, label="$20")),
        GoalDef("fall_bountiful_market", "Earn $300 from the autumn harvest.",
                GoalKind.EARN_MONEY, 300, None,
                Reward(item_name="Compost", item_count=2, unlock_seed="Rice", label="Unlock Rice + Compost x2")),
    ],
    3: [
        GoalDef("winter_mushroom_forage", "Forage 10 Mushrooms in the low winter sun.",
                GoalKind.HARVEST_CROP, 10, "Mushroom",
                Reward(money=25, label="$25")),
        GoalDef("winter_night_bloom", "Coax 4 Night Blooms to flower.",
                GoalKind.HARVEST_CROP, 4, "Night Bloom",
                Reward(money=30, label="$30")),
        GoalDef("winter_weather_titan", "Weather one Cyclone Titan visit.",
                GoalKind.SURVIVE_BOSS, 1, "cyclone",
                Reward(money=20, item_name="Storm Seed", item_count=1, label="$20 + Storm Seed")),
    ],
}

# Guaranteed crop drip at each year capstone (unlocks the first name not yet
# owned). Only ever *adds*, so it's backward compatible.
YEAR_UNLOCK_ORDER = ["Tomato", "Cactus", "Pumpkin", "Mushroom", "Rice", "NightBloom", "Apple"]

YEAR_CAPSTONE_BASE_MONEY = 50
YEAR_CAPSTONE_PERFECT_BONUS = 100
# Difficulty climbs one level per year and keeps climbing over time (bosses spawn
# faster + tougher, and thieves/critters get more frequent). This is only a very
# high sanity bound so an extreme-late game does not overflow; in normal play the
# difficulty simply tracks the year number and always rises.
AUTO_DIFFICULTY_CAP = 99

# Year grade weighting (out of 100): goals dominate; gold and titans top it up.
GRADE_GOLD_TARGET = 800
GRADE_TITAN_TARGET = 4
GRADE_W_GOALS = 70
GRADE_W_GOLD = 20
GRADE_W_TITANS = 10


def compute_year_grade(goals_done, goals_total, gold, titans, perfect) -> str:
    goals_pct = (goals_done / goals_total) if goals_total > 0 else 0.0
    score = goals_pct * GRADE_W_GOALS
    score += min(1.0, gold / GRADE_GOLD_TARGET) * GRADE_W_GOLD
    score += min(1.0, titans / GRADE_TITAN_TARGET) * GRADE_W_TITANS
    if perfect or score >= 90:
        return "S"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


class Almanac:
    def __init__(self, season_names: tuple[str, ...]):
        self.season_names = tuple(season_names) if season_names else ("Spring", "Summer", "Fall", "Winter")
        self.states: dict[int, dict[str, GoalState]] = {}
        self.season_index = 0
        self.year_index = 0
        self.difficulty = 0
        self.completed_year_count = 0
        self.year_crops_harvested = 0
        self.year_gold_earned = 0
        self.year_titans_defeated = 0
        self._pending_rewards: list[GoalCompletion] = []
        self._pending_celebrations: list[str] = []
        self._pending_capstone: YearCapstone | None = None

    # ── lifecycle ────────────────────────────────────────────────────────────
    def init_fresh(self, season_index: int, year_index: int) -> None:
        self.states = {}
        self.year_index = int(year_index)
        self.difficulty = 0
        self.completed_year_count = 0
        self.year_crops_harvested = 0
        self.year_gold_earned = 0
        self.year_titans_defeated = 0
        self.set_season(int(season_index))

    def _ensure_season(self, idx: int) -> None:
        if idx not in self.states:
            self.states[idx] = {g.id: GoalState(g.id) for g in SEASON_GOALS.get(idx, [])}
        else:
            # Backfill any newly-authored goals into an existing save.
            for g in SEASON_GOALS.get(idx, []):
                self.states[idx].setdefault(g.id, GoalState(g.id))

    def set_season(self, season_index: int) -> None:
        self.season_index = int(season_index)
        self._ensure_season(self.season_index)

    # ── progress hooks (fire-and-forget) ──────────────────────────────────────
    def on_event(self, kind: str, product: str | None = None, amount: int = 1) -> None:
        if amount <= 0:
            return
        idx = self.season_index
        self._ensure_season(idx)
        states = self.states.get(idx, {})
        for g in SEASON_GOALS.get(idx, []):
            if g.kind != kind:
                continue
            if g.product is not None and g.product != product:
                continue
            st = states.get(g.id)
            if st is None or st.completed:
                continue
            st.progress += int(amount)
            if st.progress >= g.target:
                st.progress = g.target
                st.completed = True
                self._pending_rewards.append(GoalCompletion(g.id, g.reward))
                label = g.reward.label or g.description
                self._pending_celebrations.append(f"Almanac goal done: {label}")

    def on_harvest(self, product: str, amount: int) -> None:
        self.on_event(GoalKind.HARVEST_CROP, product, int(amount))
        if amount > 0:
            self.year_crops_harvested += int(amount)

    def on_money_earned(self, amount: int) -> None:
        self.on_event(GoalKind.EARN_MONEY, None, int(amount))
        self.year_gold_earned += max(0, int(amount))

    def on_item_sold(self, item: str, amount: int) -> None:
        self.on_event(GoalKind.SELL_ITEM, item, int(amount))

    def on_plant(self, product: str | None = None) -> None:
        self.on_event(GoalKind.PLANT_COUNT, product, 1)

    def on_titan_defeated(self) -> None:
        self.year_titans_defeated += 1

    def year_goals_completed(self) -> int:
        n = 0
        for idx, goals in SEASON_GOALS.items():
            states = self.states.get(idx, {})
            for g in goals:
                st = states.get(g.id)
                if st is not None and st.completed:
                    n += 1
        return n

    @staticmethod
    def year_goal_total() -> int:
        return sum(len(goals) for goals in SEASON_GOALS.values())

    # ── year boundary / capstone ──────────────────────────────────────────────
    def on_year_boundary(self, year_index: int) -> YearCapstone:
        # Evaluate the year that just ended BEFORE resetting its goals.
        perfect = self._all_goals_completed()
        self.year_index = int(year_index)
        # Difficulty tracks the year number and keeps rising over time: entering
        # Year 2 == level 2, Year 3 == level 3, and so on (the cap is only a very
        # high sanity bound). Bosses spawn faster and tougher, and thieves/critters
        # get more frequent, so a long game grows steadily harder.
        self.difficulty = min(int(year_index) + 1, AUTO_DIFFICULTY_CAP)
        self.completed_year_count += 1
        money = YEAR_CAPSTONE_BASE_MONEY + (YEAR_CAPSTONE_PERFECT_BONUS if perfect else 0)
        goals_done = self.year_goals_completed()       # capture BEFORE reset
        goals_total = self.year_goal_total()
        grade = compute_year_grade(goals_done, goals_total,
                                   self.year_gold_earned, self.year_titans_defeated, perfect)
        cap = YearCapstone(
            int(year_index), money, self.difficulty, perfect,
            crops=int(self.year_crops_harvested),
            gold=int(self.year_gold_earned),
            titans=int(self.year_titans_defeated),
            goals_done=int(goals_done),
            goals_total=int(goals_total),
            grade=grade,
        )
        self._pending_capstone = cap
        banner = f"Year {year_index} complete!"
        if perfect:
            banner = f"Perfect Year {year_index}!"
        self._pending_celebrations.append(banner)
        # Goals + per-year stats are per-year, not lifetime: start the new year
        # fresh so progress, the Perfect-Year check, and the HUD count reflect
        # only the current year.
        self.year_crops_harvested = 0
        self.year_gold_earned = 0
        self.year_titans_defeated = 0
        self._reset_all_goals()
        return cap

    def _reset_all_goals(self) -> None:
        self.states = {}
        self._ensure_season(self.season_index)

    def _all_goals_completed(self) -> bool:
        for idx, goals in SEASON_GOALS.items():
            states = self.states.get(idx, {})
            for g in goals:
                st = states.get(g.id)
                if st is None or not st.completed:
                    return False
        return True

    # ── drains (Game calls each frame) ────────────────────────────────────────
    def pop_rewards(self) -> list[GoalCompletion]:
        out = self._pending_rewards
        self._pending_rewards = []
        for c in out:
            for states in self.states.values():
                st = states.get(c.goal_id)
                if st is not None:
                    st.reward_claimed = True
        return out

    def pop_celebrations(self) -> list[str]:
        out = self._pending_celebrations
        self._pending_celebrations = []
        return out

    def pop_year_capstone(self) -> YearCapstone | None:
        cap = self._pending_capstone
        self._pending_capstone = None
        return cap

    # ── UI queries ────────────────────────────────────────────────────────────
    def active_goals(self) -> list[tuple[GoalDef, GoalState]]:
        self._ensure_season(self.season_index)
        states = self.states.get(self.season_index, {})
        out = []
        for g in SEASON_GOALS.get(self.season_index, []):
            out.append((g, states.get(g.id, GoalState(g.id))))
        return out

    def season_goal_count(self) -> int:
        return len(SEASON_GOALS.get(self.season_index, []))

    def season_completed_count(self) -> int:
        states = self.states.get(self.season_index, {})
        return sum(1 for st in states.values() if st.completed)

    def season_name(self) -> str:
        if self.season_names and 0 <= self.season_index < len(self.season_names):
            return self.season_names[self.season_index]
        return "Season"

    # ── save / load ────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "season_index": int(self.season_index),
            "year_index": int(self.year_index),
            "difficulty": int(self.difficulty),
            "completed_year_count": int(self.completed_year_count),
            "year_crops_harvested": int(self.year_crops_harvested),
            "year_gold_earned": int(self.year_gold_earned),
            "year_titans_defeated": int(self.year_titans_defeated),
            "states": {
                str(idx): {
                    gid: {
                        "progress": int(st.progress),
                        "completed": bool(st.completed),
                        "reward_claimed": bool(st.reward_claimed),
                    }
                    for gid, st in goals.items()
                }
                for idx, goals in self.states.items()
            },
        }

    def from_dict(self, data: dict) -> None:
        self.season_index = int(data.get("season_index", 0))
        self.year_index = int(data.get("year_index", 0))
        self.difficulty = int(data.get("difficulty", 0))
        self.completed_year_count = int(data.get("completed_year_count", 0))
        self.year_crops_harvested = int(data.get("year_crops_harvested", 0))
        self.year_gold_earned = int(data.get("year_gold_earned", 0))
        self.year_titans_defeated = int(data.get("year_titans_defeated", 0))
        self.states = {}
        raw = data.get("states", {}) or {}
        for idx_str, goals in raw.items():
            try:
                idx = int(idx_str)
            except (TypeError, ValueError):
                continue
            self.states[idx] = {}
            for gid, st in (goals or {}).items():
                self.states[idx][gid] = GoalState(
                    gid,
                    progress=int(st.get("progress", 0)),
                    completed=bool(st.get("completed", False)),
                    reward_claimed=bool(st.get("reward_claimed", False)),
                )
        # Make sure the current season's goal set exists.
        self._ensure_season(self.season_index)
        # Re-queue any completed-but-unclaimed rewards (e.g. saved mid-completion).
        for idx, goals in SEASON_GOALS.items():
            states = self.states.get(idx, {})
            for g in goals:
                st = states.get(g.id)
                if st is not None and st.completed and not st.reward_claimed:
                    self._pending_rewards.append(GoalCompletion(g.id, g.reward))
