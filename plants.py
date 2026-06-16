from __future__ import annotations

from abc import ABC


class PlantType(ABC):
    """Static plant definition used by the farm system.

    Create a new plant by subclassing PlantType and setting class attributes.
    Then add an instance to Game.seeds in game.py.

    Required fields:
    - name: display name used in UI and tooltips
    - cost: seed price shown in the seed panel
    - product_name: inventory item name produced on harvest
    - growth_stages: number of growth stages (matches phase sprites count)
    - seconds_per_stage: seconds needed to advance a stage
    - water_min/max: healthy range for water
    - sun_min/max: healthy range for sun
    - base_color: fallback color if no sprite is provided
    - icon_filename: 64x64 icon used in the seed panel
    - phase_filenames: list of 48x48 sprites for growth stages
    """
    name: str
    cost: int
    product_name: str
    growth_stages: int
    seconds_per_stage: float
    water_min: float
    water_max: float
    sun_min: float
    sun_max: float
    base_color: tuple[int, int, int]
    icon_filename: str
    phase_filenames: list[str]
    harvest_yield: int = 1
    regrow_to_stage: int | None = None
    # If set, the per-stage time used AFTER the first harvest (regrow cycle).
    # Lets re-fruiting plants (e.g. Apple) regrow slower without mutating the
    # shared PlantType instance. None = reuse seconds_per_stage.
    regrow_seconds_per_stage: float | None = None
    sprite_w: int | None = None
    sprite_h: int | None = None
    seed_item_name: str | None = None
    # Total money earned (from selling) required before this seed unlocks. 0 =
    # available from the start. Used by the seed panel to gate/dim crops.
    unlock_at: int = 0
    description: str = ""  # one-line blurb for seed panel / tooltips
    # ── optional gimmick flags (read via getattr; safe defaults keep all
    #    existing crops unchanged) ──────────────────────────────────────────
    neighbor_sun_bonus: float = 0.0          # Sunflower: per-frame sun added to neighbors
    grows_only_at_night: bool = False        # Moonpetal: growth gated to darkness >= 0.5
    boss_growth_mult: float = 1.0            # Lightning Vine: growth x while a boss is active
    lightning_surge_on_strike: bool = False  # Lightning Vine: a strike surges instead of killing
    spreads_on_harvest: bool = False         # Mushroom: seed a free empty neighbor on harvest
    neighbor_sun_penalty: float = 0.0        # Fern: per-frame sun SUBTRACTED from neighbors
    neighbor_water_bonus: float = 0.0        # Reed: per-frame water ADDED to neighbors
    pollinatable: bool = False               # Clover/flowers: eligible as future bee bait

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class Carrot(PlantType):
    name = "Carrot"
    cost = 3
    product_name = "Carrot"
    growth_stages = 3
    seconds_per_stage = 6.0
    harvest_yield = 2
    water_min = 35.0
    water_max = 95.0
    sun_min = 50.0
    sun_max = 100.0
    base_color = (230, 140, 60)
    icon_filename = "carrot_icon.png"
    phase_filenames = [
        "carrot_phase1.png",
        "carrot_phase2.png",
        "carrot_phase3.png",
    ]
    description = "Forgiving starter. Its soil dries out, so rain on it now and then to keep it golden."


class Lettuce(PlantType):
    name = "Lettuce"
    cost = 4
    product_name = "Lettuce"
    growth_stages = 3
    seconds_per_stage = 4.0
    water_min = 50.0
    water_max = 85.0
    sun_min = 0.0
    sun_max = 40.0
    base_color = (90, 180, 90)
    icon_filename = "lettuce_icon.png"
    phase_filenames = [
        "lettuce_phase1.png",
        "lettuce_phase2.png",
        "lettuce_phase3.png",
    ]
    description = "A shade-lover. Park a cloud over it: that both shades it and waters it."


