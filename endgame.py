from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pygame

from almanac import AUTO_DIFFICULTY_CAP
from settings import (
    SEASON_NAMES, SEASON_GROWTH_MULT, SEASON_WATER_LOSS_MULT, SEASON_SUN_GAIN_MULT,
    TEMPEST_SPAWN_MULT,
    LEGACY_CROP_DISCOVERY_TARGET, LEGACY_TITAN_SURVIVAL_TARGET,
    LEGACY_GOLDEN_HARVEST_TARGET, LEGACY_BEST_YEAR_TARGET,
    LEGACY_MONEY_MILESTONES, LEGACY_CHALLENGE_WEIGHT,
    EVERBLOOM_LEGACY_REQUIRED, EVERBLOOM_DISCOVERED_CROPS_REQUIRED,
    EVERBLOOM_TOTAL_EARNED_REQUIRED,
)


@dataclass(frozen=True)
class NextYearPreview:
    year_index: int
    previous_difficulty: int
    next_difficulty: int
    titans: tuple[str, ...]
    season_modifiers: tuple[str, ...]
    tempest: str

    @property
    def title(self) -> str:
        return f"Year {self.year_index + 1} coming"

    @property
    def lines(self) -> tuple[str, ...]:
        diff = f"Difficulty {self.previous_difficulty} to {self.next_difficulty}"
        if self.previous_difficulty == self.next_difficulty:
            diff = f"Difficulty holds at {self.next_difficulty}"
        titan_line = "Titans: " + ", ".join(self.titans)
        return (diff, titan_line, self.tempest) + self.season_modifiers[:2]


def compute_next_year_preview(almanac, next_year_index: int, bosses: Iterable[object] | None = None) -> NextYearPreview:
    prev = int(getattr(almanac, "difficulty", 0))
    nxt = min(int(next_year_index) + 1, int(AUTO_DIFFICULTY_CAP))
    names: list[str] = []
    if bosses is not None:
        for boss in bosses:
            label = str(getattr(boss, "display_name", "Titan"))
            if label not in names:
                names.append(label)
    if not names:
        names = ["Storm Titan", "Cyclone Titan", "Drought Titan", "Frost Titan"]
    mods = []
    for i, name in enumerate(SEASON_NAMES):
        mods.append(
            f"{name}: growth x{SEASON_GROWTH_MULT[i]:.2g}, water loss x{SEASON_WATER_LOSS_MULT[i]:.2g}, sun gain x{SEASON_SUN_GAIN_MULT[i]:.2g}"
        )
    tempest = f"Winter Tempest: titan timers x{TEMPEST_SPAWN_MULT:g}"
    return NextYearPreview(int(next_year_index), prev, nxt, tuple(names), tuple(mods), tempest)


