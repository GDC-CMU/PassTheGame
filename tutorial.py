import pygame
from game import Game, TOOL_SCARECROW
from settings import (
    SCREEN_W, SCREEN_H, UI_PANEL_W, FPS,
    OVERWATER_THRESHOLD, OVERSUN_THRESHOLD,
    SCARECROW_COST,
)

# Tutorial steps:
# 0 Dead plant  1 Select seed  2 Plant  3 Grow/water  4 Harvest
# 5 Sell  6 Critters  7 Tools  8 Bosses  9 Save & HUD  10 Done
TUT_STEP_DONE = 10
TUT_STEP_EXIT = 11

# Full-screen briefing blocks input until the player confirms.
TUT_BRIEFING_OVERLAY_ALPHA = 245
TUT_STEP_OVERLAY_ALPHA = 185


class Tutorial(Game):
    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.font_tut = pygame.font.SysFont("arial", 26, bold=True)
        self.font_warn = pygame.font.SysFont("arial", 22, bold=True)
        self.font_hint = pygame.font.SysFont("arial", 14)

        self.tut_step = 0
        self._tut_briefing = True
        self._tut_step3_phase = "cloud_controls"
        self._tut_critter_seen = False
        self._understand_btn_rect = pygame.Rect(0, 0, 0, 0)

        # Disable random bosses/weather; critters enabled from step 6 onward.
        self._bosses = []
        self._critters = []
        self._weather_event = "None"

        self.target_slot = self.slots[2]
        self.tool_demo_slot = self.slots[1]
        self.target_slot.plant(self.seeds[0])

        try:
            self.target_slot.dead = True
            self.target_slot.harvestable = False
        except AttributeError:
            self.target_slot._dead = True
            self.target_slot._harvestable = False

        for slot in self.slots:
            if slot != self.target_slot:
                slot.clear()

        self.crisis_active = False
        self.crisis_reason = None
        self.crisis_btn_rect = pygame.Rect((SCREEN_W - UI_PANEL_W) // 2 - 80, SCREEN_H // 2 + 50, 160, 40)

    def _advance_to(self, step: int) -> None:
        self.tut_step = step
        self._tut_briefing = True
        self._on_enter_step(step)

    def _on_enter_step(self, step: int) -> None:
        if step == 6:
            self._critters = [self.squirrel, self.snake]
            self._tut_critter_seen = False
            if not self.target_slot.planted:
                self.target_slot.plant(self.seeds[0])
            self.squirrel.force_spawn(field_rect=self._field_rect, ground_rect=self._ground_rect)
        elif step == 7:
            self.money = max(self.money, int(SCARECROW_COST) + 10)
            self.selected_tool = None
            self.tool_demo_slot.clear()
        elif step == 3:
            self._tut_step3_phase = "cloud_controls"
            if self.target_slot.planted and self.target_slot.seed:
                mid_w = (self.target_slot.seed.water_min + self.target_slot.seed.water_max) / 2.0
                mid_s = (self.target_slot.seed.sun_min + self.target_slot.seed.sun_max) / 2.0
                setattr(self.target_slot, "water", mid_w)
                setattr(self.target_slot, "sun", mid_s)

    def _dismiss_briefing(self) -> None:
        if self.tut_step == 3 and self._tut_step3_phase == "cloud_controls":
            self._tut_step3_phase = "playing"
            self._tut_briefing = False
            return
        if self.tut_step in (8, 9):
            self._advance_to(self.tut_step + 1)
        elif self.tut_step == TUT_STEP_DONE:
            self.tut_step = TUT_STEP_EXIT
        else:
            self._tut_briefing = False

    def _prompts_for_step(self) -> list[str]:
        if self.tut_step == 0:
            return ["Oh no! The plant is dead!", "Click it to clear away the dead debris."]
        if self.tut_step == 1:
            return ["Perfectly cleared!", "Now, click the Carrot Seed to select it."]
        if self.tut_step == 2:
            return ["Click the highlighted clean soil plot", "to plant your selected seed."]
        if self.tut_step == 3:
            if self._tut_step3_phase == "cloud_controls":
                return [
                    "Left cloud: WASD. Right cloud: Arrow keys.",
                    "Click a cloud to turn rain on or off.",
                ]
            return [
                "Watch the growth bar above your plant fill up.",
                "Keep Water & Sun in the green bars.",
                "Rain on your crop, or move clouds off the sun to dry it.",
            ]
        if self.tut_step == 4:
            return [
                "A full growth bar and green frame mean the crop is ready.",
                "Click the plant to add the harvest to your Inventory.",
            ]
        if self.tut_step == 5:
            return [
                "Harvested crops go to Inventory.",
                "Click Sell All, then Confirm, to earn money.",
            ]
        if self.tut_step == 6:
            return [
                "Chipmunk and snake thieves steal plants!",
                "Click a thief to scare it away before it eats your crop.",
            ]
        if self.tut_step == 7:
            return [
                "Tools: Compost speeds growth, Scarecrow blocks thieves,",
                "Lightning Rod protects from boss strikes.",
                f"Select Scarecrow (${SCARECROW_COST}), then click the highlighted empty plot.",
            ]
        if self.tut_step == 8:
            return [
                "Storm Titan and Cyclone Titan strike your farm on a timer.",
                "Move a raining cloud over the target to block lightning.",
                "Blocked strikes damage the boss — check Farm Status (top-left).",
            ]
        if self.tut_step == 9:
            return [
                "Save writes your farm to disk; the game auto-saves every 2 minutes.",
                "Farm Status tracks day, season, market, weather, and boss timers.",
            ]
        if self.tut_step == TUT_STEP_DONE:
            return [
                "Tutorial complete!",
                "You know farming, selling, thieves, tools, and bosses.",
            ]
        return []

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return "menu"
                if self._main_menu_button_clicked(event):
                    return "menu"

                if self._intercept_event(event):
                    continue

                if not self.paused and not self.crisis_active and not self._tut_briefing:
                    for c in self.clouds:
                        c.handle_event(event)
                if not self._tut_briefing and self._handle_critter_event(event):
                    continue
                if not self._tut_briefing:
                    self._handle_farm_event(event)

            self._update()
            if not self._tut_briefing:
                self._check_progress()
            self._draw()

            if self.tut_step == TUT_STEP_EXIT:
                return "menu"

    def _intercept_event(self, event):
        if self._tut_briefing:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._understand_btn_rect.collidepoint(event.pos):
                    self._dismiss_briefing()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.crisis_active:
                if self.crisis_btn_rect.collidepoint(event.pos):
                    self._resolve_crisis()
                return True

            if self.tut_step == 0:
                if not self.target_slot.rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 1:
                seed_rect = self._seed_buttons[0][1] if self._seed_buttons else pygame.Rect(0, 0, 0, 0)
                if not seed_rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 2:
                if not self.target_slot.rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 3:
                if self._tut_step3_phase != "playing":
                    return True
                if any(c.rect.collidepoint(event.pos) for c in self.clouds):
                    return False
                return True
            elif self.tut_step == 4:
                if not self.target_slot.rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 5:
                if self._show_sell_confirm:
                    return False
                if self._sell_button.collidepoint(event.pos):
                    return False
                return True
            elif self.tut_step == 6:
                for critter in self._critters:
                    if critter.active and critter.rect.collidepoint(event.pos):
                        return False
                return True
            elif self.tut_step == 7:
                tool = self._tool_at_pos(event.pos)
                if tool == TOOL_SCARECROW:
                    return False
                slot = self._slot_at_pos(event.pos)
                if (
                    slot is self.tool_demo_slot
                    and self.selected_tool == TOOL_SCARECROW
                    and not slot.planted
                ):
                    return False
                return True

        if event.type == pygame.KEYDOWN:
            if self.crisis_active:
                return True
            if self.tut_step == 3 and self._tut_step3_phase == "playing" and event.key in (
                pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                pygame.K_a, pygame.K_w, pygame.K_s, pygame.K_d,
            ):
                return False
            return True

        return False

    def _update(self):
        if self.crisis_active or self._tut_briefing:
            orig_paused = self.paused
            self.paused = True
            super()._update()
            self.paused = orig_paused
        else:
            super()._update()
            self._monitor_plant_health()

    def _monitor_plant_health(self):
        if self.tut_step != 3 or self._tut_step3_phase != "playing":
            return

        water = getattr(self.target_slot, "water", 50)
        sun = getattr(self.target_slot, "sun", 50)

        if water < 15:
            self.crisis_active = True
            self.crisis_reason = "low_water"
        elif water > (float(OVERWATER_THRESHOLD) - 15):
            self.crisis_active = True
            self.crisis_reason = "high_water"
        elif sun < 15:
            self.crisis_active = True
            self.crisis_reason = "low_sun"
        elif sun > (float(OVERSUN_THRESHOLD) - 15):
            self.crisis_active = True
            self.crisis_reason = "high_sun"

    def _resolve_crisis(self):
        self.crisis_active = False
        if self.crisis_reason == "low_water":
            setattr(self.target_slot, "water", 40.0)
        elif self.crisis_reason == "high_water":
            setattr(self.target_slot, "water", float(OVERWATER_THRESHOLD) - 40.0)
        elif self.crisis_reason == "low_sun":
            setattr(self.target_slot, "sun", 40.0)
        elif self.crisis_reason == "high_sun":
            setattr(self.target_slot, "sun", float(OVERSUN_THRESHOLD) - 40.0)
        self.crisis_reason = None

    def _check_progress(self):
        if self.tut_step == 0 and not self.target_slot.dead:
            self._advance_to(1)
        elif self.tut_step == 1 and self.selected_seed is not None:
            self._advance_to(2)
        elif self.tut_step == 2 and self.target_slot.planted:
            self._advance_to(3)
        elif self.tut_step == 3:
            if self._tut_step3_phase != "playing":
                return
            raining_cloud_detected = False
            for c in self.clouds:
                if getattr(c, "raining", False) and (
                    c.rect.left <= self.target_slot.rect.centerx <= c.rect.right
                ):
                    raining_cloud_detected = True
                    break

            if raining_cloud_detected:
                stages = self.target_slot.seed.growth_stages
                try:
                    self.target_slot.growth_stage = stages
                    self.target_slot.harvestable = True
                except AttributeError:
                    self.target_slot._growth_stage = stages
                    self.target_slot._harvestable = True
                self._advance_to(4)

            elif self.target_slot.dead:
                try:
                    self.target_slot.dead = False
                except AttributeError:
                    self.target_slot._dead = False
                setattr(self.target_slot, "water", 50.0)
                setattr(self.target_slot, "sun", 50.0)

        elif self.tut_step == 4 and not self.target_slot.planted:
            self._advance_to(5)
        elif self.tut_step == 5 and not self.inventory:
            self._advance_to(6)
        elif self.tut_step == 6:
            if self.squirrel.active or self.snake.active:
                self._tut_critter_seen = True
            elif self._tut_critter_seen:
                self._advance_to(7)
        elif self.tut_step == 7 and self.tool_demo_slot.has_scarecrow:
            self._advance_to(8)

    def _draw(self):
        orig_flip = pygame.display.flip
        pygame.display.flip = lambda: None

        super()._draw()

        pygame.display.flip = orig_flip

        if self._tut_briefing:
            self._draw_briefing_overlay()
        else:
            self._draw_tutorial_overlay()
        if self.crisis_active:
            self._draw_crisis_window()
        if not self._tut_briefing:
            self._draw_main_menu_button()
            self._draw_exit_hint()

        pygame.display.flip()

    def _draw_exit_hint(self) -> None:
        btn = self._main_menu_btn
        lines = (
            "Main Menu or ESC: main menu",
            "P: pause",
        )
        y = btn.bottom + 6
        for line in lines:
            shadow = self.font_hint.render(line, True, (0, 0, 0))
            surf = self.font_hint.render(line, True, (220, 225, 235))
            rect = surf.get_rect(midtop=(btn.centerx, y))
            self.screen.blit(shadow, (rect.x + 1, rect.y + 1))
            self.screen.blit(surf, rect)
            y += self.font_hint.get_height() + 1

    def _draw_understand_button(self, centerx: int, top: int) -> None:
        self._understand_btn_rect = pygame.Rect(centerx - 95, top, 190, 44)
        mouse_pos = pygame.mouse.get_pos()
        hovered = self._understand_btn_rect.collidepoint(mouse_pos)
        bg = (70, 130, 85) if hovered else (55, 105, 70)
        pygame.draw.rect(self.screen, bg, self._understand_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, (150, 210, 165), self._understand_btn_rect, 2, border_radius=8)
        label = self.font_warn.render("I understand", True, (255, 255, 255))
        self.screen.blit(label, label.get_rect(center=self._understand_btn_rect.center))

    def _draw_prompt_lines(self, prompts: list[str], start_y: int) -> int:
        y_offset = start_y
        cx = (SCREEN_W - UI_PANEL_W) // 2
        for line in prompts:
            t_surf = self.font_tut.render(line, True, (255, 255, 255))
            t_shadow = self.font_tut.render(line, True, (0, 0, 0))
            t_rect = t_surf.get_rect(center=(cx, y_offset))
            self.screen.blit(t_shadow, (t_rect.x + 2, t_rect.y + 2))
            self.screen.blit(t_surf, t_rect)
            y_offset += 32
        return y_offset

    def _draw_briefing_overlay(self) -> None:
        blocker = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        blocker.fill((8, 10, 16, TUT_BRIEFING_OVERLAY_ALPHA))
        self.screen.blit(blocker, (0, 0))

        prompts = self._prompts_for_step()
        if not prompts:
            return

        card_w, card_h = 560, 40 + len(prompts) * 32 + 70
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

        prompts = self._prompts_for_step()

        if self.tut_step == 0:
            pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
        elif self.tut_step == 1:
            if self._seed_buttons:
                rect = self._seed_buttons[0][1]
                pygame.draw.circle(overlay, (255, 0, 255), rect.center, 32)
        elif self.tut_step == 2:
            pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
        elif self.tut_step == 3:
            if self._tut_step3_phase == "playing":
                growth_bar = pygame.Rect(
                    self.target_slot.rect.centerx - (self.target_slot.rect.width - 4) // 2,
                    self.target_slot.rect.top - 44,
                    self.target_slot.rect.width - 4,
                    10,
                )
                pygame.draw.rect(overlay, (255, 0, 255), growth_bar.inflate(6, 6), border_radius=6)
                pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
                for c in self.clouds:
                    pygame.draw.ellipse(overlay, (255, 0, 255), c.rect.inflate(10, 10))
        elif self.tut_step == 4:
            pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
        elif self.tut_step == 5:
            pygame.draw.rect(overlay, (255, 0, 255), self._sell_button.inflate(8, 8), border_radius=8)
        elif self.tut_step == 6:
            for critter in self._critters:
                if critter.active:
                    pygame.draw.rect(overlay, (255, 0, 255), critter.rect.inflate(12, 12), border_radius=8)
            pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
        elif self.tut_step == 7:
            for _tool_id, rect in self._tool_buttons:
                pygame.draw.rect(overlay, (255, 0, 255), rect.inflate(6, 6), border_radius=8)
            pygame.draw.rect(
                overlay, (255, 0, 255), self.tool_demo_slot.rect.inflate(15, 15), border_radius=10
            )

        overlay.set_alpha(TUT_STEP_OVERLAY_ALPHA)
        self.screen.blit(overlay, (0, 0))

        if prompts and not (self.tut_step == 3 and self._tut_step3_phase == "cloud_controls"):
            self._draw_prompt_lines(prompts, 55)

    def _draw_crisis_window(self):
        win_w, win_h = 460, 180
        window = pygame.Rect((SCREEN_W - UI_PANEL_W) // 2 - win_w // 2, (SCREEN_H // 2) - win_h // 2, win_w, win_h)

        pygame.draw.rect(self.screen, (45, 20, 25), window, border_radius=12)
        pygame.draw.rect(self.screen, (220, 75, 80), window, 3, border_radius=12)

        title_surf = self.font_warn.render("⚠️ HARVEST WARNING ⚠️", True, (240, 90, 95))
        self.screen.blit(title_surf, title_surf.get_rect(center=(window.centerx, window.top + 25)))

        msg = ""
        if self.crisis_reason == "low_water":
            msg = "Your crop is completely dried out! Move a cloud overhead and click it to rain."
        elif self.crisis_reason == "high_water":
            msg = "The soil is drowning! Move the clouds completely away so the sun dries it."
        elif self.crisis_reason == "low_sun":
            msg = "It's too dark! Move clouds away from the sun so it can heat up the crops."
        elif self.crisis_reason == "high_sun":
            msg = "The heat is too high! Keep a cloud directly above to shadow and cool it."

        msg_surf = self.font_warn.render(msg, True, (240, 240, 240))
        if msg_surf.get_width() > win_w - 30:
            words = msg.split(" ")
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            s1 = self.font_warn.render(line1, True, (240, 240, 240))
            s2 = self.font_warn.render(line2, True, (240, 240, 240))
            self.screen.blit(s1, s1.get_rect(center=(window.centerx, window.top + 65)))
            self.screen.blit(s2, s2.get_rect(center=(window.centerx, window.top + 90)))
        else:
            self.screen.blit(msg_surf, msg_surf.get_rect(center=(window.centerx, window.top + 75)))

        mouse_pos = pygame.mouse.get_pos()
        btn_color = (190, 55, 60) if self.crisis_btn_rect.collidepoint(mouse_pos) else (145, 40, 45)
        pygame.draw.rect(self.screen, btn_color, self.crisis_btn_rect, border_radius=6)
        pygame.draw.rect(self.screen, (250, 150, 155), self.crisis_btn_rect, 2, border_radius=6)

        btn_text = self.font_warn.render("I'll fix it!", True, (255, 255, 255))
        self.screen.blit(btn_text, btn_text.get_rect(center=self.crisis_btn_rect.center))