class Tomato(PlantType):
    name = "Tomato"
    cost = 8
    unlock_at = 25
    product_name = "Tomato"
    growth_stages = 4
    seconds_per_stage = 5.0
    water_min = 40.0
    water_max = 75.0
    sun_min = 55.0
    sun_max = 95.0
    base_color = (200, 70, 70)
    icon_filename = "tomato_icon.png"
    phase_filenames = [
        "tomato_phase1.png",
        "tomato_phase2.png",
        "tomato_phase3.png",
        "tomato_phase4.png",
    ]
    pollinatable = True
    description = "A thirsty sun-lover that sells for more. Wants bright sun and steady water."


class Apple(PlantType):
    name = "Apple"
    cost = 28
    unlock_at = 400
    product_name = "Apple"
    growth_stages = 4
    seconds_per_stage = 7.0
    water_min = 35.0
    water_max = 80.0
    sun_min = 40.0
    sun_max = 85.0
    base_color = (200, 60, 60)
    icon_filename = "apple_icon.png"
    phase_filenames = [
        "apple_phase1.png",
        "apple_phase2.png",
        "apple_phase3.png",
        "apple_phase4.png",
    ]
    harvest_yield = 5 #collect 5 apples per harvest
    regrow_to_stage = 3 #tree will go back to stage 3 after harvest
    regrow_seconds_per_stage = 22.0 #slow re-fruit (was a shared-instance mutation bug)
    sprite_w = 170
    sprite_h = 280 # since apple trees are taller than carrots!
    pollinatable = True
    description = "Regrows after harvest. Yields many apples at once."


class StormSeed(PlantType):
    """Rare seed dropped by the Storm Titan.

    This seed is planted by consuming an inventory item (seed_item_name) rather
    than spending money.
    """

    name = "Storm Seed"
    cost = 0
    seed_item_name = "Storm Seed"
    product_name = "Storm Crystal"
    growth_stages = 4
    seconds_per_stage = 5.5
    water_min = 40.0
    water_max = 85.0
    sun_min = 15.0
    sun_max = 65.0
    base_color = (170, 120, 220)
    icon_filename = "storm_seed_icon.png"
    phase_filenames = [
        "storm_seed_phase1.png",
        "storm_seed_phase2.png",
        "storm_seed_phase3.png",
        "storm_seed_phase4.png",
    ]
    description = "Boss reward seed. Needs shade; planted from inventory."


class Mushroom(PlantType):
    name = "Mushroom"
    cost = 4
    unlock_at = 170
    product_name = "Mushroom"
    growth_stages = 2
    seconds_per_stage = 6.0
    water_min = 60.0
    water_max = 95.0
    sun_min = 0.0
    sun_max = 40.0
    base_color = (180, 140, 120)
    icon_filename = "mushroom_icon.png"
    phase_filenames = [
        "mushroom_phase1.png",
        "mushroom_phase2.png",
    ]
    spreads_on_harvest = True
    description = "Loves rain/low sun. On harvest, seeds a free empty neighbor."


class Cactus(PlantType):
    name = "Cactus"
    cost = 6
    unlock_at = 60
    product_name = "Cactus Fruit"
    growth_stages = 3
    seconds_per_stage = 5.0
    water_min = 10.0
    water_max = 50.0
    sun_min = 60.0
    sun_max = 100.0
    base_color = (120, 200, 100)
    icon_filename = "cactus_icon.png"
    phase_filenames = [
        "cactus_phase1.png",
        "cactus_phase2.png",
        "cactus_phase3.png",
    ]
    description = "Thrives in bright sun with little water."


class Rice(PlantType):
    name = "Rice"
    cost = 4
    unlock_at = 230
    product_name = "Rice"
    growth_stages = 3
    seconds_per_stage = 3.5
    harvest_yield = 2
    water_min = 70.0
    water_max = 100.0
    sun_min = 30.0
    sun_max = 80.0
    base_color = (220, 200, 120)
    icon_filename = "rice_icon.png"
    phase_filenames = [
        "rice_phase1.png",
        "rice_phase2.png",
        "rice_phase3.png",
    ]
    description = "Keep it wet. Steady crop for rainy weather."


