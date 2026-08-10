"""HUD — header, side panel (player/inventory), event log, input area."""

from __future__ import annotations

from typing import List, Tuple

import pygame

from engine.state import GameState

from .constants import (
    HEADER_HEIGHT, FOOTER_HEIGHT,
    EVENT_LOG_MIN_HEIGHT, EVENT_LOG_RATIO,
    COLOR_BG, COLOR_PANEL_BG, COLOR_PANEL_BORDER,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_BOLD, COLOR_HEADER_BG, COLOR_ACCENT,
    COLOR_EVENT_PLAYER, COLOR_EVENT_NARRATION, COLOR_EVENT_SYSTEM,
    COLOR_EVENT_THINKING,
    HP_BAR_COLOR, HP_BAR_BG, XP_BAR_COLOR, XP_BAR_BG, BAR_HEIGHT,
    FONT_SIZE_TITLE, FONT_SIZE_BODY, FONT_SIZE_SMALL,
    COLOR_PLAYER, COLOR_VISITED, COLOR_UNVISITED, COLOR_NPC, COLOR_ITEM,
    _SCALE_REF_W, _SCALE_REF_H,
)


class HUD:
    """Draws all non-map UI elements onto the window surface."""

    def __init__(self):
        self._fonts: dict[str, pygame.font.Font] = {}

    def _get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = f"px{size}_{bold}"
        if key not in self._fonts:
            self._fonts[key] = pygame.font.Font(None, size)
        return self._fonts[key]

    def _scaled(self, base: int, w: int, h: int) -> int:
        """Scale a base font/size value relative to the reference window."""
        scale = min(w / _SCALE_REF_W, h / _SCALE_REF_H)
        return max(10, int(base * scale))

    # ------------------------------------------------------------------
    # Layout geometry (called by app to compute panel rects)
    # ------------------------------------------------------------------

    @staticmethod
    def header_rect(w: int) -> pygame.Rect:
        return pygame.Rect(0, 0, w, HEADER_HEIGHT)

    @staticmethod
    def footer_rect(w: int, h: int) -> pygame.Rect:
        return pygame.Rect(0, h - FOOTER_HEIGHT, w, FOOTER_HEIGHT)

    @staticmethod
    def event_rect(w: int, h: int) -> pygame.Rect:
        remaining = h - HEADER_HEIGHT - FOOTER_HEIGHT
        event_h = max(EVENT_LOG_MIN_HEIGHT, int(remaining * EVENT_LOG_RATIO))
        top = HEADER_HEIGHT + (remaining - event_h)
        return pygame.Rect(0, top, w, event_h)

    @staticmethod
    def map_rect(w: int, h: int) -> pygame.Rect:
        top = HEADER_HEIGHT
        event_r = HUD.event_rect(w, h)
        return pygame.Rect(0, top, w, max(0, event_r.top - top))

    @staticmethod
    def side_rect(w: int, h: int) -> pygame.Rect:
        map_r = HUD.map_rect(w, h)
        side_w = max(200, int(w * 0.25))
        return pygame.Rect(w - side_w, map_r.top, side_w, map_r.height)

    @staticmethod
    def map_area_rect(w: int, h: int) -> pygame.Rect:
        """The area available for the world map (left of side panel)."""
        map_r = HUD.map_rect(w, h)
        side_r = HUD.side_rect(w, h)
        return pygame.Rect(map_r.left, map_r.top,
                           map_r.width - side_r.width, map_r.height)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, game: GameState,
             input_text: str, cursor_visible: bool,
             text_mode: bool = False) -> None:
        w, h = surface.get_size()
        self._draw_header(surface, w, h, game)
        self._draw_side_panel(surface, w, h, game)
        self._draw_footer(surface, w, h, input_text, cursor_visible, text_mode)

    def _draw_header(self, surface: pygame.Surface, w: int, h: int,
                     game: GameState) -> None:
        rect = self.header_rect(w)
        pygame.draw.rect(surface, COLOR_HEADER_BG, rect)
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (0, rect.bottom - 1), (w, rect.bottom - 1))

        title_size = self._scaled(FONT_SIZE_TITLE, w, h)
        font = self._get_font(title_size)
        title = font.render("\u2726 INFINITE RPG", True, COLOR_ACCENT)
        surface.blit(title, (12, (rect.height - title.get_height()) // 2))

        day_text = f"Day {game.world.day}  |  {game.world.time}  |  "
        weather_text = f"{game.world.weather.condition.title()} {game.world.weather.temperature}\u00b0C"
        info_size = self._scaled(FONT_SIZE_BODY, w, h)
        info_font = self._get_font(info_size)
        right = info_font.render(day_text + weather_text, True, COLOR_TEXT)
        surface.blit(right, (w - right.get_width() - 12,
                             (rect.height - right.get_height()) // 2))

    def _draw_side_panel(self, surface: pygame.Surface, w: int, h: int,
                         game: GameState) -> None:
        rect = self.side_rect(w, h)
        # Background
        pygame.draw.rect(surface, COLOR_PANEL_BG, rect)
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (rect.left, rect.top), (rect.left, rect.bottom))

        pad = self._scaled(10, w, h)
        y = rect.top + pad

        name_size = self._scaled(FONT_SIZE_BODY + 5, w, h)
        label_size = self._scaled(FONT_SIZE_BODY, w, h)
        small_size = self._scaled(FONT_SIZE_SMALL, w, h)
        name_font = self._get_font(name_size)
        label_font = self._get_font(label_size)
        small_font = self._get_font(small_size)

        # Player section header
        header_size = self._scaled(FONT_SIZE_BODY + 1, w, h)
        header_font = self._get_font(header_size)
        txt = header_font.render("PLAYER", True, COLOR_ACCENT)
        surface.blit(txt, (rect.left + pad, y))
        y += txt.get_height() + self._scaled(4, w, h)

        # Player name
        txt = name_font.render(game.player.name, True, COLOR_TEXT_BOLD)
        surface.blit(txt, (rect.left + pad, y))
        y += txt.get_height() + self._scaled(6, w, h)

        # HP bar
        y = self._draw_bar(surface, rect.left + pad, y,
                           rect.width - pad * 2, "HP",
                           game.player.hp, game.player.max_hp,
                           HP_BAR_COLOR, HP_BAR_BG, label_font, w, h)
        y += self._scaled(4, w, h)

        # Level
        txt = label_font.render(f"Level {game.player.level}", True, COLOR_TEXT)
        surface.blit(txt, (rect.left + pad, y))
        y += txt.get_height() + self._scaled(2, w, h)

        # XP bar
        xp_next = game.player.level * 100
        y = self._draw_bar(surface, rect.left + pad, y,
                           rect.width - pad * 2, "XP",
                           game.player.xp, xp_next,
                           XP_BAR_COLOR, XP_BAR_BG, label_font, w, h)
        y += self._scaled(8, w, h)

        # Divider
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (rect.left + pad, y), (rect.right - pad, y))
        y += self._scaled(6, w, h)

        # Attributes section
        txt = header_font.render("ATTRIBUTES", True, COLOR_ACCENT)
        surface.blit(txt, (rect.left + pad, y))
        y += txt.get_height() + self._scaled(4, w, h)

        stats = [
            ("STR", game.player.strength),
            ("VIT", game.player.vitality),
            ("AGI", game.player.agility),
            ("INT", game.player.intelligence),
        ]
        for label, val in stats:
            stat_txt = f"{label}    {val}"
            txt = small_font.render(stat_txt, True, COLOR_TEXT)
            surface.blit(txt, (rect.left + pad, y))
            y += txt.get_height() + self._scaled(2, w, h)
        y += self._scaled(4, w, h)

        # Divider
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (rect.left + pad, y), (rect.right - pad, y))
        y += self._scaled(6, w, h)

        # Inventory section
        txt = header_font.render("INVENTORY", True, COLOR_ACCENT)
        surface.blit(txt, (rect.left + pad, y))
        y += txt.get_height() + self._scaled(4, w, h)

        if game.player.inventory:
            counts: dict[str, int] = {}
            for item in game.player.inventory:
                counts[item] = counts.get(item, 0) + 1
            for item, count in counts.items():
                label = f"{item} x{count}" if count > 1 else item
                txt = small_font.render(label, True, COLOR_TEXT)
                surface.blit(txt, (rect.left + pad, y))
                y += txt.get_height() + self._scaled(2, w, h)
                if y > rect.bottom - self._scaled(80, w, h):
                    txt = small_font.render("...", True, COLOR_TEXT_DIM)
                    surface.blit(txt, (rect.left + pad, y))
                    break
        else:
            txt = small_font.render("(empty)", True, COLOR_TEXT_DIM)
            surface.blit(txt, (rect.left + pad, y))

        # Map legend (anchored to bottom)
        legend_top = rect.bottom - self._scaled(90, w, h)
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (rect.left + pad, legend_top), (rect.right - pad, legend_top))
        y = legend_top + self._scaled(6, w, h)

        txt = header_font.render("MAP LEGEND", True, COLOR_ACCENT)
        surface.blit(txt, (rect.left + pad, y))
        y += txt.get_height() + self._scaled(4, w, h)

        legend_items = [
            ("You", COLOR_PLAYER),
            ("Visited", COLOR_VISITED),
            ("Unvisited", COLOR_UNVISITED),
            ("NPC", COLOR_NPC),
            ("Item", COLOR_ITEM),
        ]
        for label, color in legend_items:
            if y + self._scaled(14, w, h) > rect.bottom:
                break
            pygame.draw.circle(surface, color,
                               (rect.left + pad + self._scaled(6, w, h),
                                y + self._scaled(6, w, h)),
                               self._scaled(5, w, h))
            txt = small_font.render(f"  {label}", True, COLOR_TEXT)
            surface.blit(txt, (rect.left + pad + self._scaled(14, w, h), y))
            y += txt.get_height() + self._scaled(2, w, h)

    def _draw_bar(self, surface: pygame.Surface, x: int, y: int,
                  max_w: int, label: str, current: int, maximum: int,
                  fg: tuple, bg: tuple, font: pygame.font.Font,
                  w: int = 0, h: int = 0) -> int:
        """Draw a labeled progress bar. Returns y below the bar."""
        lbl = font.render(f"{label}:", True, COLOR_TEXT)
        surface.blit(lbl, (x, y))
        bar_x = x + lbl.get_width() + self._scaled(4, w or max_w, h or 200)
        bar_w = max_w - lbl.get_width() - self._scaled(4, w or max_w, h or 200)
        bar_h = BAR_HEIGHT
        # Background
        pygame.draw.rect(surface, bg, (bar_x, y, bar_w, bar_h))
        # Fill
        pct = max(0.0, min(1.0, current / maximum)) if maximum > 0 else 0
        fill_w = int(pct * bar_w)
        if fill_w > 0:
            pygame.draw.rect(surface, fg, (bar_x, y, fill_w, bar_h))
        # Border
        pygame.draw.rect(surface, COLOR_PANEL_BORDER, (bar_x, y, bar_w, bar_h), 1)
        # Text
        val_size = self._scaled(FONT_SIZE_SMALL, w or max_w, h or 200)
        val_font = self._get_font(val_size)
        val = val_font.render(f"{current}/{maximum}", True, COLOR_TEXT_BOLD)
        vx = bar_x + (bar_w - val.get_width()) // 2
        vy = y + (bar_h - val.get_height()) // 2
        surface.blit(val, (vx, vy))
        return y + bar_h + self._scaled(2, w or max_w, h or 200)

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def draw_event_log(self, surface: pygame.Surface,
                       events: List[Tuple[str, str]],
                       scroll_offset: int, auto_scroll: bool,
                       w: int, h: int,
                       mode: str = "history") -> int:
        """Draw the persistent event log panel.

        Args:
            mode: "latest" shows only the newest event.
                  "history" shows scrollable event history.

        Returns the actual scroll offset used (for auto-scroll sync).
        """
        rect = self.event_rect(w, h)
        font_size = self._scaled(FONT_SIZE_BODY + 2, w, h)
        small_size = self._scaled(FONT_SIZE_SMALL, w, h)
        font = self._get_font(font_size)
        small_font = self._get_font(small_size)

        # Background
        pygame.draw.rect(surface, COLOR_PANEL_BG, rect)
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (0, rect.top), (w, rect.top))

        # Title with mode indicator
        title_size = self._scaled(FONT_SIZE_BODY + 1, w, h)
        title_font = self._get_font(title_size)
        if mode == "latest":
            title = title_font.render("EVENT  [Tab: history]", True, COLOR_ACCENT)
        else:
            title = title_font.render("EVENT HISTORY  [Tab: latest]", True, COLOR_ACCENT)
        surface.blit(title, (rect.left + 8, rect.top + 4))
        title_h = title.get_height() + self._scaled(4, w, h)

        # Content area
        content_top = rect.top + title_h + self._scaled(2, w, h)
        content_h = rect.bottom - content_top - self._scaled(4, w, h)
        if content_h <= 0:
            return scroll_offset

        pad = self._scaled(8, w, h)
        line_h = self._scaled(18, w, h)
        max_chars = max(30, (rect.width - pad * 2) // self._scaled(7, w, h))

        if mode == "latest":
            return self._draw_latest_event(
                surface, events, rect, content_top,
                content_h, pad, line_h, max_chars, font, small_font, w, h,
            )

        # History mode (existing behavior)
        max_visible = max(1, content_h // line_h)

        # Wrap all events into display lines, tracking entry type per line
        all_lines: list[str] = []
        line_types: list[str] = []
        for entry_type, text in events:
            prefix = ""
            if entry_type == "player":
                prefix = "> "
            elif entry_type == "thinking":
                prefix = ""
            wrapped = self._word_wrap(prefix + text, max_chars)
            for wl in wrapped:
                all_lines.append(wl)
                line_types.append(entry_type)

        total_lines = len(all_lines)
        max_scroll = max(0, total_lines - max_visible)

        # Determine scroll
        if auto_scroll or total_lines <= max_visible:
            scroll = max_scroll
        else:
            scroll = max(0, min(scroll_offset, max_scroll))

        visible_lines = all_lines[scroll:scroll + max_visible]
        visible_types = line_types[scroll:scroll + max_visible]

        # Draw visible lines
        y = content_top
        for line, ltype in zip(visible_lines, visible_types):
            if ltype == "player":
                color = COLOR_EVENT_PLAYER
            elif ltype == "narration":
                color = COLOR_EVENT_NARRATION
            elif ltype == "system":
                color = COLOR_EVENT_SYSTEM
            elif ltype == "thinking":
                color = COLOR_EVENT_THINKING
            else:
                color = COLOR_TEXT
            surf = font.render(line, True, color)
            surface.blit(surf, (rect.left + pad, y))
            y += line_h

        # Scroll indicator
        if total_lines > max_visible:
            hint = small_font.render(
                f"[{scroll + 1}-{min(scroll + max_visible, total_lines)}/{total_lines}  PgUp/PgDn]",
                True, COLOR_TEXT_DIM,
            )
            surface.blit(hint, (rect.right - hint.get_width() - 8,
                                rect.bottom - hint.get_height() - 2))

        return scroll

    def _draw_latest_event(
        self,
        surface: pygame.Surface,
        events: List[Tuple[str, str]],
        rect: pygame.Rect,
        content_top: int,
        content_h: int,
        pad: int,
        line_h: int,
        max_chars: int,
        font: pygame.font.Font,
        small_font: pygame.font.Font,
        w: int,
        h: int,
    ) -> int:
        """Draw only the most recent event, word-wrapped to fill the area."""
        if not events:
            hint = small_font.render("No events yet.", True, COLOR_TEXT_DIM)
            surface.blit(hint, (rect.left + pad, content_top))
            return 0

        entry_type, text = events[-1]
        prefix = "> " if entry_type == "player" else ""
        wrapped = self._word_wrap(prefix + text, max_chars)

        max_visible = max(1, content_h // line_h)
        visible = wrapped[:max_visible]

        y = content_top
        for line in visible:
            if entry_type == "player":
                color = COLOR_EVENT_PLAYER
            elif entry_type == "narration":
                color = COLOR_EVENT_NARRATION
            elif entry_type == "system":
                color = COLOR_EVENT_SYSTEM
            elif entry_type == "thinking":
                color = COLOR_EVENT_THINKING
            else:
                color = COLOR_TEXT
            surf = font.render(line, True, color)
            surface.blit(surf, (rect.left + pad, y))
            y += line_h

        if len(wrapped) > max_visible:
            hint = small_font.render(
                f"[{len(wrapped)} lines, Tab for history]",
                True, COLOR_TEXT_DIM,
            )
            surface.blit(hint, (rect.right - hint.get_width() - 8,
                                rect.bottom - hint.get_height() - 2))

        return 0

    @staticmethod
    def _word_wrap(text: str, max_chars: int) -> list[str]:
        """Word-wrap text to fit within max_chars per line."""
        lines: list[str] = []
        while len(text) > max_chars:
            brk = text.rfind(" ", 0, max_chars)
            if brk <= 0:
                brk = max_chars
            lines.append(text[:brk])
            text = text[brk:].lstrip()
        lines.append(text)
        return lines

    def _draw_footer(self, surface: pygame.Surface, w: int, h: int,
                     input_text: str, cursor_visible: bool,
                     text_mode: bool = False) -> None:
        rect = self.footer_rect(w, h)
        pygame.draw.rect(surface, COLOR_HEADER_BG, rect)
        pygame.draw.line(surface, COLOR_PANEL_BORDER,
                         (0, rect.top), (w, rect.top))

        font_size = self._scaled(FONT_SIZE_BODY + 2, w, h)
        font = self._get_font(font_size)
        prompt = "> " if text_mode else ">> "
        prompt_surf = font.render(prompt, True, COLOR_ACCENT)
        surface.blit(prompt_surf, (rect.left + 12,
                                   rect.top + (rect.height - prompt_surf.get_height()) // 2))

        # Input text
        text_x = rect.left + 12 + prompt_surf.get_width()
        txt = font.render(input_text, True, COLOR_TEXT)
        surface.blit(txt, (text_x,
                           rect.top + (rect.height - txt.get_height()) // 2))

        # Cursor
        if cursor_visible:
            cx = text_x + txt.get_width() + 2
            cy = rect.top + (rect.height - txt.get_height()) // 2
            pygame.draw.rect(surface, COLOR_ACCENT,
                             (cx, cy, 2, txt.get_height()))
