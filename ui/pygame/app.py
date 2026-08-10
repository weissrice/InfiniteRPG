"""Pygame application — main loop, window, event dispatch."""

from __future__ import annotations

import sys
import time

import pygame

from engine.game import GameEngine
from engine.state import GameState

from .constants import (
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    COLOR_BG,
)
from .camera import Camera
from .world_renderer import WorldRenderer, LocalRenderer
from .hud import HUD
from .input_handler import InputHandler


_HELP_LINES = [
    "INFINITE RPG",
    "",
    "SYSTEM COMMANDS (prefix with /)",
    "  /inventory .... Show your items",
    "  /status ....... Show player stats",
    "  /quests ....... Show active quests",
    "  /map .......... Show world map",
    "  /save ......... Save the game",
    "  /load ......... Load saved game",
    "  /help ......... Show this help",
    "  /quit ......... Exit the game",
    "",
    "MOVEMENT",
    "  WASD / Arrows . Move to adjacent location",
    "",
    "GAMEPLAY",
    "  Type naturally to interact with the world.",
    "  The Game Master interprets your actions.",
    "",
    "  Examples:",
    "    inspect the door",
    "    talk to the old man",
    "    search under the bed",
    "    I ask Sarah about the forest",
    "    knock on the door three times",
    "    try to climb onto the roof",
    "    throw the key into the fireplace",
    "",
    "Tab .... Toggle text/movement mode (or event log Latest/History)",
    "Enter ... Submit input",
    "Escape .. Cancel / clear / quit",
]