class NightBloom(PlantType):
    name = "Night Bloom"
    cost = 16
    unlock_at = 300
    product_name = "Night Bloom"
    growth_stages = 4
    seconds_per_stage = 6.0
    water_min = 40.0
    water_max = 80.0
    sun_min = 0.0
    sun_max = 30.0
    base_color = (90, 40, 160)
    icon_filename = "nightbloom_icon.png"
    phase_filenames = [
        "nightbloom_phase1.png",
        "nightbloom_phase2.png",
        "nightbloom_phase3.png",
        "nightbloom_phase4.png",
    ]
    description = "Shade-loving flower. Avoid bright midday sun."


class Pumpkin(PlantType):
    name = "Pumpkin"
    cost = 12
    unlock_at = 110
    product_name = "Pumpkin"
    growth_stages = 4
    seconds_per_stage = 5.5
    water_min = 50.0
    water_max = 85.0
    sun_min = 45.0
    sun_max = 90.0
    base_color = (220, 130, 60)
    icon_filename = "pumpkin_icon.png"
    phase_filenames = [
        "pumpkin_phase1.png",
        "pumpkin_phase2.png",
        "pumpkin_phase3.png",
        "pumpkin_phase4.png",
    ]
    pollinatable = True
    description = "Slow but valuable. Balanced water and sun."


class Sunflower(PlantType):
    name = "Sunflower"
    cost = 8
    unlock_at = 130
    product_name = "Sunflower Head"
    growth_stages = 3
    seconds_per_stage = 5.0
    water_min = 30.0
    water_max = 70.0
    sun_min = 55.0
    sun_max = 100.0
    base_color = (240, 200, 60)
    icon_filename = "sunflower_icon.png"
    phase_filenames = [
        "sunflower_phase1.png",
        "sunflower_phase2.png",
        "sunflower_phase3.png",
    ]
    neighbor_sun_bonus = 0.05  # while mature, warms both neighbors with extra sun
    pollinatable = True
    description = "When ripe, gives its two neighbors extra sun. Loves bright light."


class Moonpetal(PlantType):
    name = "Moonpetal"
    cost = 14
    unlock_at = 320
    product_name = "Moonpetal"
    growth_stages = 4
    seconds_per_stage = 5.5
    water_min = 40.0
    water_max = 80.0
    sun_min = 0.0
    sun_max = 35.0
    base_color = (150, 120, 220)
    icon_filename = "moonpetal_icon.png"
    phase_filenames = [
        "moonpetal_phase1.png",
        "moonpetal_phase2.png",
        "moonpetal_phase3.png",
        "moonpetal_phase4.png",
    ]
    grows_only_at_night = True  # only advances growth while the sky is dark
    description = "Only grows at night (shade the sun). Bright light kills it."


class LightningVine(PlantType):
    """Grown from a Storm Crystal. Feeds on storms; lightning makes it surge."""

    name = "Lightning Vine"
    cost = 0
    seed_item_name = "Storm Crystal"
    product_name = "Charged Crystal"
    growth_stages = 4
    seconds_per_stage = 6.0
    water_min = 40.0
    water_max = 85.0
    sun_min = 15.0
    sun_max = 65.0
    base_color = (190, 225, 255)
    icon_filename = "lightningvine_icon.png"
    phase_filenames = [
        "lightningvine_phase1.png",
        "lightningvine_phase2.png",
        "lightningvine_phase3.png",
        "lightningvine_phase4.png",
    ]
    boss_growth_mult = 2.0             # grows twice as fast while any boss is active
    lightning_surge_on_strike = True   # a boss strike surges it a stage instead of killing
    description = "Planted from a Storm Crystal. Thrives in storms; lightning surges it."


