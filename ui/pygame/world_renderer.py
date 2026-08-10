"""World renderer — builds a tile grid from GameState, draws to surface."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

import pygame

from engine.state import GameState
from engine.world_map import (
    TerrainGrid,
    _build_grid,
    get_location_grid_pos,
    world_to_grid,
    T_GRASS, T_FOREST, T_PATH, T_BUILDING, T_WATER, T_ROCK, T_DOOR,
)

from .constants import (
    TILE_SIZE, WORLD_SCALE, TERRAIN_COLORS,
    COLOR_PLAYER, COLOR_NPC, COLOR_ITEM, COLOR_VISITED, COLOR_UNVISITED,
    COLOR_GRASS,
)


class WorldRenderer:
    """Converts engine GameState into a drawable tile grid and renders it."""

    def __init__(self, game: GameState):
        self.game = game
        self.grid: TerrainGrid = _build_grid(game)
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild cached lookup structures after state changes."""
        self.grid = _build_grid(self.game)
        # Pre-compute grid-cell positions for all locations
        self._loc_cells: Dict[str, Tuple[int, int]] = {}
        for loc_id in self.game.world.locations:
            gx, gy = get_location_grid_pos(self.game, self.grid, loc_id)
            self._loc_cells[loc_id] = (gx, gy)
        # Player grid position
        self.player_gx, self.player_gy = get_location_grid_pos(
            self.game, self.grid, self.game.player.location
        )
        # NPC grid positions
        self._npc_cells: List[Tuple[int, int, str]] = []
        for npc in self.game.world.npcs.values():
            if npc.hp <= 0:
                continue
            loc = self.game.world.locations.get(npc.location)
            if loc:
                gx, gy = world_to_grid(self.game, self.grid, loc.map_x, loc.map_y)
                self._npc_cells.append((gx, gy, npc.name))
        # Item grid positions (locations that have items)
        self._item_cells: List[Tuple[int, int]] = []
        for loc in self.game.world.locations.values():
            if loc.items:
                gx, gy = world_to_grid(self.game, self.grid, loc.map_x, loc.map_y)
                self._item_cells.append((gx, gy))

    def refresh(self) -> None:
        """Call after game state changes (movement, item pickup, etc.)."""
        self._rebuild()

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    @property
    def grid_width(self) -> int:
        return self.grid.width

    @property
    def grid_height(self) -> int:
        return self.grid.height

    @property
    def pixel_width(self) -> int:
        return self.grid.width * TILE_SIZE

    @property
    def pixel_height(self) -> int:
        return self.grid.height * TILE_SIZE

    def player_pixel_pos(self) -> Tuple[int, int]:
        """Player center in world-pixel coordinates."""
        return (self.player_gx * TILE_SIZE + TILE_SIZE // 2,
                self.player_gy * TILE_SIZE + TILE_SIZE // 2)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw visible tiles, markers, and paths onto *surface*."""
        sw, sh = surface.get_size()
        # Determine visible grid range
        gx_start = max(0, int(cam_x // TILE_SIZE) - 1)
        gx_end = min(self.grid.width, int((cam_x + sw) // TILE_SIZE) + 2)
        gy_start = max(0, int(cam_y // TILE_SIZE) - 1)
        gy_end = min(self.grid.height, int((cam_y + sh) // TILE_SIZE) + 2)

        # Draw terrain tiles
        for gy in range(gy_start, gy_end):
            for gx in range(gx_start, gx_end):
                sx = gx * TILE_SIZE - cam_x
                sy = gy * TILE_SIZE - cam_y
                cell = self.grid.get(gx, gy)
                color = TERRAIN_COLORS.get(cell, COLOR_GRASS)
                pygame.draw.rect(surface, color, (sx, sy, TILE_SIZE, TILE_SIZE))
                # Subtle grid lines
                grid_color = (color[0] // 3, color[1] // 3, color[2] // 3)
                pygame.draw.rect(surface, grid_color, (sx, sy, TILE_SIZE, TILE_SIZE), 1)

        # Draw location markers (visited * / unvisited initial)
        visited: Set[str] = self.game.visited_locations
        for loc_id, (lgx, lgy) in self._loc_cells.items():
            if not (gx_start <= lgx < gx_end and gy_start <= lgy < gy_end):
                continue
            sx = lgx * TILE_SIZE - cam_x
            sy = lgy * TILE_SIZE - cam_y
            cx = sx + TILE_SIZE // 2
            cy = sy + TILE_SIZE // 2
            if loc_id == self.game.player.location:
                continue  # player marker drawn below
            if loc_id in visited:
                color = COLOR_VISITED
                text = "*"
            else:
                loc = self.game.world.locations[loc_id]
                color = COLOR_UNVISITED
                text = loc.name[0].upper()
            self._draw_marker(surface, cx, cy, text, color)

        # Draw item markers
        for igx, igy in self._item_cells:
            if not (gx_start <= igx < gx_end and gy_start <= igy < gy_end):
                continue
            sx = igx * TILE_SIZE - cam_x
            sy = igy * TILE_SIZE - cam_y
            self._draw_marker(surface, sx + TILE_SIZE - 6, sy + 4, "I", COLOR_ITEM)

        # Draw NPC markers
        for ngx, ngy, name in self._npc_cells:
            if not (gx_start <= ngx < gx_end and gy_start <= ngy < gy_end):
                continue
            sx = ngx * TILE_SIZE - cam_x
            sy = ngy * TILE_SIZE - cam_y
            self._draw_marker(surface, sx + 4, sy + 4, "N", COLOR_NPC)

        # Draw player marker
        sx = self.player_gx * TILE_SIZE - cam_x
        sy = self.player_gy * TILE_SIZE - cam_y
        cx = sx + TILE_SIZE // 2
        cy = sy + TILE_SIZE // 2
        pygame.draw.circle(surface, COLOR_PLAYER, (cx, cy), TILE_SIZE // 3)
        # Small inner circle for depth
        inner = TILE_SIZE // 6
        pygame.draw.circle(surface, (200, 255, 200), (cx, cy), inner)

    def _draw_marker(self, surface: pygame.Surface,
                     cx: int, cy: int, text: str, color: Tuple[int, int, int]) -> None:
        """Draw a small colored marker with a letter."""
        r = 6
        pygame.draw.circle(surface, color, (cx, cy), r)
        # Use default font for the letter
        font = pygame.font.SysFont(None, 14)
        txt = font.render(text, True, (0, 0, 0))
        tx = cx - txt.get_width() // 2
        ty = cy - txt.get_height() // 2
        surface.blit(txt, (tx, ty))


# ---------------------------------------------------------------------------
# Phase 3 — Local map renderer
# ---------------------------------------------------------------------------

from engine.state import GameState, LocalMap
from .constants import (
    LOCAL_TERRAIN_COLORS,
    COLOR_LOCAL_FLOOR, COLOR_LOCAL_WALL, COLOR_LOCAL_PLAYER,
    COLOR_LOCAL_OBJECT, COLOR_LOCAL_EXIT,
)


class LocalRenderer:
    """Renders a local tile map for the current location.

    Used when the player is inside a location that supports local movement
    (Phase 3: old_wooden_house only).
    """

    LOCAL_TILE_SIZE = 40

    def __init__(self, game: GameState):
        self.game = game

    @property
    def tile_size(self) -> int:
        return self.LOCAL_TILE_SIZE

    def current_local_map(self) -> LocalMap | None:
        """Return the LocalMap for the player's current location, or None."""
        return self.game.local_maps.get(self.game.player.location)

    def pixel_width(self) -> int:
        lm = self.current_local_map()
        if lm is None:
            return 0
        return lm.width * self.LOCAL_TILE_SIZE

    def pixel_height(self) -> int:
        lm = self.current_local_map()
        if lm is None:
            return 0
        return lm.height * self.LOCAL_TILE_SIZE

    def player_pixel_pos(self) -> Tuple[int, int]:
        """Player center in local-pixel coordinates."""
        ts = self.LOCAL_TILE_SIZE
        return (
            self.game.player.local_x * ts + ts // 2,
            self.game.player.local_y * ts + ts // 2,
        )

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """Draw the local map onto *surface*."""
        lm = self.current_local_map()
        if lm is None:
            return

        ts = self.LOCAL_TILE_SIZE
        sw, sh = surface.get_size()

        # Determine visible tile range
        tx_start = max(0, int(cam_x // ts) - 1)
        tx_end = min(lm.width, int((cam_x + sw) // ts) + 2)
        ty_start = max(0, int(cam_y // ts) - 1)
        ty_end = min(lm.height, int((cam_y + sh) // ts) + 2)

        # Draw terrain
        for ty in range(ty_start, ty_end):
            for tx in range(tx_start, tx_end):
                sx = tx * ts - cam_x
                sy = ty * ts - cam_y
                terrain_char = lm.terrain[ty][tx]
                color = LOCAL_TERRAIN_COLORS.get(terrain_char, COLOR_LOCAL_FLOOR)
                pygame.draw.rect(surface, color, (sx, sy, ts, ts))
                # Grid lines
                grid_color = (color[0] // 4, color[1] // 4, color[2] // 4)
                pygame.draw.rect(surface, grid_color, (sx, sy, ts, ts), 1)

        # Draw objects with full footprint rendering
        for obj in lm.objects:
            # Check if any part of the object is visible
            ox_end = obj.x + obj.width
            oy_end = obj.y + obj.height
            if ox_end <= tx_start or obj.x >= tx_end or oy_end <= ty_start or obj.y >= ty_end:
                continue

            sx = obj.x * ts - cam_x
            sy = obj.y * ts - cam_y
            fw = obj.width * ts
            fh = obj.height * ts

            if obj.blocking:
                # Darker overlay for blocking objects — full footprint
                obj_color = (COLOR_LOCAL_OBJECT[0] // 2,
                             COLOR_LOCAL_OBJECT[1] // 2,
                             COLOR_LOCAL_OBJECT[2] // 2)
                pygame.draw.rect(surface, obj_color, (sx + 2, sy + 2, fw - 4, fh - 4))
                # Draw subtle border around footprint
                border_color = (COLOR_LOCAL_OBJECT[0] // 3,
                                COLOR_LOCAL_OBJECT[1] // 3,
                                COLOR_LOCAL_OBJECT[2] // 3)
                pygame.draw.rect(surface, border_color, (sx + 1, sy + 1, fw - 2, fh - 2), 1)
            else:
                # Non-blocking: small marker at center of footprint
                cx = sx + fw // 2
                cy = sy + fh // 2
                pygame.draw.circle(surface, COLOR_LOCAL_OBJECT, (cx, cy), ts // 6)

            # Label: centered across the full footprint
            label = obj.name
            # Pick a font size that fits the footprint width
            font_size = 14
            font = pygame.font.SysFont(None, font_size)
            # Try smaller font if label is wider than footprint
            while font_size > 8:
                test = font.render(label, True, (200, 200, 200))
                if test.get_width() <= fw - 4:
                    break
                font_size -= 1
                font = pygame.font.SysFont(None, font_size)
            lbl = font.render(label, True, (200, 200, 200))
            # If still too wide, truncate with "..."
            if lbl.get_width() > fw - 4 and len(label) > 3:
                while len(label) > 3 and font_size > 8:
                    label = label[:-1]
                    lbl = font.render(label + "...", True, (200, 200, 200))
                    if lbl.get_width() <= fw - 4:
                        break
                else:
                    lbl = font.render(label[:3] + "...", True, (200, 200, 200))
            lbl_x = sx + (fw - lbl.get_width()) // 2
            lbl_y = sy + (fh - lbl.get_height()) // 2
            surface.blit(lbl, (lbl_x, lbl_y))

        # Draw exit markers
        for ep in lm.exits.values():
            if not (tx_start <= ep.x < tx_end and ty_start <= ep.y < ty_end):
                continue
            sx = ep.x * ts - cam_x
            sy = ep.y * ts - cam_y
            pygame.draw.rect(surface, COLOR_LOCAL_EXIT, (sx + 4, sy + 4, ts - 8, ts - 8))
            font = pygame.font.SysFont(None, 12)
            lbl = font.render("EXIT", True, (0, 0, 0))
            surface.blit(lbl, (sx + (ts - lbl.get_width()) // 2,
                               sy + (ts - lbl.get_height()) // 2))

        # Draw player
        px, py = self.player_pixel_pos()
        sx = px - cam_x
        sy = py - cam_y
        pygame.draw.circle(surface, COLOR_LOCAL_PLAYER, (int(sx), int(sy)), ts // 3)
        inner = ts // 6
        pygame.draw.circle(surface, (200, 255, 200), (int(sx), int(sy)), inner)

        # Draw NPCs at their local positions
        loc = self.game.current_location()
        if loc:
            for npc_id in loc.npcs:
                npc = self.game.world.npcs.get(npc_id)
                if npc is None or npc.hp <= 0:
                    continue
                if npc.local_x < 0 or npc.local_y < 0:
                    continue
                nx, ny = npc.local_x, npc.local_y
                if not (tx_start <= nx < tx_end and ty_start <= ny < ty_end):
                    continue
                nsx = nx * ts - cam_x + ts // 2
                nsy = ny * ts - cam_y + ts // 2
                # NPC circle (distinct color from player)
                pygame.draw.circle(surface, COLOR_NPC, (int(nsx), int(nsy)), ts // 3)
                # Name label above the NPC
                font = pygame.font.SysFont(None, 13)
                lbl = font.render(npc.name, True, (200, 200, 200))
                lbl_x = nsx - lbl.get_width() // 2
                lbl_y = nsy - ts // 3 - lbl.get_height() - 2
                surface.blit(lbl, (int(lbl_x), int(lbl_y)))
