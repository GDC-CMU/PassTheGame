import pygame
from game import Game
from settings import (
    SCREEN_W, SCREEN_H, UI_PANEL_W, FPS,
    OVERWATER_THRESHOLD, OVERSUN_THRESHOLD
)

class Tutorial(Game):
    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.font_tut = pygame.font.SysFont("arial", 26, bold=True)
        self.font_warn = pygame.font.SysFont("arial", 22, bold=True)

        # Tutorial State Machine
        # 0: Dead Plant, 1: Select Seed, 2: Plant Seed, 3: Growing/Watering, 4: Harvest, 5: Done
        self.tut_step = 0

        # Disable random events/bosses during tutorial to prevent distractions
        self._bosses = []
        self._critters = []
        self._weather_event = "None"

        # Configure our tutorial focus plot (middle slot)
        self.target_slot = self.slots[2]

        # Set up a dramatic dead plant using safe methods
        self.target_slot.plant(self.seeds[0])

        # Safely force the state to dead (bypassing property setters if needed)
        try:
            self.target_slot.dead = True
            self.target_slot.harvestable = False
        except AttributeError:
            self.target_slot._dead = True
            self.target_slot._harvestable = False

        # Clear out any other randomly filled slots
        for slot in self.slots:
            if slot != self.target_slot:
                slot.clear()

        # Crisis management states
        self.crisis_active = False
        self.crisis_reason = None
        self.crisis_btn_rect = pygame.Rect((SCREEN_W - UI_PANEL_W) // 2 - 80, SCREEN_H // 2 + 50, 160, 40)

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"

                if self._intercept_event(event):
                    continue

                if not self.paused and not self.crisis_active:
                    for c in self.clouds:
                        c.handle_event(event)
                self._handle_farm_event(event)

            self._update()
            self._check_progress()
            self._draw()

            if self.tut_step == 6:
                return "menu"

    def _intercept_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.crisis_active:
                if self.crisis_btn_rect.collidepoint(event.pos):
                    self._resolve_crisis()
                return True

            if self.tut_step == 0:
                if not self.target_slot.rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 1:
                seed_rect = self._seed_buttons[0][1] if self._seed_buttons else pygame.Rect(0,0,0,0)
                if not seed_rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 2:
                if not self.target_slot.rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 3:
                if any(c.rect.collidepoint(event.pos) for c in self.clouds):
                    return False
                return True
            elif self.tut_step == 4:
                if not self.target_slot.rect.collidepoint(event.pos):
                    return True
            elif self.tut_step == 5:
                self.tut_step = 6
                return True

        if event.type == pygame.KEYDOWN:
            if self.crisis_active:
                return True
            if self.tut_step == 3 and event.key in [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN, pygame.K_a, pygame.K_w, pygame.K_s, pygame.K_d]:
                return False
            return True

        return False

    def _update(self):
        if self.crisis_active:
            orig_paused = self.paused
            self.paused = True
            super()._update()
            self.paused = orig_paused
        else:
            super()._update()
            self._monitor_plant_health()

    def _monitor_plant_health(self):
        if self.tut_step != 3:
            return

        water = getattr(self.target_slot, 'water', 50)
        sun = getattr(self.target_slot, 'sun', 50)

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
            setattr(self.target_slot, 'water', 40.0)
        elif self.crisis_reason == "high_water":
            setattr(self.target_slot, 'water', float(OVERWATER_THRESHOLD) - 40.0)
        elif self.crisis_reason == "low_sun":
            setattr(self.target_slot, 'sun', 40.0)
        elif self.crisis_reason == "high_sun":
            setattr(self.target_slot, 'sun', float(OVERSUN_THRESHOLD) - 40.0)
        self.crisis_reason = None

    def _check_progress(self):
        if self.tut_step == 0 and not self.target_slot.dead:
            self.tut_step = 1
        elif self.tut_step == 1 and self.selected_seed is not None:
            self.tut_step = 2
        elif self.tut_step == 2 and self.target_slot.planted:
            self.tut_step = 3
        elif self.tut_step == 3:
            # Check if ANY cloud is raining directly above our target slot horizontally
            raining_cloud_detected = False
            for c in self.clouds:
                if getattr(c, 'raining', False) and (c.rect.left <= self.target_slot.rect.centerx <= c.rect.right):
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

                # Progress safely to the harvesting stage without touching the read-only property
                self.tut_step = 4

            elif self.target_slot.dead:
                try:
                    self.target_slot.dead = False
                except AttributeError:
                    self.target_slot._dead = False
                setattr(self.target_slot, 'water', 50.0)
                setattr(self.target_slot, 'sun', 50.0)

        elif self.tut_step == 4 and not self.target_slot.planted:
            self.tut_step = 5

    def _draw(self):
        orig_flip = pygame.display.flip
        pygame.display.flip = lambda: None

        super()._draw()

        pygame.display.flip = orig_flip

        self._draw_tutorial_overlay()
        if self.crisis_active:
            self._draw_crisis_window()

        pygame.display.flip()

    def _draw_tutorial_overlay(self):
        if self.tut_step == 5:
            self.screen.fill((25, 30, 40))
            text = self.font_tut.render("Tutorial completed! You are ready to manage your farm.", True, (245, 220, 105))
            self.screen.blit(text, text.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
            sub = pygame.font.SysFont("arial", 18).render("Click anywhere to head back to the Main Menu", True, (190, 190, 190))
            self.screen.blit(sub, sub.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 45)))
            return

        overlay = pygame.Surface((SCREEN_W, SCREEN_H))
        overlay.fill((15, 15, 20))
        overlay.set_colorkey((255, 0, 255))

        prompts = []

        if self.tut_step == 0:
            rect = self.target_slot.rect
            pygame.draw.rect(overlay, (255, 0, 255), rect.inflate(15, 15), border_radius=10)
            prompts = ["Oh no! The plant is dead!", "Click it to clear away the dead debris."]
        elif self.tut_step == 1:
            if self._seed_buttons:
                rect = self._seed_buttons[0][1]
                pygame.draw.circle(overlay, (255, 0, 255), rect.center, 32)
            prompts = ["Perfectly cleared!", "Now, click the Carrot Seed to select it."]
        elif self.tut_step == 2:
            rect = self.target_slot.rect
            pygame.draw.rect(overlay, (255, 0, 255), rect.inflate(15, 15), border_radius=10)
            prompts = ["Click the highlighted clean soil plot", "to plant your selected seed."]
        elif self.tut_step == 3:
            pygame.draw.rect(overlay, (255, 0, 255), self.target_slot.rect.inflate(15, 15), border_radius=10)
            for c in self.clouds:
                pygame.draw.ellipse(overlay, (255, 0, 255), c.rect.inflate(10, 10))
            prompts = [
                "Move clouds with Arrow/WASD keys and click them to drop rain!",
                "Keep Water & Sun balanced to grow your crops!"
            ]
        elif self.tut_step == 4:
            rect = self.target_slot.rect
            pygame.draw.rect(overlay, (255, 0, 255), rect.inflate(15, 15), border_radius=10)
            prompts = ["It's fully mature!", "Click the grown plant to harvest your profit."]

        overlay.set_alpha(185)
        self.screen.blit(overlay, (0, 0))

        if prompts:
            y_offset = 55
            for line in prompts:
                t_surf = self.font_tut.render(line, True, (255, 255, 255))
                t_shadow = self.font_tut.render(line, True, (0, 0, 0))
                t_rect = t_surf.get_rect(center=((SCREEN_W - UI_PANEL_W) // 2, y_offset))
                self.screen.blit(t_shadow, (t_rect.x + 2, t_rect.y + 2))
                self.screen.blit(t_surf, t_rect)
                y_offset += 32

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
            words = msg.split(' ')
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
