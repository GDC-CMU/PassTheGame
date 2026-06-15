import pygame

from game import Game
from settings import (
    SCREEN_W, SCREEN_H, UI_PANEL_W, FPS,
    STAR_MIN_ALIVE_SECONDS,
)

# Tutorial steps. Keep this as a small Game subclass so main.py can keep calling
# Tutorial(screen).run() exactly as before.
TUT_STEP_RIGHT_CLOUD = 0
TUT_STEP_LEFT_CLOUD = 1
TUT_STEP_RAIN = 2
TUT_STEP_SELECT_SEED = 3
TUT_STEP_PLANT = 4
TUT_STEP_CARE = 5
TUT_STEP_HARVEST = 6
TUT_STEP_WILT = 7
TUT_STEP_TITAN_BLOCK = 8
TUT_STEP_INVENTORY = 9
TUT_STEP_MARKET = 10
TUT_STEP_ALMANAC = 11
TUT_STEP_DONE = 12
TUT_STEP_EXIT = 13

TUT_BRIEFING_OVERLAY_ALPHA = 225
TUT_STEP_OVERLAY_ALPHA = 165


class Tutorial(Game):
    def __init__(self, screen):
        # Start from a clean fixed scenario (new_game=True) so the tutorial never
        # loads the player's real save, and its save_game/load_game are no-ops
        # below so it can never overwrite the real savegame.json either.
        super().__init__(new_game=True)
        self.screen = screen
        self.font_tut = pygame.font.SysFont("arial", 25, bold=True)
        self.font_warn = pygame.font.SysFont("arial", 21, bold=True)
        self.font_hint = pygame.font.SysFont("arial", 14)

        self.tut_step = TUT_STEP_RIGHT_CLOUD
        self._tut_briefing = True
        self._understand_btn_rect = pygame.Rect(0, 0, 0, 0)
        self._care_seconds = 0.0
        self._block_seconds = 0.0
        self._opened_inventory = False
        self._opened_market = False
        self._opened_almanac = False

        # The tutorial owns pacing. Disable random threats and weather so prompts
        # teach one idea at a time.
        self._bosses = []
        self._critters = []
        self._weather_event = "None"
        self._crows.set_difficulty_scale(0.0)
        if hasattr(self, "_minibosses"):
            self._minibosses._cooldown = 999999.0

        self.right_cloud = self._cloud_with_label("Arrows")
        self.left_cloud = self._cloud_with_label("WASD")
        self._right_start = self.right_cloud.rect.center if self.right_cloud else (0, 0)
        self._left_start = self.left_cloud.rect.center if self.left_cloud else (0, 0)

        self.target_slot = self.slots[3]
        self.wilt_slot = self.slots[4]
        self.titan_slot = self.slots[6]
        for slot in self.slots:
            slot.clear()

    def _cloud_with_label(self, label: str):
        for cloud in self.clouds:
            if getattr(cloud, "control_label", "") == label:
                return cloud
        return next(iter(self.clouds), None)

    # The tutorial must never read or write the real savegame.json. Saving is a
    # no-op (tutorial progress is not persisted), and loading is disabled so the
    # fixed teaching scenario is never replaced by the player's real save.
    def save_game(self, flash: bool = True):
        return

    def load_game(self):
        return

    def _advance_to(self, step: int) -> None:
        self.tut_step = step
        self._tut_briefing = True
        self._on_enter_step(step)

    def _on_enter_step(self, step: int) -> None:
        if step == TUT_STEP_CARE:
            self._care_seconds = 0.0
            if self.target_slot.planted and self.target_slot.seed:
                seed = self.target_slot.seed
                self.target_slot.water = (seed.water_min + seed.water_max) / 2.0
                self.target_slot.sun = (seed.sun_min + seed.sun_max) / 2.0
        elif step == TUT_STEP_WILT:
            self._show_inventory_overlay = False
            self._show_market_overlay = False
            self._show_almanac = False
            if not self.wilt_slot.planted:
                self.wilt_slot.plant(self.seeds[0])
            seed = self.wilt_slot.seed
            if seed:
                self.wilt_slot.water = max(0.0, seed.water_min - 25.0)
                self.wilt_slot.sun = (seed.sun_min + seed.sun_max) / 2.0
            self.wilt_slot._bad_frames = max(self.wilt_slot._bad_frames, 4.0)
        elif step == TUT_STEP_TITAN_BLOCK:
            self._block_seconds = 0.0
            self.titan_slot.clear()
            self.titan_slot.plant(self.seeds[0])
        elif step == TUT_STEP_DONE:
            self._show_inventory_overlay = False
            self._show_market_overlay = False
            self._show_almanac = False

    def _dismiss_briefing(self) -> None:
        if self.tut_step == TUT_STEP_DONE:
            self.tut_step = TUT_STEP_EXIT
        else:
            self._tut_briefing = False

    def _prompts_for_step(self) -> list[str]:
        if self.tut_step == TUT_STEP_RIGHT_CLOUD:
            return ["Right cloud: hold Arrow keys.", "Move it a little."]
        if self.tut_step == TUT_STEP_LEFT_CLOUD:
            return ["Left cloud: hold WASD.", "Move it a little too."]
        if self.tut_step == TUT_STEP_RAIN:
            return ["Click either cloud.", "Rain cycles Off, Light, Heavy."]
        if self.tut_step == TUT_STEP_SELECT_SEED:
            return ["Pick a seed from the panel.", "Carrot is the forgiving starter."]
        if self.tut_step == TUT_STEP_PLANT:
            return ["Click or drag the seed onto soil.", "Plant in the highlighted slot."]
        if self.tut_step == TUT_STEP_CARE:
            return ["Core rule: keep Sun and Water in green.", "Use clouds for shade. Click clouds for rain."]
        if self.tut_step == TUT_STEP_HARVEST:
            return ["Ready crop: click it to harvest.", "Mostly-green care makes Golden crops, worth 2x."]
        if self.tut_step == TUT_STEP_WILT:
            return ["Wilting is the death warning.", "Rain this crop back into its green Water band."]
        if self.tut_step == TUT_STEP_TITAN_BLOCK:
            return ["Storm Titan mark: cover the target slot.", "Move either cloud over the red ring."]
        if self.tut_step == TUT_STEP_INVENTORY:
            return ["Press E for Inventory.", "Harvests, tools, and Golden crops live there."]
        if self.tut_step == TUT_STEP_MARKET:
            return ["Press M for Market.", "Tools unlock there as each threat appears."]
        if self.tut_step == TUT_STEP_ALMANAC:
            return ["Press J for the Almanac.", "It tracks seasons, goals, years, and difficulty."]
        if self.tut_step == TUT_STEP_DONE:
            return ["Tutorial complete.", "Now keep ten crops alive with two clouds."]
        return []

    def run(self):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._stop_ambient_sounds()
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._stop_ambient_sounds()
                    return "menu"
                if self._main_menu_button_clicked(event):
                    self._stop_ambient_sounds()
                    return "menu"

                if self._intercept_event(event):
                    continue

                if not self.paused and not self._tut_briefing:
                    for cloud in self.clouds:
                        if cloud.handle_event(event):
                            break
                if not self._tut_briefing:
                    self._handle_farm_event(event)

            self._update()
            if not self._tut_briefing:
                self._check_progress()
            self._draw()

            if self.tut_step == TUT_STEP_EXIT:
                self._stop_ambient_sounds()
                return "menu"

    def _intercept_event(self, event):
        if self._tut_briefing:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._dismiss_briefing()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._understand_btn_rect.collidepoint(event.pos):
                    self._dismiss_briefing()
            return True

        if event.type == pygame.KEYDOWN:
            if self.tut_step == TUT_STEP_INVENTORY and event.key == pygame.K_e:
                self._toggle_inventory_overlay()
                self._opened_inventory = True
                return True
            if self.tut_step == TUT_STEP_MARKET and event.key == pygame.K_m:
                self._toggle_market_overlay()
                self._opened_market = True
                return True
            if self.tut_step == TUT_STEP_ALMANAC and event.key == pygame.K_j:
                self._toggle_almanac()
                self._opened_almanac = True
                return True
            if self.tut_step in (TUT_STEP_RIGHT_CLOUD, TUT_STEP_LEFT_CLOUD):
                return False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.tut_step == TUT_STEP_RAIN:
                return not any(c.rect.collidepoint(event.pos) for c in self.clouds)
            if self.tut_step == TUT_STEP_SELECT_SEED:
                seed_rect = self._seed_buttons[0][1] if self._seed_buttons else pygame.Rect(0, 0, 0, 0)
                return not seed_rect.collidepoint(event.pos)
            if self.tut_step == TUT_STEP_PLANT:
                return not self.target_slot.rect.collidepoint(event.pos)
            if self.tut_step == TUT_STEP_CARE:
                return not any(c.rect.collidepoint(event.pos) for c in self.clouds)
            if self.tut_step == TUT_STEP_HARVEST:
                return not self.target_slot.rect.collidepoint(event.pos)
            if self.tut_step == TUT_STEP_WILT:
                return not any(c.rect.collidepoint(event.pos) for c in self.clouds)
            if self.tut_step == TUT_STEP_TITAN_BLOCK:
                return True
            if self.tut_step in (TUT_STEP_INVENTORY, TUT_STEP_MARKET, TUT_STEP_ALMANAC):
                return False
        return False

    def _update(self):
        # Keep the random mini-boss director asleep in the tutorial.
        if hasattr(self, "_minibosses"):
            self._minibosses._cooldown = 999999.0
            self._minibosses._active = []
        super()._update()

    def _moved_from(self, cloud, start, pixels=24) -> bool:
        if cloud is None:
            return False
        dx = cloud.rect.centerx - start[0]
        dy = cloud.rect.centery - start[1]
        return (dx * dx + dy * dy) ** 0.5 >= pixels

    def _cloud_covers_slot(self, slot) -> bool:
        return any(c.rect.left <= slot.rect.centerx <= c.rect.right for c in self.clouds)

    def _check_progress(self):
        dt = min(self.clock.get_time() / 1000.0, 0.1)
        if self.tut_step == TUT_STEP_RIGHT_CLOUD and self._moved_from(self.right_cloud, self._right_start):
            self._advance_to(TUT_STEP_LEFT_CLOUD)
        elif self.tut_step == TUT_STEP_LEFT_CLOUD and self._moved_from(self.left_cloud, self._left_start):
            self._advance_to(TUT_STEP_RAIN)
        elif self.tut_step == TUT_STEP_RAIN and any(getattr(c, "raining", False) for c in self.clouds):
            self._advance_to(TUT_STEP_SELECT_SEED)
        elif self.tut_step == TUT_STEP_SELECT_SEED and self.selected_seed is not None:
            self._advance_to(TUT_STEP_PLANT)
        elif self.tut_step == TUT_STEP_PLANT and self.target_slot.planted:
            self._advance_to(TUT_STEP_CARE)
        elif self.tut_step == TUT_STEP_CARE:
            if self.target_slot.in_range:
                self._care_seconds += dt
            else:
                self._care_seconds = max(0.0, self._care_seconds - dt)
            if self._care_seconds >= 3.0 and self.target_slot.seed:
                self.target_slot._alive_seconds = max(float(STAR_MIN_ALIVE_SECONDS), self.target_slot._alive_seconds)
                self.target_slot._in_range_seconds = self.target_slot._alive_seconds
                self.target_slot.growth_stage = self.target_slot.seed.growth_stages
                self.target_slot._growth_frames = 0.0
                self._advance_to(TUT_STEP_HARVEST)
        elif self.tut_step == TUT_STEP_HARVEST and not self.target_slot.planted:
            self._advance_to(TUT_STEP_WILT)
        elif self.tut_step == TUT_STEP_WILT:
            if self.wilt_slot.dead:
                self._on_enter_step(TUT_STEP_WILT)
            elif self.wilt_slot.seed and self.wilt_slot.water >= self.wilt_slot.seed.water_min:
                self.wilt_slot._bad_frames = 0.0
                self._advance_to(TUT_STEP_TITAN_BLOCK)
        elif self.tut_step == TUT_STEP_TITAN_BLOCK:
            if self._cloud_covers_slot(self.titan_slot):
                self._block_seconds += dt
            else:
                self._block_seconds = 0.0
            if self._block_seconds >= 0.6:
                self._advance_to(TUT_STEP_INVENTORY)
        elif self.tut_step == TUT_STEP_INVENTORY and self._opened_inventory:
            self._advance_to(TUT_STEP_MARKET)
        elif self.tut_step == TUT_STEP_MARKET and self._opened_market:
            self._advance_to(TUT_STEP_ALMANAC)
        elif self.tut_step == TUT_STEP_ALMANAC and self._opened_almanac:
            self._advance_to(TUT_STEP_DONE)

    def _draw(self):
        orig_flip = pygame.display.flip
        pygame.display.flip = lambda: None
        super()._draw()
        pygame.display.flip = orig_flip

        if self._tut_briefing:
            self._draw_briefing_overlay()
        else:
            self._draw_tutorial_overlay()
            self._draw_main_menu_button()
            self._draw_exit_hint()
        pygame.display.flip()

    def _draw_exit_hint(self) -> None:
        btn = self._main_menu_btn
        for i, line in enumerate(("ESC or Main Menu: leave tutorial", "P: pause")):
            y = btn.bottom + 6 + i * (self.font_hint.get_height() + 1)
            shadow = self.font_hint.render(line, True, (0, 0, 0))
            surf = self.font_hint.render(line, True, (220, 225, 235))
            rect = surf.get_rect(midtop=(btn.centerx, y))
            self.screen.blit(shadow, (rect.x + 1, rect.y + 1))
            self.screen.blit(surf, rect)

    def _draw_understand_button(self, centerx: int, top: int) -> None:
        self._understand_btn_rect = pygame.Rect(centerx - 95, top, 190, 42)
        hovered = self._understand_btn_rect.collidepoint(pygame.mouse.get_pos())
        bg = (70, 130, 85) if hovered else (55, 105, 70)
        pygame.draw.rect(self.screen, bg, self._understand_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (150, 210, 165), self._understand_btn_rect, 2, border_radius=8)
        label = self.font_warn.render("Got it", True, (255, 255, 255))
        self.screen.blit(label, label.get_rect(center=self._understand_btn_rect.center))

    def _draw_prompt_lines(self, prompts: list[str], start_y: int) -> int:
        y = start_y
        cx = (SCREEN_W - UI_PANEL_W) // 2
        for line in prompts:
            shadow = self.font_tut.render(line, True, (0, 0, 0))
            surf = self.font_tut.render(line, True, (255, 255, 255))
            rect = surf.get_rect(center=(cx, y))
            self.screen.blit(shadow, (rect.x + 2, rect.y + 2))
            self.screen.blit(surf, rect)
            y += 31
        return y

    def _draw_briefing_overlay(self) -> None:
        blocker = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        blocker.fill((8, 10, 16, TUT_BRIEFING_OVERLAY_ALPHA))
        self.screen.blit(blocker, (0, 0))
        prompts = self._prompts_for_step()
        if not prompts:
            return
        card_w = 560
        card_h = 38 + len(prompts) * 31 + 62
        card = pygame.Rect((SCREEN_W - UI_PANEL_W) // 2 - card_w // 2, SCREEN_H // 2 - card_h // 2, card_w, card_h)
        pygame.draw.rect(self.screen, (28, 32, 42), card, border_radius=14)
        pygame.draw.rect(self.screen, (120, 140, 170), card, 2, border_radius=14)
        text_y = self._draw_prompt_lines(prompts, card.top + 24)
        self._draw_understand_button(card.centerx, text_y + 8)

    def _draw_tutorial_overlay(self):
        if self.tut_step == TUT_STEP_DONE:
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H))
        overlay.fill((15, 15, 20))
        overlay.set_colorkey((255, 0, 255))

        if self.tut_step == TUT_STEP_RIGHT_CLOUD and self.right_cloud:
            pygame.draw.ellipse(overlay, (255, 0, 255), self.right_cloud.rect.inflate(18, 18))
        elif self.tut_step == TUT_STEP_LEFT_CLOUD and self.left_cloud:
            pygame.draw.ellipse(overlay, (255, 0, 255), self.left_cloud.rect.inflate(18, 18))
        elif self.tut_step == TUT_STEP_RAIN:
            for cloud in self.clouds:
                pygame.draw.ellipse(overlay, (255, 0, 255), cloud.rect.inflate(18, 18))
        elif self.tut_step == TUT_STEP_SELECT_SEED and self._seed_buttons:
            pygame.draw.rect(overlay, (255, 0, 255), self._seed_buttons[0][1].inflate(8, 8), border_radius=8)
        elif self.tut_step in (TUT_STEP_PLANT, TUT_STEP_CARE, TUT_STEP_HARVEST):
            pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
            for cloud in self.clouds:
                pygame.draw.ellipse(overlay, (255, 0, 255), cloud.rect.inflate(10, 10))
        elif self.tut_step == TUT_STEP_WILT:
            pygame.draw.rect(overlay, (255, 0, 255), self.wilt_slot.rect.inflate(15, 15), border_radius=10)
            for cloud in self.clouds:
                pygame.draw.ellipse(overlay, (255, 0, 255), cloud.rect.inflate(10, 10))
        elif self.tut_step == TUT_STEP_TITAN_BLOCK:
            pygame.draw.rect(overlay, (255, 0, 255), self.titan_slot.rect.inflate(28, 28), border_radius=16)
            for cloud in self.clouds:
                pygame.draw.ellipse(overlay, (255, 0, 255), cloud.rect.inflate(10, 10))

        overlay.set_alpha(TUT_STEP_OVERLAY_ALPHA)
        self.screen.blit(overlay, (0, 0))
        if self.tut_step == TUT_STEP_TITAN_BLOCK:
            self._draw_titan_marker()
        prompts = self._prompts_for_step()
        if prompts:
            self._draw_prompt_lines(prompts, 55)

    def _draw_titan_marker(self) -> None:
        rect = self.titan_slot.rect.inflate(26, 26)
        pulse = 2 + int((pygame.time.get_ticks() / 180) % 3)
        pygame.draw.ellipse(self.screen, (220, 55, 55), rect, pulse)
        pygame.draw.line(self.screen, (255, 120, 120), (rect.centerx - 22, rect.centery), (rect.centerx + 22, rect.centery), 2)
        pygame.draw.line(self.screen, (255, 120, 120), (rect.centerx, rect.centery - 22), (rect.centerx, rect.centery + 22), 2)
