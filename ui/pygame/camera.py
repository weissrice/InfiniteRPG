"""2D camera — follows player, respects world bounds, supports resize."""

from __future__ import annotations

from .constants import TILE_SIZE, WORLD_SCALE


class Camera:
    """A 2D camera that tracks the player in world-pixel space."""

    def __init__(self, view_width: int, view_height: int):
        self.view_width = view_width
        self.view_height = view_height
        # Camera top-left in world-pixel coordinates
        self.x: float = 0.0
        self.y: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, player_pixel_x: float, player_pixel_y: float,
               world_pixel_w: int, world_pixel_h: int) -> None:
        """Center on the player, clamped to world bounds."""
        self.x = player_pixel_x - self.view_width / 2
        self.y = player_pixel_y - self.view_height / 2
        self._clamp(world_pixel_w, world_pixel_h)

    def resize(self, w: int, h: int) -> None:
        self.view_width = w
        self.view_height = h

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        """World-pixel → screen-pixel."""
        return int(wx - self.x), int(wy - self.y)

    def screen_to_world(self, sx: int, sy: int) -> tuple[float, float]:
        """Screen-pixel → world-pixel."""
        return sx + self.x, sy + self.y

    def grid_to_screen(self, gx: int, gy: int) -> tuple[int, int]:
        """Grid-cell → screen-pixel (top-left corner of tile)."""
        px = gx * TILE_SIZE
        py = gy * TILE_SIZE
        return self.world_to_screen(px, py)

    def is_visible(self, gx: int, gy: int) -> bool:
        """Is this grid cell at least partially visible?"""
        sx, sy = self.grid_to_screen(gx, gy)
        return (-TILE_SIZE < sx < self.view_width and
                -TILE_SIZE < sy < self.view_height)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clamp(self, world_w: int, world_h: int) -> None:
        if self.view_width >= world_w:
            self.x = (world_w - self.view_width) / 2
        else:
            self.x = max(0, min(self.x, world_w - self.view_width))
        if self.view_height >= world_h:
            self.y = (world_h - self.view_height) / 2
        else:
            self.y = max(0, min(self.y, world_h - self.view_height))
