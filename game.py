import os
import random
import pygame
from settings import (
    TITLE, SCREEN_W, SCREEN_H, FPS,
    SKY_DAY, SKY_DARK,
    UI_PANEL_W, GROUND_HEIGHT_PCT, SLOT_COUNT,
    SLOT_PADDING, SLOT_COLOR, SLOT_BORDER_COLOR,
    GROUND_COLOR,
    WATER_GAIN_RAIN_LIGHT, WATER_GAIN_RAIN_HEAVY, WATER_LOSS, SUN_GAIN_CLEAR,
    SUN_LOSS, OVERWATER_THRESHOLD, OVERSUN_THRESHOLD,
    PLANT_BAD_SECONDS_TO_DIE, PLANT_BAD_RECOVERY_RATE,
    PLANT_GROWTH_RATE_GOOD, PLANT_GROWTH_RATE_BAD,
    PLANT_SPRITE_W, PLANT_SPRITE_H,
    HEAVY_RAIN_GROWTH_MULT,
    CLOUD_START_X, CLOUD_START_Y, CLOUD2_START_X, CLOUD2_START_Y,
    IN_GAME_DAY_SECONDS, IN_GAME_DAYS_PER_WEEK,
    SEASON_NAMES,
    SEASON_GROWTH_MULT, SEASON_WATER_LOSS_MULT, SEASON_SUN_GAIN_MULT,
    MARKET_FEATURED_MULT, MARKET_DISCOUNT_MULT,
    WIND_SPEED,
    WEATHER_EVENT_WEIGHTS, WEATHER_EVENT_DURATION_SECONDS,
    WEATHER_HEATWAVE_WATER_LOSS_MULT, WEATHER_HEATWAVE_SUN_GAIN_MULT,
    WEATHER_DRIZZLE_WATER_BONUS, WEATHER_DRIZZLE_SUN_GAIN_MULT,
    WEATHER_GUSTS_WIND_MULT,
    COMPOST_ITEM_NAME, COMPOST_FROM_DEAD_PLANT, COMPOST_BOOST_SECONDS, COMPOST_GROWTH_MULT,
    SCARECROW_COST, SCARECROW_RADIUS_SLOTS,
    LIGHTNING_ROD_COST, LIGHTNING_ROD_CHARGES,
)
from cloud import Cloud
from sun import Sun
from moon import Moon
from stars import Stars
from farming import PlantSlot
from plants import PlantType, Carrot, Lettuce, Tomato, Apple, StormSeed
from items import ITEMS
from storm_titan import StormTitan
from cyclone_titan import CycloneTitan
from critters import make_squirrel, make_snake

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")

# Tool IDs (kept as strings so the UI/event code stays simple)
TOOL_COMPOST = "compost"
TOOL_SCARECROW = "scarecrow"
TOOL_LIGHTNING_ROD = "lightning_rod"

TOOL_ICON_FILENAMES = {
    TOOL_COMPOST: "compost_icon.png",
    TOOL_SCARECROW: "scarecrow_icon.png",
    TOOL_LIGHTNING_ROD: "lightning_rod_icon.png",
}