class Fern(PlantType):
    """Canopy crop. While ripe it casts shade onto both neighbors, letting the
    player manufacture a little shade by layout instead of parking a cloud. The
    relief is single-axis (sun only) and a fixed, small amount, so a real cloud,
    which zeroes sun gain and also waters, stays the stronger tool."""

    name = "Fern"
    cost = 6
    unlock_at = 180
    product_name = "Fern Frond"
    growth_stages = 3
    seconds_per_stage = 4.5
    water_min = 55.0
    water_max = 90.0
    sun_min = 0.0
    sun_max = 35.0
    base_color = (48, 132, 104)
    icon_filename = "fern_icon.png"
    phase_filenames = [
        "fern_phase1.png",
        "fern_phase2.png",
        "fern_phase3.png",
    ]
    neighbor_sun_penalty = 0.08  # while ripe, shades both neighbors (sun subtracted)
    description = "A thirsty shade-lover. When ripe it shades its two neighbors."


class Reed(PlantType):
    """Soaker crop. While ripe it sheds water onto both neighbors, letting the
    player manufacture a little watering by layout. Single-axis (water only) and
    a fixed, small amount, so a raining cloud, which waters far harder and also
    shades, stays the stronger tool. Reed is itself thirsty, so it costs a slot."""

    name = "Reed"
    cost = 6
    unlock_at = 210
    product_name = "Reed"
    growth_stages = 3
    seconds_per_stage = 4.5
    water_min = 70.0
    water_max = 100.0
    sun_min = 20.0
    sun_max = 70.0
    base_color = (176, 184, 88)
    icon_filename = "reed_icon.png"
    phase_filenames = [
        "reed_phase1.png",
        "reed_phase2.png",
        "reed_phase3.png",
    ]
    neighbor_water_bonus = 0.06  # while ripe, waters both neighbors (water added)
    description = "A thirsty water-lover. When ripe it waters its two neighbors."


class Clover(PlantType):
    """Cheap filler flower. Its real job is to be pollinator bait once the bee
    system lands, so it carries the pollinatable flag. Easy on sun, but its soil
    dries out over its life, so it wants a little rain to finish golden."""

    name = "Clover"
    cost = 2
    unlock_at = 90
    product_name = "Clover"
    growth_stages = 2
    seconds_per_stage = 8.0
    harvest_yield = 2
    water_min = 40.0
    water_max = 80.0
    sun_min = 40.0
    sun_max = 90.0
    base_color = (150, 210, 70)
    icon_filename = "clover_icon.png"
    phase_filenames = [
        "clover_phase1.png",
        "clover_phase2.png",
    ]
    pollinatable = True  # a pollinator favorite (bee system coming later)
    description = "Cheap pollinator favorite. Needs shade breaks to stay golden."


class Orchid(PlantType):
    """Diva crop. A razor-thin healthy band ties up a whole cloud's attention for
    one slot, but it pays out big. Gated late as an end-game flex."""

    name = "Orchid"
    cost = 30
    unlock_at = 550
    product_name = "Orchid Bloom"
    growth_stages = 4
    seconds_per_stage = 6.5
    water_min = 55.0
    water_max = 70.0
    sun_min = 45.0
    sun_max = 58.0
    base_color = (210, 70, 165)
    icon_filename = "orchid_icon.png"
    phase_filenames = [
        "orchid_phase1.png",
        "orchid_phase2.png",
        "orchid_phase3.png",
        "orchid_phase4.png",
    ]
    description = "A diva with a razor-thin happy band. Sells for a fortune."

class Everbloom(PlantType):
    name = "Everbloom"
    cost = 40
    unlock_at = 0
    product_name = "Everbloom"
    growth_stages = 5
    seconds_per_stage = 7.0
    water_min = 45.0
    water_max = 68.0
    sun_min = 38.0
    sun_max = 62.0
    base_color = (122, 220, 205)
    icon_filename = "everbloom_icon.png"
    phase_filenames = [
        "everbloom_phase1.png",
        "everbloom_phase2.png",
        "everbloom_phase3.png",
        "everbloom_phase4.png",
        "everbloom_phase5.png",
    ]
    harvest_yield = 1
    regrow_to_stage = 4
    regrow_seconds_per_stage = 28.0
    pollinatable = True
    legacy_quest_seed = True
    prestige_crop = True
    cosmetic_glow = True
    description = "Late-game prestige flower. Regrows, pays well, and needs a tight water and sun band."