class App:
    """Top-level Pygame application for InfiniteRPG."""

    def __init__(self, engine: GameEngine | None = None):
        pygame.init()
        self.screen = pygame.display.set_mode(
            (DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT),
            pygame.RESIZABLE,
        )
        pygame.display.set_caption("Infinite RPG")
        self.clock = pygame.time.Clock()

        self.engine = engine or GameEngine()
        self.game = self.engine.game  # shortcut to GameState
        self.world_renderer = WorldRenderer(self.game)
        self.local_renderer = LocalRenderer(self.game)
        self.hud = HUD()
        self.input_handler = InputHandler(self.engine)
        self.camera = Camera(0, 0)

        self.event_log: list[tuple[str, str]] = []
        self.event_scroll: int = 0
        self.event_auto_scroll: bool = True
        self.event_mode: str = "latest"  # "latest" or "history"
        self._max_events: int = 100

        self.show_help: bool = False

        self._sync_camera()

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def _add_event(self, entry_type: str, text: str) -> None:
        """Append an event to the log."""
        self.event_log.append((entry_type, text))
        if len(self.event_log) > self._max_events:
            self.event_log = self.event_log[-self._max_events:]
        self.event_auto_scroll = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            now_ms = pygame.time.get_ticks()

            for event in pygame.event.get():
                # Help overlay: any key dismisses
                if self.show_help:
                    if event.type == pygame.KEYDOWN:
                        self.show_help = False
                    continue

                # Event log scrolling (when no overlay is active)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        if not self.input_handler.text_mode:
                            if self.event_mode == "latest":
                                self.event_mode = "history"
                            else:
                                self.event_mode = "latest"
                                self.event_auto_scroll = True
                            continue
                    elif event.key == pygame.K_PAGEUP:
                        self.event_scroll = max(0, self.event_scroll - 3)
                        self.event_auto_scroll = False
                        continue
                    elif event.key == pygame.K_PAGEDOWN:
                        self.event_scroll += 3
                        self.event_auto_scroll = False
                        continue

                if event.type == pygame.MOUSEWHEEL:
                    self.event_scroll -= event.y * 3
                    self.event_scroll = max(0, self.event_scroll)
                    self.event_auto_scroll = False
                    continue

                # Before processing RETURN, prepare thinking indicator for AI calls
                if (event.type == pygame.KEYDOWN
                        and event.key == pygame.K_RETURN
                        and self.input_handler.input_buffer.strip()):
                    text = self.input_handler.input_buffer.strip()
                    if not text.startswith("/"):
                        self._add_event("thinking",
                                        "The Game Master is pondering...")
                        self._draw()
                        pygame.display.flip()

                result = self.input_handler.handle_event(event, self.game)

                # Clean up thinking entry if present
                if (self.event_log
                        and self.event_log[-1][0] == "thinking"):
                    self.event_log.pop()
                    self.event_auto_scroll = True

                if result == "__QUIT__":
                    running = False
                    break
                elif result == "__HELP__":
                    self.show_help = True
                elif result:
                    entry_type = "narration" if self.input_handler.last_was_ai else "system"
                    self._add_event(entry_type, result)
                    self.world_renderer.refresh()
                    self._sync_camera()

            self.input_handler.update_cursor(now_ms)
            self._draw()
            pygame.display.flip()

        self.engine.close()
        pygame.quit()

    # ------------------------------------------------------------------
    # Local vs world rendering
    # ------------------------------------------------------------------

    def _use_local_renderer(self) -> bool:
        """Return True if the current location should use local rendering."""
        from engine.actions import has_local_movement
        return has_local_movement(self.game)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        self.screen.fill(COLOR_BG)
        w, h = self.screen.get_size()

        # Compute layout regions
        map_area = self.hud.map_area_rect(w, h)

        # Draw map into its sub-surface
        map_surface = pygame.Surface((map_area.width, map_area.height))
        map_surface.fill(COLOR_BG)

        if self._use_local_renderer():
            self._sync_local_camera(map_area.width, map_area.height)
            cam_x, cam_y = self.camera.x, self.camera.y
            self.local_renderer.draw(map_surface, cam_x, cam_y)
        else:
            self._sync_camera(map_area.width, map_area.height)
            cam_x, cam_y = self.camera.x, self.camera.y
            self.world_renderer.draw(map_surface, cam_x, cam_y)

        self.screen.blit(map_surface, map_area.topleft)

        # Draw HUD elements (header, side panel, footer)
        self.hud.draw(self.screen, self.game,
                      self.input_handler.input_buffer,
                      self.input_handler._cursor_blink,
                      self.input_handler.text_mode)

        # Draw event log (persistent)
        self.event_scroll = self.hud.draw_event_log(
            self.screen, self.event_log,
            self.event_scroll, self.event_auto_scroll, w, h,
            mode=self.event_mode,
        )

        # Help overlay (full screen)
        if self.show_help:
            self._draw_help()

    def _draw_help(self) -> None:
        w, h = self.screen.get_size()
        # Semi-transparent dark overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Help panel
        font_title = pygame.font.Font(None, 28)
        font_body = pygame.font.Font(None, 18)
        font_hint = pygame.font.Font(None, 16)

        title_surf = font_title.render("HELP", True, (100, 180, 255))
        title_x = (w - title_surf.get_width()) // 2
        title_y = 60

        # Measure total height
        line_height = 20
        total_height = 40 + len(_HELP_LINES) * line_height + 30
        panel_rect = pygame.Rect(
            (w - 500) // 2,
            title_y - 10,
            500,
            total_height,
        )
        pygame.draw.rect(self.screen, (32, 32, 44), panel_rect)
        pygame.draw.rect(self.screen, (100, 180, 255), panel_rect, 2)

        self.screen.blit(title_surf, (title_x, title_y))

        y = title_y + title_surf.get_height() + 12
        for line in _HELP_LINES:
            if not line:
                y += line_height // 2
                continue
            if line.startswith("COMMANDS"):
                color = (100, 180, 255)
            elif line.endswith(":"):
                color = (200, 200, 200)
            elif line.startswith("  "):
                color = (180, 180, 180)
            else:
                color = (160, 160, 160)
            surf = font_body.render(line, True, color)
            self.screen.blit(surf, (panel_rect.x + 20, y))
            y += line_height

        hint = font_hint.render("Press any key to close", True, (120, 120, 120))
        self.screen.blit(hint, ((w - hint.get_width()) // 2, y + 8))

    # ------------------------------------------------------------------
    # Camera sync
    # ------------------------------------------------------------------

    def _sync_camera(self, view_w: int | None = None,
                     view_h: int | None = None) -> None:
        if view_w is not None and view_h is not None:
            self.camera.resize(view_w, view_h)
        px, py = self.world_renderer.player_pixel_pos()
        self.camera.update(px, py,
                           self.world_renderer.pixel_width,
                           self.world_renderer.pixel_height)

    def _sync_local_camera(self, view_w: int | None = None,
                           view_h: int | None = None) -> None:
        """Center camera on the player within the local map."""
        if view_w is not None and view_h is not None:
            self.camera.resize(view_w, view_h)
        px, py = self.local_renderer.player_pixel_pos()
        self.camera.update(px, py,
                           self.local_renderer.pixel_width(),
                           self.local_renderer.pixel_height())


def run_game(engine: GameEngine | None = None) -> None:
    """Entry point — create and run the Pygame application."""
    app = App(engine)
    app.run()