class Game:
    """
    Core game loop.  All state lives here; sprites are kept in groups so that
    future contributors can easily add more sprites or layers.
    """

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED | pygame.FULLSCREEN)
        pygame.display.set_caption(TITLE)
        self.clock  = pygame.time.Clock()
        self.paused = False

        # ── sprites ───────────────────────────────────────────────────────────
        self.sun   = Sun()
        self.moon = Moon()
        self.stars = Stars()
        self._darkness = 0.0

        # ── world time / seasons ───────────────────────────────────────────
        # I only advance world time while unpaused.
        self._rng = random.Random()
        self._world_seconds = 0.0
        self._day_index = 0
        self._week_index = 0
        self._season_index = 0
        self._last_day_index = -1
        self._last_week_index = -1

        # ── market (daily sell multipliers) ────────────────────────────────
        self._market_featured_item = None
        self._market_discounted_item = None

        # ── weather events (rolled daily) ─────────────────────────────────
        self._weather_event = "None"
        self._weather_remaining = 0.0

        # ── boss ─────────────────────────────────────────────────────────────
        self.storm_titan = StormTitan()
        self.cyclone_titan = CycloneTitan()
        # Priority order when multiple bosses are ready to spawn.
        self._bosses = [self.cyclone_titan, self.storm_titan]

        #controls for cloud2
        WASD = {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "up": pygame.K_w,
            "down": pygame.K_s,
        }
        self.clouds = {
            Cloud(start_pos=(CLOUD_START_X, CLOUD_START_Y)),
            Cloud(start_pos=(CLOUD2_START_X, CLOUD2_START_Y), controls=WASD)
        }

        self.all_sprites = pygame.sprite.Group(self.sun, *self.clouds)

        # ── sky transition ────────────────────────────────────────────────────
        self._sky_color = list(SKY_DAY)   # mutable for lerp
        self._font = pygame.font.SysFont("arial", 18)
        self._small_font = pygame.font.SysFont("arial", 16)

        # ── farm setup ─────────────────────────────────────────────────────────
        self._ground_height = int(SCREEN_H * GROUND_HEIGHT_PCT)
        self._field_rect = pygame.Rect(0, 0, SCREEN_W - UI_PANEL_W, SCREEN_H)
        self._ground_rect = pygame.Rect(
            0, SCREEN_H - self._ground_height, self._field_rect.width, self._ground_height,
        )

        # ── critters ─────────────────────────────────────────────────────────
        self.squirrel = make_squirrel()
        self.snake = make_snake()
        self._critters = [self.squirrel, self.snake]

        # Add new plants by instantiating PlantType subclasses here.
        self.seeds: list[PlantType] = [Carrot(), Lettuce(), Tomato(), Apple(), StormSeed()]
        self.money = 20
        self.inventory: dict[str, int] = {}
        self.items = ITEMS
        self.drag_seed: PlantType | None = None
        self.selected_seed: PlantType | None = None
        self.selected_tool = None
        self._seed_buttons: list[tuple[PlantType, pygame.Rect]] = []
        self._seed_icons: dict[str, pygame.Surface] = {}
        self._tool_buttons: list[tuple[str, pygame.Rect]] = []
        self._tool_icons: dict[str, pygame.Surface] = {}
        self._plant_phase_icons: dict[str, pygame.Surface] = {}
        self._hover_slot: PlantSlot | None = None
        self._sell_button = pygame.Rect(0, 0, 0, 0)
        self._money_flash_timer = 0
        self._ui_panel_image: pygame.Surface | None = None
        self._coin_icon: pygame.Surface | None = None
        self._dead_plant_image: pygame.Surface | None = None
        # sell confirmation UI
        self._pending_sell_total: int | None = None
        self._show_sell_confirm: bool = False
        self._sell_confirm_buttons: dict[str, pygame.Rect] = {}

        self.slots = self._create_slots()
        self._load_seed_icons()
        self._load_ui_panel()
        self._load_coin_icon()
        self._load_tool_icons()
        self._load_plant_phases()
        self._load_dead_plant()

        #  ── pause menu buttons ────────────────────────────────────────────────
        self._pause_resume_btn = pygame.Rect(SCREEN_W // 2 - 100, SCREEN_H // 2 - 15, 200, 45)
        self._pause_quit_btn = pygame.Rect(SCREEN_W // 2 - 100, SCREEN_H // 2 + 35, 200, 45)

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                    self.paused = not self.paused
                if event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                    self._toggle_boss(self.storm_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                    self._toggle_boss(self.cyclone_titan)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_v:
                    self.squirrel.force_spawn(field_rect=self._field_rect, ground_rect=self._ground_rect)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_n:
                    self.snake.force_spawn(field_rect=self._field_rect, ground_rect=self._ground_rect)

                if self._handle_critter_event(event):
                    continue
                if not self.paused:
                    for c in self.clouds:
                        c.handle_event(event)
                if self.paused:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self._pause_resume_btn.collidepoint(event.pos):
                            self.paused = False
                        if self._pause_quit_btn.collidepoint(event.pos):
                            running = False
                self._handle_farm_event(event)

            self._update()
            self._draw()

    # ── update ────────────────────────────────────────────────────────────────
    def _update(self):
        self.all_sprites.update()

        dt = self.clock.get_time() / 1000.0

        if self._money_flash_timer > 0:
            self._money_flash_timer -= 1

        # lerp sky colour toward target
        target = SKY_DARK if any(c.covers_sun(self.sun.circle_rect) for c in self.clouds) else SKY_DAY
        for i in range(3):
            diff = target[i] - self._sky_color[i]
            self._sky_color[i] += diff * 0.04   # smooth transition speed

        #derive darkness level (uses red)
        denominator = max(1, SKY_DAY[0] - SKY_DARK[0])
        self._darkness = max(0.0, min(1.0, (SKY_DAY[0] - self._sky_color[0])/denominator ))

        if not self.paused:
            self._update_world_time(dt)
            self._update_weather(dt)

            # Weather can temporarily amplify wind.
            wind_mult = float(WEATHER_GUSTS_WIND_MULT) if self._weather_event == "Gusts" else 1.0
            for c in self.clouds:
                c.wind_speed = float(WIND_SPEED) * wind_mult
                c.update_movement()

            self._update_bosses(dt)
            self._update_critters(dt)
            self._update_plants()
        self.stars.update(dt)

    def _update_world_time(self, dt: float) -> None:
        if dt <= 0.0:
            return

        self._world_seconds += dt
        day_index = int(self._world_seconds // float(IN_GAME_DAY_SECONDS))
        week_index = int(day_index // int(IN_GAME_DAYS_PER_WEEK))

        self._day_index = day_index
        if day_index != self._last_day_index:
            self._last_day_index = day_index
            self._on_new_day(day_index)

        if week_index != self._week_index:
            self._week_index = week_index
            if SEASON_NAMES:
                self._season_index = week_index % len(SEASON_NAMES)
            else:
                self._season_index = 0

    def _roll_market_for_day(self) -> None:
        # Pick a daily featured item and a discounted item from sellable items.
        sellable: list[str] = [
            name for name, item in self.items.items() if int(getattr(item, "sell_price", 0)) > 0
        ]
        if len(sellable) < 2:
            self._market_featured_item = None
            self._market_discounted_item = None
            return

        featured = self._rng.choice(sellable)
        discounted_pool = [n for n in sellable if n != featured]
        discounted = self._rng.choice(discounted_pool) if discounted_pool else None

        self._market_featured_item = featured
        self._market_discounted_item = discounted

    def _on_new_day(self, day_index: int) -> None:
        # I keep daily rolls in one place so future systems can hook in cleanly.
        self._roll_market_for_day()
        self._roll_weather_for_day(day_index)

    def _roll_weather_for_day(self, day_index: int) -> None:
        # Weighted random pick from WEATHER_EVENT_WEIGHTS.
        # day_index is currently unused, but I keep it here so later contributors
        # can do day-based patterns if they want.
        _ = day_index

        total = 0.0
        for w in WEATHER_EVENT_WEIGHTS.values():
            total += max(0.0, float(w))
        if total <= 0.0:
            self._weather_event = "None"
            self._weather_remaining = 0.0
            return

        roll = self._rng.random() * total
        acc = 0.0
        chosen = "None"
        for name, w in WEATHER_EVENT_WEIGHTS.items():
            acc += max(0.0, float(w))
            if roll <= acc:
                chosen = str(name)
                break

        self._weather_event = chosen
        self._weather_remaining = float(WEATHER_EVENT_DURATION_SECONDS) if chosen != "None" else 0.0

    def _update_weather(self, dt: float) -> None:
        if dt <= 0.0:
            return
        if self._weather_event == "None":
            return
        self._weather_remaining = max(0.0, self._weather_remaining - dt)
        if self._weather_remaining <= 0.0:
            self._weather_event = "None"

    def _market_mult_for_item(self, name: str) -> float:
        if self._market_featured_item and name == self._market_featured_item:
            return float(MARKET_FEATURED_MULT)
        if self._market_discounted_item and name == self._market_discounted_item:
            return float(MARKET_DISCOUNT_MULT)
        return 1.0

    # ── draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(tuple(int(c) for c in self._sky_color))

        self.stars.draw(self.screen, self._darkness)
        sun_alpha = int(255 *(1 - self._darkness))
        moon_alpha = int (255 * self._darkness)
        if sun_alpha > 0:
            self.sun.image.set_alpha(sun_alpha)
            self.screen.blit(self.sun.image, self.sun.rect)
        if moon_alpha > 0:
            self.moon.image.set_alpha(moon_alpha)
            self.screen.blit(self.moon.image, self.moon.rect)

        self.storm_titan.draw_body(self.screen)
        self.cyclone_titan.draw_body(self.screen)

        for c in self.clouds:
            c.draw_rain(self.screen)
            self.screen.blit(c.image, c.rect)

        self._draw_ground()
        self._draw_slots()
        self._draw_shadow()
        self._draw_critters()

        self.storm_titan.draw_bolt(self.screen)
        self.storm_titan.draw_warning(self.screen, slots=self.slots)

        self.cyclone_titan.draw_bolt(self.screen)
        self.cyclone_titan.draw_warning(self.screen, slots=self.slots)

        self._draw_boss_health_bar()

        self._draw_ui_panel()
        self._draw_hover_tooltip()
        self._draw_drag_seed()
        self._draw_hud()
        if self.paused:
            self._draw_pause_window()
        if self._show_sell_confirm:
            self._draw_sell_confirm()
        pygame.display.flip()

    def _draw_hud(self):
        hints = []

        day_in_week = (self._day_index % int(IN_GAME_DAYS_PER_WEEK)) + 1
        week = self._week_index + 1
        season = SEASON_NAMES[self._season_index] if SEASON_NAMES else "Season"
        hints.append(f"Day {day_in_week}/{IN_GAME_DAYS_PER_WEEK}  Week {week}  Season: {season}")

        if self._market_featured_item and self._market_discounted_item:
            hot = f"Hot: {self._market_featured_item} x{MARKET_FEATURED_MULT:g}"
            cold = f"Cold: {self._market_discounted_item} x{MARKET_DISCOUNT_MULT:g}"
            hints.append(f"Market — {hot}   {cold}")

        if self._weather_event != "None":
            remaining = max(0, int(self._weather_remaining) + 1)
            hints.append(f"Weather: {self._weather_event} ({remaining}s)")
        if self.storm_titan.state == StormTitan.STATE_ACTIVE:
            hints.append(f"Storm Titan HP: {self.storm_titan.hp}/{self.storm_titan.max_hp}")
        elif self.storm_titan.state == StormTitan.STATE_RETREATING:
            hints.append(f"Storm Titan leaves in: {max(0, int(self.storm_titan.seconds_until_leave) + 1)}s")
        else:
            hints.append(f"Next Storm Titan: {self._format_mmss(self.storm_titan.seconds_until_spawn)}")

        if self.cyclone_titan.state == StormTitan.STATE_ACTIVE:
            hints.append(f"Cyclone Titan HP: {self.cyclone_titan.hp}/{self.cyclone_titan.max_hp}")
        elif self.cyclone_titan.state == StormTitan.STATE_RETREATING:
            hints.append(f"Cyclone Titan leaves in: {max(0, int(self.cyclone_titan.seconds_until_leave) + 1)}s")
        else:
            hints.append(f"Next Cyclone Titan: {self._format_mmss(self.cyclone_titan.seconds_until_spawn)}")
        y = 8
        for hint in hints:
            surf = self._font.render(hint, True, (255, 255, 255))
            shadow = self._font.render(hint, True, (0, 0, 0))
            self.screen.blit(shadow, (11, y + 1))
            self.screen.blit(surf,   (10, y))
            y += 22

        # Flash 'Perfect Block!' when a perfect block was recently registered
        now = pygame.time.get_ticks() / 1000.0
        flash_duration = 1.2
        perfect_shown = False
        for boss in (self.storm_titan, self.cyclone_titan):
            t = getattr(boss, "_last_perfect_at", None)
            if t is not None and now - float(t) <= flash_duration:
                msg = "Perfect Block!"
                surf = self._font.render(msg, True, (255, 215, 0))
                shadow = self._font.render(msg, True, (0, 0, 0))
                sx = (self._width - surf.get_width()) // 2
                sy = 40
                self.screen.blit(shadow, (sx + 2, sy + 2))
                self.screen.blit(surf, (sx, sy))
                perfect_shown = True
                break

    @staticmethod
    def _format_mmss(seconds: float) -> str:
        total = max(0, int(seconds))
        minutes, secs = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    # ── bosses ─────────────────────────────────────────────────────────────
    def _visible_boss(self):
        for boss in self._bosses:
            if getattr(boss, "visible", False):
                return boss
        return None

    def _toggle_boss(self, boss):
        if getattr(boss, "visible", False):
            boss.despawn_now()
            return

        # Ensure only one boss is on-screen at a time.
        for other in self._bosses:
            if other is boss:
                continue
            other.despawn_now()
        boss.force_spawn_now()

    def _update_bosses(self, dt: float) -> None:
        visible = self._visible_boss()
        if visible is not None:
            visible.update_battle(dt, slots=self.slots, clouds=self.clouds)
            for boss in self._bosses:
                if boss is visible:
                    continue
                boss.tick_spawn_timer(dt)
        else:
            # No boss on screen; allow a single boss to spawn.
            for boss in self._bosses:
                boss.update_battle(dt, slots=self.slots, clouds=self.clouds)
                if boss.visible:
                    break

        # Deliver any boss rewards.
        for boss in self._bosses:
            reward = boss.pop_reward()
            if reward:
                name, count = reward
                self.inventory[name] = self.inventory.get(name, 0) + count

    def _draw_boss_health_bar(self) -> None:
        boss = self._visible_boss()
        if boss is None:
            return

        max_hp = max(1, int(getattr(boss, "max_hp", 1)))
        hp = max(0, int(getattr(boss, "hp", 0)))
        ratio = max(0.0, min(1.0, hp / max_hp))

        cfg = getattr(boss, "config", None)
        width = int(getattr(cfg, "health_bar_width", 360))
        height = int(getattr(cfg, "health_bar_height", 18))

        field_w = self._field_rect.width
        width = max(180, min(width, field_w - 20))
        height = max(12, min(height, 32))

        bar = pygame.Rect(0, 0, width, height)
        bar.midtop = (field_w // 2, 8)

        pygame.draw.rect(self.screen, (20, 20, 20), bar, border_radius=6)
        inner = bar.inflate(-4, -4)
        fill_w = int(inner.width * ratio)
        if fill_w > 0:
            fill = pygame.Rect(inner.left, inner.top, fill_w, inner.height)
            pygame.draw.rect(self.screen, (215, 60, 60), fill, border_radius=5)
        pygame.draw.rect(self.screen, (255, 255, 255), bar, 2, border_radius=6)

    # ── critters ─────────────────────────────────────────────────────────
    def _update_critters(self, dt: float) -> None:
        for critter in self._critters:
            critter.update(dt, slots=self.slots, field_rect=self._field_rect, ground_rect=self._ground_rect)
            # collect any drop produced by the critter (e.g., Fur, Venom)
            drop = getattr(critter, "_last_drop", None)
            if drop:
                try:
                    name, count = drop
                    self.inventory[name] = self.inventory.get(name, 0) + int(count)
                except Exception:
                    pass
                critter._last_drop = None

    def _draw_critters(self) -> None:
        for critter in self._critters:
            critter.draw(self.screen)

    def _handle_critter_event(self, event: pygame.event.Event) -> bool:
        if self.paused:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if event.pos[0] > self._field_rect.width:
            return False
        for critter in self._critters:
            if critter.active and critter.rect.collidepoint(event.pos):
                critter.scare_away(field_rect=self._field_rect)
                return True
        return False

    def _create_slots(self) -> list[PlantSlot]:
        slots: list[PlantSlot] = []
        total_padding = SLOT_PADDING * (SLOT_COUNT + 1)
        slot_width = (self._field_rect.width - total_padding) // SLOT_COUNT
        slot_height = max(20, self._ground_height - SLOT_PADDING * 2)
        y = self._ground_rect.top + (self._ground_height - slot_height) // 2
        for i in range(SLOT_COUNT):
            x = SLOT_PADDING + i * (slot_width + SLOT_PADDING)
            rect = pygame.Rect(x, y, slot_width, slot_height)
            slots.append(PlantSlot(rect))
        return slots

    def _update_plants(self):
        sun_clear = not any(c.covers_sun(self.sun.circle_rect) for c in self.clouds)
        dt = self.clock.get_time() / 1000.0

        season_idx = self._season_index
        growth_mult = float(SEASON_GROWTH_MULT[season_idx % len(SEASON_GROWTH_MULT)]) if SEASON_GROWTH_MULT else 1.0
        water_loss_mult = float(SEASON_WATER_LOSS_MULT[season_idx % len(SEASON_WATER_LOSS_MULT)]) if SEASON_WATER_LOSS_MULT else 1.0
        sun_gain_mult = float(SEASON_SUN_GAIN_MULT[season_idx % len(SEASON_SUN_GAIN_MULT)]) if SEASON_SUN_GAIN_MULT else 1.0

        event_water_loss_mult = 1.0
        event_sun_gain_mult = 1.0
        event_water_bonus = 0.0
        if self._weather_event == "Heatwave":
            event_water_loss_mult = float(WEATHER_HEATWAVE_WATER_LOSS_MULT)
            event_sun_gain_mult = float(WEATHER_HEATWAVE_SUN_GAIN_MULT)
        elif self._weather_event == "Drizzle":
            event_water_bonus = float(WEATHER_DRIZZLE_WATER_BONUS)
            event_sun_gain_mult = float(WEATHER_DRIZZLE_SUN_GAIN_MULT)

        for slot in self.slots:
            cloud_over_slot = any(c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)
            raining_over_slot = any(c.raining and c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)
            heavy_rain_over_slot = any(getattr(c, "heavy_rain", False) and c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)
            water_delta = -WATER_LOSS * water_loss_mult * event_water_loss_mult
            water_delta += event_water_bonus
            sun_delta = -SUN_LOSS

            if heavy_rain_over_slot:
                water_delta += WATER_GAIN_RAIN_HEAVY
            elif raining_over_slot:
                water_delta += WATER_GAIN_RAIN_LIGHT
            if sun_clear and not cloud_over_slot:
                sun_delta += SUN_GAIN_CLEAR * sun_gain_mult * event_sun_gain_mult

            slot_growth_mult = growth_mult
            if heavy_rain_over_slot:
                slot_growth_mult *= float(HEAVY_RAIN_GROWTH_MULT)
            if getattr(slot, "compost_boost_remaining", 0.0) > 0.0:
                slot_growth_mult *= float(COMPOST_GROWTH_MULT)
            slot.update(
                water_delta,
                sun_delta,
                water_kill=OVERWATER_THRESHOLD,
                sun_kill=OVERSUN_THRESHOLD,
                bad_seconds_to_die=PLANT_BAD_SECONDS_TO_DIE,
                bad_recovery_rate=PLANT_BAD_RECOVERY_RATE,
                growth_rate_good=PLANT_GROWTH_RATE_GOOD * slot_growth_mult,
                growth_rate_bad=PLANT_GROWTH_RATE_BAD * slot_growth_mult,
                dt=dt,
            )

    def _draw_ground(self):
        pygame.draw.rect(self.screen, GROUND_COLOR, self._ground_rect)

    def _draw_shadow(self):
        for c in self.clouds:
            shadow_width = int(c.rect.width * 1.15)
            shadow_height = int(self._ground_height * 0.75)
            shadow_x = c.rect.centerx - shadow_width // 2
            shadow_y = self._ground_rect.top + (self._ground_height - shadow_height) // 2
            shadow_x = max(0, min(shadow_x, self._field_rect.width - shadow_width))

            shadow = pygame.Surface((shadow_width, shadow_height), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (10, 10, 10, 140), shadow.get_rect())
            self.screen.blit(shadow, (shadow_x, shadow_y))

    def _draw_slots(self):
        for slot in self.slots:
            phase_image = self._phase_image_for_slot(slot)
            slot.draw(
                self.screen,
                SLOT_COLOR,
                SLOT_BORDER_COLOR,
                phase_image=phase_image,
                dead_image=self._dead_plant_image,
            )

    def _draw_ui_panel(self):
        panel_rect = pygame.Rect(self._field_rect.width, 0, UI_PANEL_W, SCREEN_H)
        if self._ui_panel_image:
            self.screen.blit(self._ui_panel_image, panel_rect)
        else:
            pygame.draw.rect(self.screen, (40, 45, 55), panel_rect)
            pygame.draw.line(self.screen, (70, 75, 90), (panel_rect.left, 0), (panel_rect.left, SCREEN_H), 2)

        left = panel_rect.left + 16

        title = self._font.render("Seeds", True, (230, 230, 230))
        self.screen.blit(title, (left, 16))

        money_color = (245, 230, 120)
        if self._money_flash_timer > 0:
            money_color = (210, 70, 70)
        money_text = f"{self.money}"
        money = self._font.render(money_text, True, money_color)
        money_x = left
        money_y = 44
        if self._coin_icon:
            icon_rect = self._coin_icon.get_rect(midleft=(money_x, money_y + 12))
            self.screen.blit(self._coin_icon, icon_rect)
            money_x = icon_rect.right + 8
        else:
            label = self._font.render("Money:", True, money_color)
            self.screen.blit(label, (money_x, money_y))
            money_x += label.get_width() + 6
        self.screen.blit(money, (money_x, money_y))

        coin_small = pygame.transform.smoothscale(self._coin_icon, (12, 12)) if self._coin_icon else None

        # ── seeds grid ───────────────────────────────────────────────────
        self._seed_buttons = []
        seed_cols = 4
        button_size = 48
        padding = 8
        grid_w = seed_cols * button_size + (seed_cols - 1) * padding
        grid_x = panel_rect.left + (UI_PANEL_W - grid_w) // 2
        grid_y = 86

        for i, seed in enumerate(self.seeds):
            col = i % seed_cols
            row = i // seed_cols
            rect = pygame.Rect(
                grid_x + col * (button_size + padding),
                grid_y + row * (button_size + padding),
                button_size,
                button_size,
            )

            affordable = self._can_afford_seed(seed)
            bg = (70, 80, 95) if affordable else (55, 60, 70)
            if self.selected_seed == seed:
                bg = (90, 110, 130)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, (95, 105, 120), rect, 2, border_radius=8)

            icon = self._seed_icons.get(seed.icon_filename)
            if icon:
                icon_rect = icon.get_rect(center=(rect.centerx, rect.centery - 6))
                self.screen.blit(icon, icon_rect)
            else:
                fallback = self._small_font.render(seed.name[0], True, (235, 235, 235))
                self.screen.blit(fallback, fallback.get_rect(center=(rect.centerx, rect.centery - 8)))

            req = self._seed_item_requirement(seed)
            if req:
                _, count = req
                req_text = self._small_font.render(f"{count}x", True, (210, 210, 240))
                self.screen.blit(req_text, req_text.get_rect(midbottom=(rect.centerx, rect.bottom - 4)))
            else:
                cost_text = self._small_font.render(str(seed.cost), True, (230, 230, 230))
                cost_y = rect.bottom - 12
                if coin_small:
                    coin_rect = coin_small.get_rect(center=(rect.centerx - 8, cost_y + 2))
                    self.screen.blit(coin_small, coin_rect)
                    cost_rect = cost_text.get_rect(midleft=(coin_rect.right + 4, coin_rect.centery))
                else:
                    cost_prefix = self._small_font.render("$", True, (230, 230, 230))
                    prefix_rect = cost_prefix.get_rect(center=(rect.centerx - 6, cost_y + 2))
                    self.screen.blit(cost_prefix, prefix_rect)
                    cost_rect = cost_text.get_rect(midleft=(prefix_rect.right + 2, prefix_rect.centery))
                self.screen.blit(cost_text, cost_rect)

            self._seed_buttons.append((seed, rect))

        rows = (len(self.seeds) + seed_cols - 1) // seed_cols
        y = grid_y + rows * (button_size + padding) + 12

        # ── tools ─────────────────────────────────────────────────────────
        tools_title = self._font.render("Tools", True, (230, 230, 230))
        self.screen.blit(tools_title, (left, y))
        y += 26

        self._tool_buttons = []
        tool_ids = [TOOL_COMPOST, TOOL_SCARECROW, TOOL_LIGHTNING_ROD]
        tool_names = {
            TOOL_COMPOST: "Compost",
            TOOL_SCARECROW: "Scarecrow",
            TOOL_LIGHTNING_ROD: "Rod",
        }
        tool_costs = {
            TOOL_SCARECROW: int(SCARECROW_COST),
            TOOL_LIGHTNING_ROD: int(LIGHTNING_ROD_COST),
        }
        tool_cols = 3
        tool_grid_w = tool_cols * button_size + (tool_cols - 1) * padding
        tool_grid_x = panel_rect.left + (UI_PANEL_W - tool_grid_w) // 2

        for i, tool_id in enumerate(tool_ids):
            col = i % tool_cols
            row = i // tool_cols
            rect = pygame.Rect(
                tool_grid_x + col * (button_size + padding),
                y + row * (button_size + padding),
                button_size,
                button_size,
            )

            affordable = True
            if tool_id == TOOL_COMPOST:
                affordable = self.inventory.get(COMPOST_ITEM_NAME, 0) >= 1
            elif tool_id in tool_costs:
                affordable = self.money >= int(tool_costs[tool_id])

            bg = (70, 80, 95) if affordable else (55, 60, 70)
            if self.selected_tool == tool_id:
                bg = (90, 110, 130)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, (95, 105, 120), rect, 2, border_radius=8)

            icon = self._tool_icons.get(tool_id)
            label = tool_names.get(tool_id, tool_id)
            if icon:
                icon_rect = icon.get_rect(center=(rect.centerx, rect.centery - 6))
                self.screen.blit(icon, icon_rect)
            else:
                fallback = self._small_font.render(label[0], True, (235, 235, 235))
                self.screen.blit(fallback, fallback.get_rect(center=(rect.centerx, rect.centery - 8)))

            if tool_id == TOOL_COMPOST:
                have = self.inventory.get(COMPOST_ITEM_NAME, 0)
                have_text = self._small_font.render(f"{have}x", True, (210, 210, 240))
                self.screen.blit(have_text, have_text.get_rect(midbottom=(rect.centerx, rect.bottom - 4)))
            else:
                cost = int(tool_costs.get(tool_id, 0))
                cost_text = self._small_font.render(str(cost), True, (230, 230, 230))
                cost_y = rect.bottom - 12
                if coin_small:
                    coin_rect = coin_small.get_rect(center=(rect.centerx - 8, cost_y + 2))
                    self.screen.blit(coin_small, coin_rect)
                    cost_rect = cost_text.get_rect(midleft=(coin_rect.right + 4, coin_rect.centery))
                else:
                    cost_prefix = self._small_font.render("$", True, (230, 230, 230))
                    prefix_rect = cost_prefix.get_rect(center=(rect.centerx - 6, cost_y + 2))
                    self.screen.blit(cost_prefix, prefix_rect)
                    cost_rect = cost_text.get_rect(midleft=(prefix_rect.right + 2, prefix_rect.centery))
                self.screen.blit(cost_text, cost_rect)

            self._tool_buttons.append((tool_id, rect))

        tool_rows = (len(tool_ids) + tool_cols - 1) // tool_cols
        y = y + tool_rows * (button_size + padding) + 10

        # Sell button is fixed at the bottom.
        self._sell_button = pygame.Rect(left, SCREEN_H - 54, UI_PANEL_W - 32, 32)
        inv_bottom = self._sell_button.top - 8

        # ── inventory ─────────────────────────────────────────────────────
        inv_title = self._font.render("Inventory", True, (230, 230, 230))
        self.screen.blit(inv_title, (left, y))
        y += 28

        if not self.inventory:
            empty = self._small_font.render("(empty)", True, (170, 170, 170))
            self.screen.blit(empty, (left, y))
        else:
            lines = sorted(self.inventory.items(), key=lambda kv: kv[0].lower())
            line_h = 22
            max_lines = max(0, int((inv_bottom - y) // line_h))
            shown = 0
            for name, count in lines:
                if shown >= max_lines:
                    break
                line = self._small_font.render(f"{name}: {count}", True, (210, 210, 210))
                self.screen.blit(line, (left, y))
                y += line_h
                shown += 1

            remaining = len(lines) - shown
            if remaining > 0 and shown > 0 and y + line_h <= inv_bottom:
                more = self._small_font.render(f"(+{remaining} more)", True, (170, 170, 170))
                self.screen.blit(more, (left, y))

        pygame.draw.rect(self.screen, (80, 120, 90), self._sell_button, border_radius=6)
        pygame.draw.rect(self.screen, (110, 150, 120), self._sell_button, 2, border_radius=6)
        sell_text = self._small_font.render("Sell All", True, (230, 240, 230))
        sell_rect = sell_text.get_rect(center=self._sell_button.center)
        self.screen.blit(sell_text, sell_rect)

        # Market featured/discounted display (compact)
        m_y = self._sell_button.top - 68
        if self._market_featured_item or self._market_discounted_item:
            m_title = self._small_font.render("Market", True, (220, 220, 160))
            self.screen.blit(m_title, (left, m_y))
            m_y += 18
            if self._market_featured_item:
                hot = f"Hot: {self._market_featured_item} x{MARKET_FEATURED_MULT:g}"
                hot_s = self._small_font.render(hot, True, (230, 200, 120))
                self.screen.blit(hot_s, (left, m_y))
                m_y += 18
            if self._market_discounted_item:
                cold = f"Cold: {self._market_discounted_item} x{MARKET_DISCOUNT_MULT:g}"
                cold_s = self._small_font.render(cold, True, (180, 200, 255))
                self.screen.blit(cold_s, (left, m_y))
                m_y += 18

    def _draw_hover_tooltip(self):
        if not self._hover_slot or not self._hover_slot.planted:
            return
        lines = self._hover_slot.stats_lines()
        if not lines:
            return
        width = 160
        height = 10 + len(lines) * 18
        mouse_x, mouse_y = pygame.mouse.get_pos()
        x = min(mouse_x + 12, self._field_rect.width - width - 8)
        y = min(mouse_y + 12, SCREEN_H - height - 8)
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, (25, 25, 30), rect, border_radius=6)
        pygame.draw.rect(self.screen, (70, 70, 80), rect, 2, border_radius=6)
        text_y = y + 6
        for line in lines:
            surf = self._small_font.render(line, True, (230, 230, 230))
            self.screen.blit(surf, (x + 8, text_y))
            text_y += 18

    def _draw_drag_seed(self):
        if not self.drag_seed:
            return
        mouse_x, mouse_y = pygame.mouse.get_pos()
        rect = pygame.Rect(mouse_x - 26, mouse_y - 26, 52, 52)
        pygame.draw.rect(self.screen, (90, 110, 130), rect, border_radius=8)
        pygame.draw.rect(self.screen, (120, 140, 160), rect, 2, border_radius=8)
        icon = self._seed_icons.get(self.drag_seed.icon_filename)
        if icon:
            icon_rect = icon.get_rect(center=rect.center)
            self.screen.blit(icon, icon_rect)
        else:
            label = self._small_font.render(self.drag_seed.name[0], True, (240, 240, 240))
            self.screen.blit(label, (rect.centerx - 4, rect.centery - 8))

    def _draw_pause_window(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        win_w, win_h = 300, 200
        window = pygame.Rect((SCREEN_W - win_w) // 2, (SCREEN_H - win_h) // 2, win_w, win_h)
        pygame.draw.rect(self.screen, (130, 150, 190), window, border_radius=12)

        win_font = pygame.font.SysFont("arial", 30)
        btn_font = pygame.font.SysFont("arial", 24)
        paused_text = win_font.render("Paused", True, (255, 255, 255))
        resume_text = btn_font.render("Resume", True, (255, 255, 255))
        quit_text = btn_font.render("Quit", True, (255, 255, 255))

        pygame.draw.rect(self.screen, (70, 110, 150), self._pause_resume_btn, border_radius=6)
        pygame.draw.rect(self.screen, (70, 110, 150), self._pause_quit_btn, border_radius=6)

        self.screen.blit(paused_text, paused_text.get_rect(center=(window.centerx, window.centery - 55)))
        self.screen.blit(resume_text, resume_text.get_rect(center=self._pause_resume_btn.center))
        self.screen.blit(quit_text, quit_text.get_rect(center=self._pause_quit_btn.center))

        return

    def _handle_farm_event(self, event: pygame.event.Event):
        # If a sell confirmation overlay is active, limit interactions to it.
        if self._show_sell_confirm:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                # Confirm
                confirm = self._sell_confirm_buttons.get("confirm")
                cancel = self._sell_confirm_buttons.get("cancel")
                if confirm and confirm.collidepoint(pos):
                    self._do_sell_inventory()
                    self._show_sell_confirm = False
                    self._pending_sell_total = None
                    return
                if cancel and cancel.collidepoint(pos):
                    self._show_sell_confirm = False
                    self._pending_sell_total = None
                    return
            return

        if event.type == pygame.MOUSEMOTION:
            self._hover_slot = self._slot_at_pos(event.pos)
            return

        if self.paused:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            seed = self._seed_at_pos(event.pos)
            if seed:
                if self._can_afford_seed(seed):
                    self.selected_seed = seed
                    self.selected_tool = None
                    self.drag_seed = seed
                else:
                    self._money_flash_timer = 20
                return

            tool_id = self._tool_at_pos(event.pos)
            if tool_id:
                if self.selected_tool == tool_id:
                    self.selected_tool = None
                else:
                    self.selected_tool = tool_id
                    self.selected_seed = None
                    self.drag_seed = None
                return

            if self._sell_button.collidepoint(event.pos):
                self._sell_inventory()
                return

            slot = self._slot_at_pos(event.pos)
            if slot and slot.dead:
                slot.clear()
                if COMPOST_FROM_DEAD_PLANT > 0:
                    self.inventory[COMPOST_ITEM_NAME] = self.inventory.get(COMPOST_ITEM_NAME, 0) + int(COMPOST_FROM_DEAD_PLANT)
                return
            if slot and slot.harvestable:
                self._harvest(slot)
                return

            if slot and self.selected_tool:
                self._apply_tool_to_slot(slot, self.selected_tool)
                return

            if slot and (not slot.planted) and (not slot.has_scarecrow) and self.selected_seed and self._can_afford_seed(self.selected_seed):
                self._plant_slot(slot, self.selected_seed)
                return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            slot = self._slot_at_pos(event.pos)
            if self.drag_seed and slot and (not slot.planted) and (not slot.has_scarecrow):
                self._plant_slot(slot, self.drag_seed)
            self.drag_seed = None
            return

    def _seed_at_pos(self, pos: tuple[int, int]) -> PlantType | None:
        for seed, rect in self._seed_buttons:
            if rect.collidepoint(pos):
                return seed
        return None

    def _tool_at_pos(self, pos: tuple[int, int]) -> str | None:
        for tool_id, rect in self._tool_buttons:
            if rect.collidepoint(pos):
                return tool_id
        return None

    def _load_seed_icons(self):
        for seed in self.seeds:
            path = os.path.join(PROPS_DIR, seed.icon_filename)
            if not os.path.exists(path):
                continue
            raw = pygame.image.load(path).convert_alpha()
            self._seed_icons[seed.icon_filename] = pygame.transform.smoothscale(raw, (32, 32))

    def _load_tool_icons(self):
        for tool_id, filename in TOOL_ICON_FILENAMES.items():
            path = os.path.join(PROPS_DIR, filename)
            if not os.path.exists(path):
                continue
            raw = pygame.image.load(path).convert_alpha()
            self._tool_icons[tool_id] = pygame.transform.smoothscale(raw, (32, 32))

    def _load_ui_panel(self):
        path = os.path.join(PROPS_DIR, "ui_panel.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._ui_panel_image = pygame.transform.smoothscale(raw, (UI_PANEL_W, SCREEN_H))

    def _load_coin_icon(self):
        path = os.path.join(PROPS_DIR, "coin.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._coin_icon = pygame.transform.smoothscale(raw, (20, 20))

    def _load_dead_plant(self):
        path = os.path.join(PROPS_DIR, "dead_plant.png")
        if not os.path.exists(path):
            return
        raw = pygame.image.load(path).convert_alpha()
        self._dead_plant_image = pygame.transform.smoothscale(raw, (PLANT_SPRITE_W, PLANT_SPRITE_H))

    def _load_plant_phases(self):
        for seed in self.seeds:
            w = seed.sprite_w if seed.sprite_w is not None else PLANT_SPRITE_W
            h = seed.sprite_h if seed.sprite_h is not None else PLANT_SPRITE_H
            for filename in seed.phase_filenames:
                if filename in self._plant_phase_icons:
                    continue
                path = os.path.join(PROPS_DIR, filename)
                if not os.path.exists(path):
                    continue
                raw = pygame.image.load(path).convert_alpha()
                self._plant_phase_icons[filename] = pygame.transform.smoothscale(raw, (w, h))

    def _phase_image_for_slot(self, slot: PlantSlot) -> pygame.Surface | None:
        if not slot.seed:
            return None
        stage = min(slot.growth_stage, slot.seed.growth_stages)
        index = min(stage, len(slot.seed.phase_filenames)) - 1
        if index < 0:
            return None
        filename = slot.seed.phase_filenames[index]
        return self._plant_phase_icons.get(filename)

    def _slot_at_pos(self, pos: tuple[int, int]) -> PlantSlot | None:
        if pos[0] > self._field_rect.width:
            return None
        for slot in self.slots:
            if slot.rect.collidepoint(pos):
                return slot
        return None

    def _seed_item_requirement(self, seed: PlantType) -> tuple[str, int] | None:
        item_name = getattr(seed, "seed_item_name", None)
        if not item_name:
            return None
        return (str(item_name), 1)

    def _draw_sell_confirm(self):
        # Semi-opaque overlay
        w, h = 420, 140
        rect = pygame.Rect((SCREEN_W - w) // 2, (SCREEN_H - h) // 2, w, h)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (20, 20, 30, 220), overlay.get_rect(), border_radius=8)
        title = self._font.render("Confirm Sell All", True, (240, 240, 240))
        overlay.blit(title, (16, 12))
        total_text = f"Total: ${int(self._pending_sell_total or 0)}"
        total_s = self._font.render(total_text, True, (220, 220, 180))
        overlay.blit(total_s, (16, 48))

        # Buttons
        btn_w, btn_h = 140, 36
        spacing = 18
        bx = w - btn_w - 16
        by = h - btn_h - 16
        confirm = pygame.Rect(bx, by, btn_w, btn_h)
        cancel = pygame.Rect(bx - (btn_w + spacing), by, btn_w, btn_h)
        pygame.draw.rect(overlay, (60, 140, 70), confirm, border_radius=8)
        pygame.draw.rect(overlay, (140, 80, 60), cancel, border_radius=8)
        c_text = self._small_font.render("Confirm", True, (240, 240, 240))
        x_text = self._small_font.render("Cancel", True, (240, 240, 240))
        overlay.blit(c_text, c_text.get_rect(center=confirm.center))
        overlay.blit(x_text, x_text.get_rect(center=cancel.center))

        # store button rects in screen coords
        screen_confirm = confirm.move(rect.left, rect.top)
        screen_cancel = cancel.move(rect.left, rect.top)
        self._sell_confirm_buttons["confirm"] = screen_confirm
        self._sell_confirm_buttons["cancel"] = screen_cancel

        self.screen.blit(overlay, rect.topleft)

    def _can_afford_seed(self, seed: PlantType) -> bool:
        if self.money < seed.cost:
            return False
        req = self._seed_item_requirement(seed)
        if not req:
            return True
        item_name, count = req
        return self.inventory.get(item_name, 0) >= count

    def _pay_for_seed(self, seed: PlantType) -> bool:
        if not self._can_afford_seed(seed):
            return False

        self.money -= seed.cost
        req = self._seed_item_requirement(seed)
        if req:
            item_name, count = req
            remaining = self.inventory.get(item_name, 0) - count
            if remaining > 0:
                self.inventory[item_name] = remaining
            else:
                self.inventory.pop(item_name, None)
        return True

    def _plant_slot(self, slot: PlantSlot, seed: PlantType):
        if getattr(slot, "has_scarecrow", False):
            return
        if not self._pay_for_seed(seed):
            return
        slot.plant(seed)

    def _apply_tool_to_slot(self, slot: PlantSlot, tool_id: str) -> None:
        if tool_id == TOOL_COMPOST:
            if (not slot.planted) or slot.dead or slot.harvestable:
                return
            have = self.inventory.get(COMPOST_ITEM_NAME, 0)
            if have < 1:
                return
            if have == 1:
                self.inventory.pop(COMPOST_ITEM_NAME, None)
            else:
                self.inventory[COMPOST_ITEM_NAME] = have - 1
            slot.apply_compost(COMPOST_BOOST_SECONDS)
            return

        if tool_id == TOOL_SCARECROW:
            if slot.planted or slot.dead:
                return
            if slot.has_scarecrow:
                slot.remove_scarecrow()
                return
            if self.money < int(SCARECROW_COST):
                self._money_flash_timer = 20
                return
            self.money -= int(SCARECROW_COST)
            slot.place_scarecrow()
            return

        if tool_id == TOOL_LIGHTNING_ROD:
            if (not slot.planted) or slot.dead:
                return
            if self.money < int(LIGHTNING_ROD_COST):
                self._money_flash_timer = 20
                return
            self.money -= int(LIGHTNING_ROD_COST)
            slot.add_lightning_rod_charges(LIGHTNING_ROD_CHARGES)
            return

    def _harvest(self, slot: PlantSlot):
        if not slot.seed:
            return
        name = slot.seed.product_name
        self.inventory[name] = self.inventory.get(name, 0) + slot.seed.harvest_yield
        # SFX removed: no-op here (placeholder for future audio)
        if slot.seed.regrow_to_stage is None:
            slot.clear()
        else:
            slot.seed.seconds_per_stage = 12.0
            slot.regrow(slot.seed.regrow_to_stage)

    def _sell_inventory(self):
        # Compute the sell total and show confirmation overlay.
        total = 0
        for name, count in self.inventory.items():
            item = self.items.get(name)
            if item:
                mult = self._market_mult_for_item(name)
                total += int(round(item.sell_price * mult)) * count
        if total == 0:
            return
        self._pending_sell_total = int(total)
        self._show_sell_confirm = True

    def _do_sell_inventory(self):
        if not self._pending_sell_total:
            return
        self.money += int(self._pending_sell_total)
        self.inventory = {}
        self._pending_sell_total = None
