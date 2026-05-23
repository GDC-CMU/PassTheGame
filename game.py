import os
import pygame
from settings import (
    TITLE, SCREEN_W, SCREEN_H, FPS,
    SKY_DAY, SKY_DARK,
    UI_PANEL_W, GROUND_HEIGHT_PCT, SLOT_COUNT,
    SLOT_PADDING, SLOT_COLOR, SLOT_BORDER_COLOR,
    GROUND_COLOR,
    WATER_GAIN_RAIN, WATER_LOSS, SUN_GAIN_CLEAR,
    SUN_LOSS, OVERWATER_THRESHOLD, OVERSUN_THRESHOLD,
    PLANT_BAD_SECONDS_TO_DIE, PLANT_BAD_RECOVERY_RATE,
    PLANT_GROWTH_RATE_GOOD, PLANT_GROWTH_RATE_BAD,
    PLANT_SPRITE_W, PLANT_SPRITE_H,
)
from cloud import Cloud
from sun import Sun
from farming import PlantSlot
from plants import PlantType, Carrot, Lettuce, Tomato
from items import ITEMS

PROPS_DIR = os.path.join(os.path.dirname(__file__), "props")


class Game:
    """
    Core game loop.  All state lives here; sprites are kept in groups so that
    future contributors can easily add more sprites or layers.
    """

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption(TITLE)
        self.clock  = pygame.time.Clock()

        # ── sprites ───────────────────────────────────────────────────────────
        self.sun   = Sun()
        self.cloud = Cloud()

        self.all_sprites = pygame.sprite.Group(self.sun, self.cloud)

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

        # Add new plants by instantiating PlantType subclasses here.
        self.seeds: list[PlantType] = [Carrot(), Lettuce(), Tomato()]
        self.money = 20
        self.inventory: dict[str, int] = {}
        self.items = ITEMS
        self.drag_seed: PlantType | None = None
        self.selected_seed: PlantType | None = None
        self._seed_buttons: list[tuple[PlantType, pygame.Rect]] = []
        self._seed_icons: dict[str, pygame.Surface] = {}
        self._plant_phase_icons: dict[str, pygame.Surface] = {}
        self._hover_slot: PlantSlot | None = None
        self._sell_button = pygame.Rect(0, 0, 0, 0)
        self._money_flash_timer = 0
        self._ui_panel_image: pygame.Surface | None = None
        self._coin_icon: pygame.Surface | None = None
        self._dead_plant_image: pygame.Surface | None = None

        self.slots = self._create_slots()
        self._load_seed_icons()
        self._load_ui_panel()
        self._load_coin_icon()
        self._load_plant_phases()
        self._load_dead_plant()

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
                self.cloud.handle_event(event)
                self._handle_farm_event(event)

            self._update()
            self._draw()

    # ── update ────────────────────────────────────────────────────────────────
    def _update(self):
        self.all_sprites.update()

        if self._money_flash_timer > 0:
            self._money_flash_timer -= 1

        # lerp sky colour toward target
        target = SKY_DARK if self.cloud.covers_sun(self.sun.circle_rect) else SKY_DAY
        for i in range(3):
            diff = target[i] - self._sky_color[i]
            self._sky_color[i] += diff * 0.04   # smooth transition speed

        self._update_plants()

    # ── draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(tuple(int(c) for c in self._sky_color))

        self.screen.blit(self.sun.image, self.sun.rect)
        self.cloud.draw_rain(self.screen)
        self.screen.blit(self.cloud.image, self.cloud.rect)

        self._draw_ground()
        self._draw_slots()
        self._draw_shadow()
        self._draw_ui_panel()
        self._draw_hover_tooltip()
        self._draw_drag_seed()
        self._draw_hud()
        pygame.display.flip()

    def _draw_hud(self):
        hints = [
            "Arrow keys: move cloud",
            "Click cloud: toggle rain",
            "Drag or click seed to plant",
            "Click harvestable plant",
            "ESC: quit",
        ]
        y = 8
        for hint in hints:
            surf = self._font.render(hint, True, (255, 255, 255))
            shadow = self._font.render(hint, True, (0, 0, 0))
            self.screen.blit(shadow, (11, y + 1))
            self.screen.blit(surf,   (10, y))
            y += 22

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
        raining = self.cloud.raining
        sun_clear = not self.cloud.covers_sun(self.sun.circle_rect)
        dt = self.clock.get_time() / 1000.0
        for slot in self.slots:
            cloud_over_slot = self.cloud.rect.left <= slot.rect.centerx <= self.cloud.rect.right
            water_delta = -WATER_LOSS
            sun_delta = -SUN_LOSS
            if raining and cloud_over_slot:
                water_delta += WATER_GAIN_RAIN
            if sun_clear and not cloud_over_slot:
                sun_delta += SUN_GAIN_CLEAR
            slot.update(
                water_delta,
                sun_delta,
                water_kill=OVERWATER_THRESHOLD,
                sun_kill=OVERSUN_THRESHOLD,
                bad_seconds_to_die=PLANT_BAD_SECONDS_TO_DIE,
                bad_recovery_rate=PLANT_BAD_RECOVERY_RATE,
                growth_rate_good=PLANT_GROWTH_RATE_GOOD,
                growth_rate_bad=PLANT_GROWTH_RATE_BAD,
                dt=dt,
            )

    def _draw_ground(self):
        pygame.draw.rect(self.screen, GROUND_COLOR, self._ground_rect)

    def _draw_shadow(self):
        shadow_width = int(self.cloud.rect.width * 1.15)
        shadow_height = int(self._ground_height * 0.75)
        shadow_x = self.cloud.rect.centerx - shadow_width // 2
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

        title = self._font.render("Seeds", True, (230, 230, 230))
        self.screen.blit(title, (panel_rect.left + 16, 16))

        money_color = (245, 230, 120)
        if self._money_flash_timer > 0:
            money_color = (210, 70, 70)
        money_text = f"{self.money}"
        money = self._font.render(money_text, True, money_color)
        money_x = panel_rect.left + 16
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

        self._seed_buttons = []
        y = 86
        button_size = 64
        padding = 10
        x = panel_rect.left + 16
        for seed in self.seeds:
            rect = pygame.Rect(x, y, button_size, button_size)
            affordable = self.money >= seed.cost
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
                self.screen.blit(fallback, (rect.centerx - 4, rect.centery - 10))

            cost_text = self._small_font.render(str(seed.cost), True, (230, 230, 230))
            cost_y = rect.bottom - 12
            if self._coin_icon:
                coin = pygame.transform.smoothscale(self._coin_icon, (12, 12))
                coin_rect = coin.get_rect(center=(rect.centerx - 8, cost_y + 2))
                self.screen.blit(coin, coin_rect)
                cost_rect = cost_text.get_rect(midleft=(coin_rect.right + 4, coin_rect.centery))
            else:
                cost_prefix = self._small_font.render("$", True, (230, 230, 230))
                prefix_rect = cost_prefix.get_rect(center=(rect.centerx - 6, cost_y + 2))
                self.screen.blit(cost_prefix, prefix_rect)
                cost_rect = cost_text.get_rect(midleft=(prefix_rect.right + 2, prefix_rect.centery))
            self.screen.blit(cost_text, cost_rect)

            self._seed_buttons.append((seed, rect))
            y += button_size + padding

        inv_title = self._font.render("Inventory", True, (230, 230, 230))
        self.screen.blit(inv_title, (panel_rect.left + 16, y + 12))
        y += 40
        if not self.inventory:
            empty = self._small_font.render("(empty)", True, (170, 170, 170))
            self.screen.blit(empty, (panel_rect.left + 16, y))
            y += 22
        else:
            for name, count in self.inventory.items():
                line = self._small_font.render(f"{name}: {count}", True, (210, 210, 210))
                self.screen.blit(line, (panel_rect.left + 16, y))
                y += 22

        self._sell_button = pygame.Rect(panel_rect.left + 16, SCREEN_H - 54, UI_PANEL_W - 32, 32)
        pygame.draw.rect(self.screen, (80, 120, 90), self._sell_button, border_radius=6)
        pygame.draw.rect(self.screen, (110, 150, 120), self._sell_button, 2, border_radius=6)
        sell_text = self._small_font.render("Sell All", True, (230, 240, 230))
        sell_rect = sell_text.get_rect(center=self._sell_button.center)
        self.screen.blit(sell_text, sell_rect)

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

    def _handle_farm_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEMOTION:
            self._hover_slot = self._slot_at_pos(event.pos)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            seed = self._seed_at_pos(event.pos)
            if seed:
                if self.money >= seed.cost:
                    self.selected_seed = seed
                    self.drag_seed = seed
                else:
                    self._money_flash_timer = 20
                return

            if self._sell_button.collidepoint(event.pos):
                self._sell_inventory()
                return

            slot = self._slot_at_pos(event.pos)
            if slot and slot.dead:
                slot.clear()
                return
            if slot and slot.harvestable:
                self._harvest(slot)
                return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            slot = self._slot_at_pos(event.pos)
            if self.drag_seed and slot and not slot.planted:
                self._plant_slot(slot, self.drag_seed)
            self.drag_seed = None
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            slot = self._slot_at_pos(event.pos)
            if slot and not slot.planted and self.selected_seed and self.money >= self.selected_seed.cost:
                self._plant_slot(slot, self.selected_seed)

    def _seed_at_pos(self, pos: tuple[int, int]) -> PlantType | None:
        for seed, rect in self._seed_buttons:
            if rect.collidepoint(pos):
                return seed
        return None

    def _load_seed_icons(self):
        for seed in self.seeds:
            path = os.path.join(PROPS_DIR, seed.icon_filename)
            if not os.path.exists(path):
                continue
            raw = pygame.image.load(path).convert_alpha()
            self._seed_icons[seed.icon_filename] = pygame.transform.smoothscale(raw, (32, 32))

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
            for filename in seed.phase_filenames:
                if filename in self._plant_phase_icons:
                    continue
                path = os.path.join(PROPS_DIR, filename)
                if not os.path.exists(path):
                    continue
                raw = pygame.image.load(path).convert_alpha()
                self._plant_phase_icons[filename] = pygame.transform.smoothscale(raw, (PLANT_SPRITE_W, PLANT_SPRITE_H))

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

    def _plant_slot(self, slot: PlantSlot, seed: PlantType):
        if self.money < seed.cost:
            return
        slot.plant(seed)
        self.money -= seed.cost

    def _harvest(self, slot: PlantSlot):
        if not slot.seed:
            return
        name = slot.seed.product_name
        self.inventory[name] = self.inventory.get(name, 0) + 1
        slot.clear()

    def _sell_inventory(self):
        total = 0
        for name, count in self.inventory.items():
            item = self.items.get(name)
            if item:
                total += item.sell_price * count
        if total == 0:
            return
        self.money += total
        self.inventory = {}