@dataclass
class LegacyTracker:
    discovered_crops: set[str] = field(default_factory=set)
    survived_titans: set[str] = field(default_factory=set)
    golden_harvests: int = 0
    best_year_reached: int = 0
    total_earned: int = 0
    completed_challenges: set[str] = field(default_factory=set)
    everbloom_harvests: int = 0

    def record_crop(self, product: str | None, amount: int = 1, *, golden: bool = False) -> None:
        if product and amount > 0:
            self.discovered_crops.add(str(product))
            if golden:
                self.golden_harvests += int(amount)

    def record_titan(self, titan_id: str | None) -> None:
        if titan_id:
            self.survived_titans.add(str(titan_id))

    def record_money(self, amount: int) -> None:
        self.total_earned = max(int(self.total_earned), int(amount))

    def record_year(self, year_index: int) -> None:
        self.best_year_reached = max(int(self.best_year_reached), int(year_index) + 1)

    def mark_challenge_complete(self, challenge_id: str) -> None:
        if challenge_id:
            self.completed_challenges.add(str(challenge_id))

    def percent(self, challenge_total: int | None = None) -> int:
        total_challenges = max(1, int(challenge_total or len(CHALLENGES) or 1))
        crops = min(1.0, len(self.discovered_crops) / float(LEGACY_CROP_DISCOVERY_TARGET)) * 30.0
        titans = min(1.0, len(self.survived_titans) / float(LEGACY_TITAN_SURVIVAL_TARGET)) * 20.0
        gold = min(1.0, int(self.golden_harvests) / float(LEGACY_GOLDEN_HARVEST_TARGET)) * 15.0
        years = min(1.0, int(self.best_year_reached) / float(LEGACY_BEST_YEAR_TARGET)) * 15.0
        money_count = sum(1 for m in LEGACY_MONEY_MILESTONES if int(self.total_earned) >= int(m))
        money = (money_count / max(1, len(LEGACY_MONEY_MILESTONES))) * 10.0
        challenges = min(1.0, len(self.completed_challenges) / float(total_challenges)) * float(LEGACY_CHALLENGE_WEIGHT)
        return max(0, min(100, int(round(crops + titans + gold + years + money + challenges))))

    def formula_lines(self) -> tuple[str, ...]:
        return (
            f"Crops {len(self.discovered_crops)}/{LEGACY_CROP_DISCOVERY_TARGET}: 30%",
            f"Titans {len(self.survived_titans)}/{LEGACY_TITAN_SURVIVAL_TARGET}: 20%",
            f"Golden harvests {self.golden_harvests}/{LEGACY_GOLDEN_HARVEST_TARGET}: 15%",
            f"Best year {self.best_year_reached}/{LEGACY_BEST_YEAR_TARGET}: 15%",
            f"Money milestones {self.total_earned}: 10%",
            f"Challenges {len(self.completed_challenges)}/{len(CHALLENGES)}: 10%",
        )

    def to_dict(self) -> dict:
        return {
            "discovered_crops": sorted(self.discovered_crops),
            "survived_titans": sorted(self.survived_titans),
            "golden_harvests": int(self.golden_harvests),
            "best_year_reached": int(self.best_year_reached),
            "total_earned": int(self.total_earned),
            "completed_challenges": sorted(self.completed_challenges),
            "everbloom_harvests": int(self.everbloom_harvests),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "LegacyTracker":
        data = data or {}
        return cls(
            discovered_crops={str(x) for x in data.get("discovered_crops", [])},
            survived_titans={str(x) for x in data.get("survived_titans", [])},
            golden_harvests=int(data.get("golden_harvests", 0)),
            best_year_reached=int(data.get("best_year_reached", 0)),
            total_earned=int(data.get("total_earned", 0)),
            completed_challenges={str(x) for x in data.get("completed_challenges", [])},
            everbloom_harvests=int(data.get("everbloom_harvests", 0)),
        )


@dataclass(frozen=True)
class ChallengeDef:
    id: str
    name: str
    effect: str
    params: dict


CHALLENGES: tuple[ChallengeDef, ...] = (
    ChallengeDef("storm_clock", "Storm Clock", "Titans spawn 20% faster.", {"boss_spawn_scale": 0.80}),
    ChallengeDef("thin_bands", "Thin Bands", "Healthy water and sun bands are 15% narrower.", {"healthy_band_scale": 0.85}),
    ChallengeDef("lean_start", "Lean Start", "Start a fresh run with half money.", {"start_money_mult": 0.50}),
    ChallengeDef("single_cloud_week", "One Cloud Week", "Only one cloud may be used during week 1.", {"one_cloud_until_week": 1}),
)


class ChallengeLadder:
    def __init__(self, active: Iterable[str] | None = None, completed: Iterable[str] | None = None):
        self.active: set[str] = {str(x) for x in (active or []) if self.get(x)}
        self.completed: set[str] = {str(x) for x in (completed or []) if self.get(x)}

    @staticmethod
    def get(challenge_id: str) -> ChallengeDef | None:
        for ch in CHALLENGES:
            if ch.id == str(challenge_id):
                return ch
        return None

    def toggle(self, challenge_id: str) -> bool:
        ch = self.get(challenge_id)
        if ch is None:
            return False
        if ch.id in self.active:
            self.active.remove(ch.id)
            return False
        self.active.add(ch.id)
        return True

    def apply_to_bosses(self, bosses: Iterable[object]) -> None:
        mult = 1.0
        for cid in self.active:
            ch = self.get(cid)
            if ch:
                mult *= float(ch.params.get("boss_spawn_scale", 1.0))
        if mult == 1.0:
            return
        for boss in bosses:
            if hasattr(boss, "_spawn_scale"):
                boss._spawn_scale *= mult
            if hasattr(boss, "_spawn_remaining"):
                boss._spawn_remaining *= mult

    def band_scale(self) -> float:
        scale = 1.0
        for cid in self.active:
            ch = self.get(cid)
            if ch:
                scale *= float(ch.params.get("healthy_band_scale", 1.0))
        return scale

    def starting_money(self, base: int) -> int:
        value = float(base)
        for cid in self.active:
            ch = self.get(cid)
            if ch:
                value *= float(ch.params.get("start_money_mult", 1.0))
        return max(0, int(round(value)))

    def cloud_limit(self, week_index: int, default: int) -> int:
        limit = int(default)
        for cid in self.active:
            ch = self.get(cid)
            if ch and int(week_index) < int(ch.params.get("one_cloud_until_week", 0)):
                limit = min(limit, 1)
        return limit

    def mark_completed(self, challenge_id: str, legacy: LegacyTracker | None = None) -> None:
        ch = self.get(challenge_id)
        if ch is None:
            return
        self.completed.add(ch.id)
        if legacy is not None:
            legacy.mark_challenge_complete(ch.id)

    def to_dict(self) -> dict:
        return {"active": sorted(self.active), "completed": sorted(self.completed)}

    @classmethod
    def from_dict(cls, data: dict | None) -> "ChallengeLadder":
        data = data or {}
        return cls(data.get("active", []), data.get("completed", []))


@dataclass
class EverbloomQuest:
    unlocked: bool = False

    def progress(self, legacy: LegacyTracker) -> dict[str, tuple[int, int]]:
        return {
            "Legacy": (legacy.percent(), int(EVERBLOOM_LEGACY_REQUIRED)),
            "Crops": (len(legacy.discovered_crops), int(EVERBLOOM_DISCOVERED_CROPS_REQUIRED)),
            "Earned": (int(legacy.total_earned), int(EVERBLOOM_TOTAL_EARNED_REQUIRED)),
        }

    def is_unlocked(self, legacy: LegacyTracker) -> bool:
        if self.unlocked:
            return True
        checks = self.progress(legacy)
        return all(cur >= need for cur, need in checks.values())

    def refresh(self, legacy: LegacyTracker) -> bool:
        if self.is_unlocked(legacy):
            self.unlocked = True
        return self.unlocked

    def help_lines(self, legacy: LegacyTracker) -> tuple[str, ...]:
        if self.is_unlocked(legacy):
            return ("Quest complete: Everbloom seeds unlocked.",)
        return tuple(f"{name} {cur}/{need}" for name, (cur, need) in self.progress(legacy).items())

    def to_dict(self) -> dict:
        return {"unlocked": bool(self.unlocked)}

    @classmethod
    def from_dict(cls, data: dict | None) -> "EverbloomQuest":
        return cls(bool((data or {}).get("unlocked", False)))


@dataclass
class EndgameState:
    legacy: LegacyTracker = field(default_factory=LegacyTracker)
    ladder: ChallengeLadder = field(default_factory=ChallengeLadder)
    everbloom: EverbloomQuest = field(default_factory=EverbloomQuest)
    last_preview: NextYearPreview | None = None

    def to_dict(self) -> dict:
        return {
            "legacy": self.legacy.to_dict(),
            "ladder": self.ladder.to_dict(),
            "everbloom": self.everbloom.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "EndgameState":
        data = data or {}
        return cls(
            legacy=LegacyTracker.from_dict(data.get("legacy")),
            ladder=ChallengeLadder.from_dict(data.get("ladder")),
            everbloom=EverbloomQuest.from_dict(data.get("everbloom")),
        )


def draw_legacy_line(surface: pygame.Surface, font: pygame.font.Font, state: EndgameState, pos: tuple[int, int]) -> None:
    text = f"Legacy {state.legacy.percent()}%"
    img = font.render(text, True, (210, 245, 220))
    surface.blit(img, pos)


def draw_preview(surface: pygame.Surface, font: pygame.font.Font, preview: NextYearPreview, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, (28, 32, 44), rect, border_radius=8)
    pygame.draw.rect(surface, (130, 170, 150), rect, 2, border_radius=8)
    y = rect.y + 8
    title = font.render(preview.title, True, (245, 238, 210))
    surface.blit(title, (rect.x + 10, y))
    y += title.get_height() + 4
    for line in preview.lines[:4]:
        img = font.render(line, True, (210, 225, 210))
        surface.blit(img, (rect.x + 10, y))
        y += img.get_height() + 2


def sync_legacy_from_game(state: EndgameState, game) -> None:
    state.legacy.total_earned = max(int(state.legacy.total_earned), int(getattr(game, "_total_earned", 0)))
    alm = getattr(game, "_almanac", None)
    if alm is not None:
        state.legacy.best_year_reached = max(int(state.legacy.best_year_reached), int(getattr(alm, "year_index", 0)) + 1)
    # Only real crop products count toward discovery. Inventory also holds non-crop
    # byproducts (Compost, seed items, reward items) that must not inflate the
    # Everbloom gate or the Legacy crop slice.
    crop_products = {getattr(s, "product_name", None) for s in getattr(game, "seeds", [])}
    crop_products.discard(None)
    for inv_name in list(getattr(game, "inventory", {}).keys()) + list(getattr(game, "_golden_inventory", {}).keys()):
        if inv_name in crop_products:
            state.legacy.record_crop(inv_name, 1)
    state.everbloom.refresh(state.legacy)


def ensure_game_endgame(game) -> EndgameState:
    state = getattr(game, "_endgame", None)
    if not isinstance(state, EndgameState):
        state = EndgameState()
        game._endgame = state
    _ensure_everbloom_seed(game)
    return state


def _ensure_everbloom_seed(game) -> None:
    from plants import Everbloom

    seeds = getattr(game, "seeds", None)
    if seeds is None:
        return
    if not any(type(seed).__name__ == "Everbloom" for seed in seeds):
        seeds.append(Everbloom())
        # The base __init__ art loaders already ran before this seed was appended,
        # so load its icon + phase sprites now (the loaders skip cached filenames).
        for loader_name in ("_load_seed_icons", "_load_plant_phases"):
            loader = getattr(game, loader_name, None)
            if callable(loader):
                try:
                    loader()
                except Exception:
                    pass


def install_game_hooks(GameClass) -> None:
    if getattr(GameClass, "_endgame_hooks_installed", False):
        return

    import json
    import os
    import game as game_mod
    from plants import Everbloom

    orig_init = GameClass.__init__
    orig_seed_lookup = GameClass._seed_lookup
    orig_save = GameClass.save_game
    orig_load = GameClass.load_game
    orig_is_seed_unlocked = GameClass._is_seed_unlocked
    orig_seed_help_lines = GameClass._seed_help_lines
    orig_apply_year_capstone = GameClass._apply_year_capstone
    orig_harvest = GameClass._harvest

    def patched_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        ensure_game_endgame(self)
        sync_legacy_from_game(self._endgame, self)

    def patched_seed_lookup(self):
        lookup = dict(orig_seed_lookup(self))
        lookup.setdefault("Everbloom", Everbloom())
        return lookup

    def patched_save_game(self, flash=True):
        state = ensure_game_endgame(self)
        sync_legacy_from_game(state, self)
        orig_save(self, flash=flash)
        path = game_mod.SAVE_PATH
        try:
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["endgame"] = state.to_dict()
            tmp_path = str(path) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)  # atomic: the on-disk save is always complete
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def patched_load_game(self):
        ensure_game_endgame(self)
        orig_load(self)
        path = game_mod.SAVE_PATH
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            data = {}
        self._endgame = EndgameState.from_dict(data.get("endgame"))
        ensure_game_endgame(self)
        sync_legacy_from_game(self._endgame, self)

    def patched_is_seed_unlocked(self, seed):
        if getattr(seed, "legacy_quest_seed", False):
            state = ensure_game_endgame(self)
            return state.everbloom.is_unlocked(state.legacy)
        return orig_is_seed_unlocked(self, seed)

    def patched_seed_help_lines(self, seed):
        lines = list(orig_seed_help_lines(self, seed))
        if getattr(seed, "legacy_quest_seed", False):
            lines.extend(ensure_game_endgame(self).everbloom.help_lines(self._endgame.legacy))
        return lines

    def patched_apply_year_capstone(self, cap):
        state = ensure_game_endgame(self)
        if cap is not None:
            state.last_preview = compute_next_year_preview(getattr(self, "_almanac", None), int(getattr(cap, "year", 0)), getattr(self, "_bosses", None))
            state.legacy.record_year(int(getattr(cap, "year", 0)))
        return orig_apply_year_capstone(self, cap)

    def patched_harvest(self, slot):
        seed = getattr(slot, "seed", None)
        product = getattr(seed, "product_name", None)
        amount = int(getattr(seed, "harvest_yield", 1)) if seed is not None else 0
        golden = bool(getattr(slot, "is_golden", False))
        result = orig_harvest(self, slot)
        if product and amount > 0:
            state = ensure_game_endgame(self)
            state.legacy.record_crop(product, amount, golden=golden)
            if product == "Everbloom":
                state.legacy.everbloom_harvests += amount
            state.everbloom.refresh(state.legacy)
        return result

    GameClass.__init__ = patched_init
    GameClass._seed_lookup = patched_seed_lookup
    GameClass.save_game = patched_save_game
    GameClass.load_game = patched_load_game
    GameClass._is_seed_unlocked = patched_is_seed_unlocked
    GameClass._seed_help_lines = patched_seed_help_lines
    GameClass._apply_year_capstone = patched_apply_year_capstone
    GameClass._harvest = patched_harvest
    GameClass._endgame_hooks_installed = True
