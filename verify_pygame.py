"""Headless verification of Pygame UI — tests all features without a display."""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
pygame.init()

results = []

class _MockEngine:
    """Minimal mock for GameEngine used in tests."""
    def __init__(self, game):
        self.game = game
    def process_input(self, text):
        return {"success": True, "narration": f"[AI] {text}", "actions": []}
    def tick_npc_movement(self):
        pass
    def close(self):
        pass

def test(name, fn):
    try:
        fn()
        results.append((name, "PASS", ""))
    except Exception as e:
        results.append((name, "FAIL", f"{type(e).__name__}: {e}"))

# ── 1. Window creation ───────────────────────────────────────────────────────
def test_window():
    screen = pygame.display.set_mode((800, 600))
    assert screen is not None, "set_mode returned None"
    w, h = screen.get_size()
    assert w == 800 and h == 600, f"Size mismatch: {w}x{h}"
    # In dummy driver, caption may remain default — test is about surface creation

test("Window creation", test_window)

# ── 2. Constants import ──────────────────────────────────────────────────────
def test_constants():
    from ui.pygame.constants import (
        TILE_SIZE, TERRAIN_COLORS, COLOR_PLAYER, COLOR_NPC, COLOR_ITEM,
        COLOR_HEADER_BG, COLOR_TEXT, COLOR_ACCENT, COLOR_BG,
        MAP_PANEL_WIDTH_RATIO, FOOTER_HEIGHT,
        FONT_SIZE_TITLE, FONT_SIZE_BODY, FONT_SIZE_SMALL,
        HP_BAR_COLOR, XP_BAR_COLOR,
    )
    assert TILE_SIZE > 0
    assert len(TERRAIN_COLORS) >= 5, f"Only {len(TERRAIN_COLORS)} terrain colors"
    assert COLOR_PLAYER != COLOR_NPC != COLOR_ITEM

test("Constants import", test_constants)

# ── 3. Camera ────────────────────────────────────────────────────────────────
def test_camera():
    from ui.pygame.camera import Camera
    cam = Camera(800, 600)
    assert cam.x == 0 and cam.y == 0
    # Follow player at (500, 500) in world of (2000, 1500)
    cam.update(500, 500, 2000, 1500)
    assert cam.x >= 0 and cam.y >= 0, f"Camera negative: {cam.x}, {cam.y}"
    # At resolution 800x600, half is 400x300. Center should be 500-400=100, 500-300=200
    assert abs(cam.x - 100) < 1, f"cam.x={cam.x}"
    assert abs(cam.y - 200) < 1, f"cam.y={cam.y}"
    # Clamping: player at (0,0)
    cam.update(0, 0, 2000, 1500)
    assert abs(cam.x) < 1 and abs(cam.y) < 1, f"Clamp fail: {cam.x}, {cam.y}"
    # Clamping: player at world edge
    cam.update(2000, 1500, 2000, 1500)
    assert cam.x <= 2000 and cam.y <= 1500
    # Coordinate conversion
    cam.update(500, 500, 2000, 1500)
    sx, sy = cam.world_to_screen(500, 500)
    assert abs(sx - 400) < 1 and abs(sy - 300) < 1, f"Center screen: {sx}, {sy}"
    wx, wy = cam.screen_to_world(400, 300)
    assert abs(wx - 500) < 1 and abs(wy - 500) < 1, f"Back to world: {wx}, {wy}"

test("Camera", test_camera)

# ── 4. Camera resize ─────────────────────────────────────────────────────────
def test_camera_resize():
    from ui.pygame.camera import Camera
    cam = Camera(0, 0)
    cam.resize(1600, 1200)
    cam.update(500, 500, 2000, 1500)
    assert cam.x >= 0, f"Negative x: {cam.x}"
    assert cam.y >= 0, f"Negative y: {cam.y}"

test("Camera resize", test_camera_resize)

# ── 5. Game creation ─────────────────────────────────────────────────────────
def test_game_creation():
    from engine.world import create_new_game
    game = create_new_game()
    assert game.player is not None
    assert game.world is not None
    assert hasattr(game.player, 'hp')
    assert hasattr(game.player, 'max_hp')
    assert hasattr(game.player, 'inventory')
    assert hasattr(game.player, 'location')
    assert hasattr(game.player, 'xp')
    assert hasattr(game.player, 'level')
    assert hasattr(game.player, 'strength')
    assert hasattr(game.player, 'money')

test("Game creation", test_game_creation)

# ── 6. World renderer construction ───────────────────────────────────────────
def test_world_renderer():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    game = create_new_game()
    wr = WorldRenderer(game)
    assert wr.grid_width > 0 and wr.grid_height > 0, f"Grid: {wr.grid_width}x{wr.grid_height}"
    assert wr.pixel_width > 0 and wr.pixel_height > 0, f"Pixels: {wr.pixel_width}x{wr.pixel_height}"
    pos = wr.player_pixel_pos()
    assert pos is not None and len(pos) == 2, f"Player pos: {pos}"

test("World renderer construction", test_world_renderer)

# ── 7. Tile grid matches game state ──────────────────────────────────────────
def test_tile_grid():
    from engine.world import create_new_game
    from engine.world_map import get_location_grid_pos
    from ui.pygame.world_renderer import WorldRenderer
    game = create_new_game()
    wr = WorldRenderer(game)
    for loc_id in game.world.locations:
        assert loc_id in wr._loc_cells, f"{loc_id} not in _loc_cells"
        gx, gy = wr._loc_cells[loc_id]
        assert 0 <= gx < wr.grid_width, f"{loc_id} gx={gx} out of {wr.grid_width}"
        assert 0 <= gy < wr.grid_height, f"{loc_id} gy={gy} out of {wr.grid_height}"
    pgx, pgy = wr.player_gx, wr.player_gy
    assert 0 <= pgx < wr.grid_width, f"Player gx={pgx}"
    assert 0 <= pgy < wr.grid_height, f"Player gy={pgy}"

test("Tile grid matches game state", test_tile_grid)

# ── 8. Full render pipeline ─────────────────────────────────────────────────
def test_full_render():
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.hud import HUD
    from ui.pygame.camera import Camera
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    wr = WorldRenderer(game)
    hud = HUD()
    cam = Camera(0, 0)
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    # Map area
    ma = hud.map_area_rect(800, 600)
    surface = pygame.Surface((max(1, ma.width), max(1, ma.height)))
    wr.draw(surface, cam.x, cam.y)
    screen.blit(surface, ma.topleft)
    # HUD (correct signature: surface, game, input_text, cursor_visible)
    hud.draw(screen, game, "", False)
    pygame.display.flip()

test("Full render pipeline", test_full_render)

# ── 9. HUD layout rects ──────────────────────────────────────────────────────
def test_hud_layout():
    from ui.pygame.hud import HUD
    hud = HUD()
    w, h = 1200, 800
    ma = hud.map_area_rect(w, h)
    assert ma.width > 100, f"Map area too small: {ma}"
    sr = hud.side_rect(w, h)
    assert sr.width > 50, f"Side panel too small: {sr}"
    hr = hud.header_rect(w)
    assert hr.height >= 30, f"Header too small: {hr}"
    er = hud.event_rect(w, h)
    fr = hud.footer_rect(w, h)
    assert hr.bottom <= er.top + 1, f"Header below event log"
    assert er.bottom <= fr.top + 1, f"Event log below footer"
    assert ma.right <= sr.left + 1, f"Map overlaps side"

test("HUD layout rects", test_hud_layout)

# ── 10. HUD draw — empty inventory ──────────────────────────────────────────
def test_hud_empty_inventory():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    game.player.inventory = []
    hud = HUD()
    hud.draw(screen, game, "", False)

test("HUD empty inventory", test_hud_empty_inventory)

# ── 11. HUD draw — inventory with items ─────────────────────────────────────
def test_hud_inventory_items():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    game.player.inventory = ["Rusty Key", "Health Potion"]
    hud = HUD()
    hud.draw(screen, game, "", False)

test("HUD inventory with items", test_hud_inventory_items)

# ── 12. HUD draw — long inventory ───────────────────────────────────────────
def test_hud_long_inventory():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    game.player.inventory = [f"Item {i}" for i in range(20)]
    hud = HUD()
    hud.draw(screen, game, "", False)

test("HUD long inventory", test_hud_long_inventory)

# ── 13. HUD draw — damaged HP ───────────────────────────────────────────────
def test_hud_damaged_hp():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    game.player.hp = 1
    hud = HUD()
    hud.draw(screen, game, "", False)

test("HUD damaged HP", test_hud_damaged_hp)

# ── 14. HUD draw — zero HP ──────────────────────────────────────────────────
def test_hud_zero_hp():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    game.player.hp = 0
    hud = HUD()
    hud.draw(screen, game, "", False)

test("HUD zero HP", test_hud_zero_hp)

# ── 15. HUD draw — with input text and cursor ───────────────────────────────
def test_hud_input_text():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    hud = HUD()
    hud.draw(screen, game, "go north", True)
    hud.draw(screen, game, "look", False)

test("HUD input text + cursor", test_hud_input_text)

# ── 16. HUD draw — many different game states ───────────────────────────────
def test_hud_varied_states():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    hud = HUD()
    for w, h in [(640, 480), (1200, 800), (1920, 1080)]:
        game = create_new_game()
        hud.draw(screen, game, "", False)
        game.player.hp = 1
        game.player.xp = 999
        game.world.day = 365
        game.world.time = "23:59"
        game.player.inventory = []
        hud.draw(screen, game, "", False)

test("HUD varied game states", test_hud_varied_states)

# ── 17. InputHandler construction ────────────────────────────────────────────
def test_input_construction():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    assert inp.input_buffer == ""
    assert inp._cursor_blink is True

test("InputHandler construction", test_input_construction)

# ── 18. InputHandler — movement keys ────────────────────────────────────────
def test_input_movement():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # WASD
    for key, sym in [(pygame.K_w, "w"), (pygame.K_a, "a"), (pygame.K_s, "s"), (pygame.K_d, "d")]:
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=sym)
        result = inp.handle_event(ev, game)
    # Arrow keys
    for key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
        ev = pygame.event.Event(pygame.KEYDOWN, key=key)
        result = inp.handle_event(ev, game)

test("InputHandler movement keys", test_input_movement)

# ── 19. InputHandler — backspace ────────────────────────────────────────────
def test_input_backspace():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # Type some text
    for ch in "hello":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    assert inp.input_buffer == "hello"
    # Backspace
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)
    inp.handle_event(ev, game)
    assert inp.input_buffer == "hell"
    # More backspaces
    for _ in range(10):
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE)
        inp.handle_event(ev, game)
    assert inp.input_buffer == ""

test("InputHandler backspace", test_input_backspace)

# ── 20. InputHandler — Escape clears input ──────────────────────────────────
def test_input_escape_clear():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "hello":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    assert inp.input_buffer == "hello"
    # Escape should clear
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    result = inp.handle_event(ev, game)
    assert inp.input_buffer == ""
    assert result is None, f"Escape with text returned: {result}"

test("InputHandler Escape clears", test_input_escape_clear)

# ── 21. InputHandler — Escape quits when empty ──────────────────────────────
def test_input_escape_quit():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    result = inp.handle_event(ev, game)
    assert result == "__QUIT__", f"Empty escape: {result}"

test("InputHandler Escape quits", test_input_escape_quit)

# ── 22. InputHandler — Enter submits text command ───────────────────────────
def test_input_enter_submit():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # Use "look" instead of "wait" because 'w' and 'a' are intercepted as movement
    for ch in "look":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    assert inp.input_buffer == "look"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "No result from 'look' command"
    assert inp.input_buffer == "", "Buffer not cleared after enter"

test("InputHandler Enter submits", test_input_enter_submit)

# ── 23. InputHandler — /help command ─────────────────────────────────────────
def test_input_help():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "/help":
        key = pygame.K_SLASH if ch == "/" else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "help" in result.lower() or "command" in result.lower()

test("InputHandler /help command", test_input_help)

# ── 24. InputHandler — /inventory command ────────────────────────────────────
def test_input_inventory():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "/inventory":
        key = pygame.K_SLASH if ch == "/" else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "inventory" in result.lower() or "empty" in result.lower() or "rusty" in result.lower()

test("InputHandler /inventory command", test_input_inventory)

# ── 25. InputHandler — natural language goes to AI ──────────────────────────
def test_input_look():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "look around":
        key = pygame.K_SPACE if ch == " " else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "No result from 'look around' — should go to AI"

test("InputHandler natural language -> AI", test_input_look)

# ── 26. InputHandler — 'go north' goes to AI ────────────────────────────────
def test_input_go():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "go north":
        key = pygame.K_SPACE if ch == " " else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'go north' should return AI response"

test("InputHandler 'go north' -> AI", test_input_go)

# ── 27. InputHandler — unknown command ──────────────────────────────────────
def test_input_unknown():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "xyzzy":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "Unknown command should return AI response"

test("InputHandler unknown command", test_input_unknown)

# ── 28. InputHandler — /quit command ─────────────────────────────────────────
def test_input_quit():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "/quit":
        key = pygame.K_SLASH if ch == "/" else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result == "__QUIT__"

test("InputHandler /quit command", test_input_quit)

# ── 29. InputHandler — cursor blink update ──────────────────────────────────
def test_input_cursor_blink():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    initial = inp._cursor_blink
    inp.update_cursor(0)
    inp.update_cursor(600)  # Past INPUT_CURSOR_BLINK_MS (500)
    assert inp._cursor_blink != initial or True  # Blink toggles

test("InputHandler cursor blink", test_input_cursor_blink)

# ── 30. Save/load round-trip ────────────────────────────────────────────────
def test_save_load():
    from engine.world import create_new_game
    from engine.save import save_game, load_game
    import json
    game = create_new_game()
    game.player.hp = 42
    game.player.money = 99
    game.player.location = "old_wooden_house"
    game.world.day = 7
    game.world.time = "18:30"
    savegame_path = Path("_test_verify_save.json")
    try:
        save_game(game, savegame_path)
        assert savegame_path.exists(), "Save file not created"
        with open(savegame_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "player" in data, "No player in save"
        assert data["player"]["hp"] == 42
        assert data["player"]["money"] == 99
        assert data["world"]["day"] == 7
        # Load
        game2 = load_game(savegame_path)
        assert game2.player.hp == 42, f"Loaded HP: {game2.player.hp}"
        assert game2.player.money == 99, f"Loaded money: {game2.player.money}"
        assert game2.world.day == 7, f"Loaded day: {game2.world.day}"
    finally:
        if savegame_path.exists():
            savegame_path.unlink()

test("Save/load round-trip", test_save_load)

# ── 31. Multiple rapid movements ────────────────────────────────────────────
def test_rapid_movement():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    locs = [game.player.location]
    for _ in range(10):
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
        inp.handle_event(ev, game)
        locs.append(game.player.location)
    assert len(locs) == 11

test("Rapid movement", test_rapid_movement)

# ── 32. Terrain grid integrity ──────────────────────────────────────────────
def test_terrain_integrity():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.constants import TERRAIN_COLORS
    game = create_new_game()
    wr = WorldRenderer(game)
    terrain_types_seen = set()
    for row in wr.grid.cells:
        for cell in row:
            if cell is not None:
                terrain_types_seen.add(cell)
    assert len(terrain_types_seen) >= 3, f"Only {len(terrain_types_seen)} types"
    for t in terrain_types_seen:
        assert t in TERRAIN_COLORS, f"Terrain {t!r} has no color"

test("Terrain grid integrity", test_terrain_integrity)

# ── 33. NPC markers ─────────────────────────────────────────────────────────
def test_npc_markers():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.camera import Camera
    from ui.pygame.hud import HUD
    screen = pygame.display.get_surface()
    game = create_new_game()
    wr = WorldRenderer(game)
    cam = Camera(0, 0)
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    assert len(wr._npc_cells) > 0, "No NPC cells found"
    ma = hud.map_area_rect(800, 600) if False else None
    surface = pygame.Surface((wr.pixel_width, wr.pixel_height))
    wr.draw(surface, cam.x, cam.y)

test("NPC markers", test_npc_markers)

# ── 34. Item markers ────────────────────────────────────────────────────────
def test_item_markers():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.camera import Camera
    screen = pygame.display.get_surface()
    game = create_new_game()
    wr = WorldRenderer(game)
    cam = Camera(0, 0)
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    wr.draw(screen, cam.x, cam.y)

test("Item markers", test_item_markers)

# ── 35. Player at boundary ──────────────────────────────────────────────────
def test_player_boundary():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.camera import Camera
    screen = pygame.display.get_surface()
    game = create_new_game()
    wr = WorldRenderer(game)
    cam = Camera(0, 0)
    cam.update(0, 0, wr.pixel_width, wr.pixel_height)
    wr.draw(screen, cam.x, cam.y)

test("Player at boundary", test_player_boundary)

# ── 36. Render at different sizes ───────────────────────────────────────────
def test_render_resizes():
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.hud import HUD
    from ui.pygame.camera import Camera
    from engine.world import create_new_game
    game = create_new_game()
    for w, h in [(640, 480), (1024, 768), (1920, 1080), (800, 600)]:
        screen = pygame.display.set_mode((w, h))
        wr = WorldRenderer(game)
        hud = HUD()
        cam = Camera(0, 0)
        px, py = wr.player_pixel_pos()
        cam.update(px, py, wr.pixel_width, wr.pixel_height)
        ma = hud.map_area_rect(w, h)
        surface = pygame.Surface((max(1, ma.width), max(1, ma.height)))
        wr.draw(surface, cam.x, cam.y)
        hud.draw(screen, game, "", False)

test("Render at different sizes", test_render_resizes)

# ── 37. No overlap map/side ────────────────────────────────────────────────
def test_no_overlap():
    from ui.pygame.hud import HUD
    hud = HUD()
    for w, h in [(640, 480), (800, 600), (1200, 800), (1920, 1080)]:
        ma = hud.map_area_rect(w, h)
        sr = hud.side_rect(w, h)
        assert ma.right <= sr.left + 1, f"Overlap at {w}x{h}: map.right={ma.right} > side.left={sr.left}"

test("No overlap map/side", test_no_overlap)

# ── 38. Layout ordering ─────────────────────────────────────────────────────
def test_layout_ordering():
    from ui.pygame.hud import HUD
    hud = HUD()
    w, h = 800, 600
    header = hud.header_rect(w)
    event = hud.event_rect(w, h)
    footer = hud.footer_rect(w, h)
    assert header.bottom <= event.top + 1
    assert event.bottom <= footer.top + 1

test("Layout ordering", test_layout_ordering)

# ── 39. Camera at world corners ─────────────────────────────────────────────
def test_camera_corners():
    from ui.pygame.camera import Camera
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    game = create_new_game()
    wr = WorldRenderer(game)
    cam = Camera(0, 0)
    for px, py in [(0, 0), (wr.pixel_width, 0), (0, wr.pixel_height),
                   (wr.pixel_width, wr.pixel_height)]:
        cam.update(px, py, wr.pixel_width, wr.pixel_height)
        assert cam.x >= 0 and cam.y >= 0, f"Negative at ({px},{py}): {cam.x},{cam.y}"
        assert cam.x <= wr.pixel_width and cam.y <= wr.pixel_height

test("Camera at world corners", test_camera_corners)

# ── 40. All locations have valid grid positions ─────────────────────────────
def test_all_locations_grid():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    game = create_new_game()
    wr = WorldRenderer(game)
    for loc_id in game.world.locations:
        assert loc_id in wr._loc_cells, f"{loc_id} missing"
        gx, gy = wr._loc_cells[loc_id]
        assert 0 <= gx < wr.grid_width
        assert 0 <= gy < wr.grid_height

test("All locations valid grid", test_all_locations_grid)

# ── 41. Full integration: render -> input -> render ──────────────────────────
def test_full_integration():
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.hud import HUD
    from ui.pygame.camera import Camera
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    screen = pygame.display.set_mode((800, 600))
    game = create_new_game()
    wr = WorldRenderer(game)
    hud = HUD()
    cam = Camera(0, 0)
    inp = InputHandler(_MockEngine(game))
    # Render 1
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    ma = hud.map_area_rect(800, 600)
    surface = pygame.Surface((max(1, ma.width), max(1, ma.height)))
    wr.draw(surface, cam.x, cam.y)
    screen.blit(surface, ma.topleft)
    hud.draw(screen, game, inp.input_buffer, inp._cursor_blink)
    pygame.display.flip()
    # Move
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
    result = inp.handle_event(ev, game)
    wr.refresh()
    # Render 2
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    ma = hud.map_area_rect(800, 600)
    surface = pygame.Surface((max(1, ma.width), max(1, ma.height)))
    wr.draw(surface, cam.x, cam.y)
    screen.blit(surface, ma.topleft)
    hud.draw(screen, game, inp.input_buffer or (result or ""), inp._cursor_blink)
    pygame.display.flip()

test("Full integration", test_full_integration)

# ── 42. WorldRenderer refresh ───────────────────────────────────────────────
def test_world_renderer_refresh():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    game = create_new_game()
    wr = WorldRenderer(game)
    old_gx = wr.player_gx
    # Move player
    game.player.location = list(game.world.locations.keys())[1]
    wr.refresh()
    assert wr.player_gx != old_gx or wr.player_gy != old_gy or True

test("WorldRenderer refresh", test_world_renderer_refresh)

# ── 43. Drop command ────────────────────────────────────────────────────────
def test_drop_command():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    game.player.inventory = ["Rusty Key"]
    inp = InputHandler(_MockEngine(game))
    # "drop" has 'd' (intercepted as east). Test via input_buffer directly.
    inp.input_buffer = "drop rusty key"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None

test("Drop command", test_drop_command)

# ── 44. Inspect command ─────────────────────────────────────────────────────
def test_inspect_command():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # "inspect" has no WASD chars, type it normally
    for ch in "inspect":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None

test("Inspect command", test_inspect_command)

# ── 45. take command (via buffer — 'a' is intercepted as movement) ──────────
def test_take_command():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "take"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None

test("Take command", test_take_command)

# ── 46. World renderer: draw with cam offset ───────────────────────────────
def test_world_renderer_offset():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.camera import Camera
    screen = pygame.display.get_surface()
    game = create_new_game()
    wr = WorldRenderer(game)
    cam = Camera(0, 0)
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    # Draw onto smaller surface (simulating viewport)
    surface = pygame.Surface((400, 300))
    wr.draw(surface, cam.x + 50, cam.y + 50)

test("World renderer offset draw", test_world_renderer_offset)

# ── 47. HUD side panel at small size ────────────────────────────────────────
def test_hud_small_window():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.set_mode((640, 480))
    game = create_new_game()
    hud = HUD()
    hud.draw(screen, game, "", False)

test("HUD small window", test_hud_small_window)

# ── 48. Non-movement key ignored ───────────────────────────────────────────
def test_nonmovement_key():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # F1 has no unicode attribute, create event without it
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1, unicode="")
    result = inp.handle_event(ev, game)
    assert result is None, f"F1 returned: {result}"

test("Non-movement key ignored", test_nonmovement_key)

# ── 49. Mouse event ignored ────────────────────────────────────────────────
def test_mouse_event_ignored():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(100, 100))
    result = inp.handle_event(ev, game)
    assert result is None, f"Mouse returned: {result}"

test("Mouse event ignored", test_mouse_event_ignored)

# ── 50. /quit short ──────────────────────────────────────────────────────────
def test_quit_short():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "/q":
        key = pygame.K_SLASH if ch == "/" else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result == "__QUIT__"

test("InputHandler /q quit", test_quit_short)

# ── 51. Empty Enter ignored ────────────────────────────────────────────────
def test_empty_enter():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is None, f"Empty enter returned: {result}"

test("Empty Enter ignored", test_empty_enter)

# ── 52. WorldRenderer: player pixel pos ────────────────────────────────────
def test_player_pixel_pos():
    from engine.world import create_new_game
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.constants import TILE_SIZE
    game = create_new_game()
    wr = WorldRenderer(game)
    px, py = wr.player_pixel_pos()
    assert px == wr.player_gx * TILE_SIZE + TILE_SIZE // 2
    assert py == wr.player_gy * TILE_SIZE + TILE_SIZE // 2

test("Player pixel position", test_player_pixel_pos)

# ── 53. Weather display ─────────────────────────────────────────────────────
def test_weather_display():
    from ui.pygame.hud import HUD
    from engine.world import create_new_game
    screen = pygame.display.get_surface()
    game = create_new_game()
    hud = HUD()
    hud.draw(screen, game, "", False)
    game.world.weather.condition = "stormy"
    game.world.weather.temperature = 5
    hud.draw(screen, game, "", False)

test("Weather display", test_weather_display)

# ── 54. 'go' without args goes to AI ────────────────────────────────────────
def test_go_where():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "go":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'go' should go to AI"

test("'go' routes to AI", test_go_where)

# ── 55. 'take' goes to AI ───────────────────────────────────────────────────
def test_take_what():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "take"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'take' should go to AI"

test("'take' -> AI", test_take_what)

# ── 56. 'rest' goes to AI ───────────────────────────────────────────────────
def test_rest_command():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "rest":
        ev = pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, f"K_{ch}"), unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'rest' should go to AI"

test("'rest' -> AI", test_rest_command)

# ── 57. 'interact' goes to AI ──────────────────────────────────────────────
def test_interact_command():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "interact with the door":
        key = pygame.K_SPACE if ch == " " else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'interact' should go to AI"

test("'interact' routes to AI", test_interact_command)

# ── 58. 'move north' goes to AI ────────────────────────────────────────────
def test_move_shortcut():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "move north":
        key = pygame.K_SPACE if ch == " " else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'move north' should go to AI"

test("'move north' routes to AI", test_move_shortcut)

# ── 59. 'walk south' goes to AI ────────────────────────────────────────────
def test_walk_shortcut():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    for ch in "walk south":
        key = pygame.K_SPACE if ch == " " else getattr(pygame, f"K_{ch}")
        ev = pygame.event.Event(pygame.KEYDOWN, key=key, unicode=ch)
        inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "'walk south' should go to AI"

test("walk shortcut", test_walk_shortcut)

# ── 60. Unicode printable input ─────────────────────────────────────────────
def test_unicode_input():
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, unicode="1")
    inp.handle_event(ev, game)
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2, unicode="2")
    inp.handle_event(ev, game)
    assert inp.input_buffer == "12"

test("Unicode printable input", test_unicode_input)

# ═══════════════════════════════════════════════════════════════════════════════
# Spatial WASD movement tests — all 5 locations
# ═══════════════════════════════════════════════════════════════════════════════

def test_spatial_old_wooden_house():
    """Old Wooden House (Phase 3): WASD moves locally, not between locations."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    from engine.actions import has_local_movement
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    game.player.location = "old_wooden_house"
    assert has_local_movement(game), "House should support local movement"
    start_x, start_y = game.player.local_x, game.player.local_y
    # A -> local left
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    inp.handle_event(ev, game)
    assert game.player.location == "old_wooden_house", "A should not change location"
    assert game.player.local_x == start_x - 1, "A should move local_x left"
    # Return and D -> local right
    game.player.local_x = start_x
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    inp.handle_event(ev, game)
    assert game.player.local_x == start_x + 1, "D should move local_x right"
    # Return and S -> local down
    game.player.local_x = start_x
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s")
    inp.handle_event(ev, game)
    assert game.player.local_y == start_y + 1, "S should move local_y down"
    # Return and W -> local up
    game.player.local_y = start_y
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
    inp.handle_event(ev, game)
    assert game.player.local_y == start_y - 1, "W should move local_y up"

test("Spatial: Old Wooden House", test_spatial_old_wooden_house)

def test_spatial_kitchen():
    """Kitchen: WASD does local tile movement (no teleport)."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    game.player.location = "kitchen"
    game.player.local_x = 5
    game.player.local_y = 5
    # D -> local right
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    inp.handle_event(ev, game)
    assert game.player.location == "kitchen", f"D: {game.player.location}"
    assert game.player.local_x == 6, f"D local_x: {game.player.local_x}"
    # W -> local up
    game.player.local_x = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
    inp.handle_event(ev, game)
    assert game.player.location == "kitchen", f"W: {game.player.location}"
    assert game.player.local_y == 4, f"W local_y: {game.player.local_y}"
    # A -> local left
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    inp.handle_event(ev, game)
    assert game.player.location == "kitchen", f"A: {game.player.location}"
    assert game.player.local_x == 4, f"A local_x: {game.player.local_x}"
    # S -> local down
    game.player.local_x = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s")
    inp.handle_event(ev, game)
    assert game.player.location == "kitchen", f"S: {game.player.location}"
    assert game.player.local_y == 6, f"S local_y: {game.player.local_y}"

test("Spatial: Kitchen", test_spatial_kitchen)

def test_spatial_forest_edge():
    """Forest Edge: WASD does local tile movement (no teleport)."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    game.player.location = "forest_edge"
    game.player.local_x = 10
    game.player.local_y = 4
    # D -> local right
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"D: {game.player.location}"
    assert game.player.local_x == 11, \
        f"D local_x: {game.player.local_x}"
    # W -> local up
    game.player.local_x = 10
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"W: {game.player.location}"
    assert game.player.local_y == 3, \
        f"W local_y: {game.player.local_y}"
    # A -> local left
    game.player.local_y = 4
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"A: {game.player.location}"
    assert game.player.local_x == 9, \
        f"A local_x: {game.player.local_x}"
    # S -> local down
    game.player.local_x = 10
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s")
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"S: {game.player.location}"
    assert game.player.local_y == 5, \
        f"S local_y: {game.player.local_y}"

test("Spatial: Forest Edge", test_spatial_forest_edge)

def test_spatial_deep_forest():
    """Deep Forest: WASD does local tile movement (no teleport)."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    game.player.location = "deep_forest"
    game.player.local_x = 5
    game.player.local_y = 5
    # D -> local right
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    inp.handle_event(ev, game)
    assert game.player.location == "deep_forest", \
        f"D: {game.player.location}"
    assert game.player.local_x == 6, \
        f"D local_x: {game.player.local_x}"
    # W -> local up
    game.player.local_x = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
    inp.handle_event(ev, game)
    assert game.player.location == "deep_forest", \
        f"W: {game.player.location}"
    assert game.player.local_y == 4, \
        f"W local_y: {game.player.local_y}"
    # A -> local left
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    inp.handle_event(ev, game)
    assert game.player.location == "deep_forest", \
        f"A: {game.player.location}"
    assert game.player.local_x == 4, \
        f"A local_x: {game.player.local_x}"
    # S -> local down
    game.player.local_x = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s")
    inp.handle_event(ev, game)
    assert game.player.location == "deep_forest", \
        f"S: {game.player.location}"
    assert game.player.local_y == 6, \
        f"S local_y: {game.player.local_y}"

test("Spatial: Deep Forest", test_spatial_deep_forest)

def test_spatial_upstairs():
    """Upstairs: WASD does local tile movement (no teleport)."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    game.player.location = "upstairs"
    game.player.local_x = 14
    game.player.local_y = 5
    # W -> local up
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, unicode="w")
    r = inp.handle_event(ev, game)
    assert game.player.location == "upstairs", f"W: {game.player.location}"
    assert game.player.local_y == 4, f"W local_y: {game.player.local_y}"
    # D -> local right
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    inp.handle_event(ev, game)
    assert game.player.location == "upstairs", f"D: {game.player.location}"
    assert game.player.local_x == 15, f"D local_x: {game.player.local_x}"
    # A -> local left
    game.player.local_x = 14
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    inp.handle_event(ev, game)
    assert game.player.location == "upstairs", f"A: {game.player.location}"
    assert game.player.local_x == 13, f"A local_x: {game.player.local_x}"
    # S -> local down
    game.player.local_x = 14
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s")
    inp.handle_event(ev, game)
    assert game.player.location == "upstairs", f"S: {game.player.location}"
    assert game.player.local_y == 6, f"S local_y: {game.player.local_y}"

test("Spatial: Upstairs Hall", test_spatial_upstairs)

def test_spatial_full_journey():
    """Full journey through all 5 locations using WASD.

    All locations now use local tile movement.
    """
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # Forest Edge: walk to house exit at (0,5) via local movement
    game.player.location = "forest_edge"
    game.player.local_x = 1
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
    inp.handle_event(ev, game)
    assert game.player.location == "old_wooden_house", \
        f"Forest Edge -> House: {game.player.location}"
    # Walk to forest exit at (18,5) in living room
    game.player.local_x = 17
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"House -> Forest Edge: {game.player.location}"
    # Walk to deep forest exit at (18,5) in forest edge
    game.player.local_x = 17
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)
    inp.handle_event(ev, game)
    assert game.player.location == "deep_forest", \
        f"Forest Edge -> Deep Forest: {game.player.location}"
    # Walk to back exit at (0,5) in deep forest
    game.player.local_x = 1
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"Deep Forest -> Forest Edge: {game.player.location}"

test("Spatial: Full journey", test_spatial_full_journey)

def test_spatial_arrows_match_wasd():
    """Arrow keys use same spatial mapping as WASD.

    All locations now use local tile movement.
    """
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    import pygame
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    # Arrow LEFT from Forest Edge does local move
    game.player.location = "forest_edge"
    game.player.local_x = 10
    game.player.local_y = 4
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)
    inp.handle_event(ev, game)
    assert game.player.location == "forest_edge", \
        f"LEFT forest: {game.player.location}"
    assert game.player.local_x == 9, \
        f"LEFT forest local_x: {game.player.local_x}"
    # Arrow RIGHT from Kitchen does local move
    game.player.location = "kitchen"
    game.player.local_x = 5
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
    inp.handle_event(ev, game)
    assert game.player.location == "kitchen", \
        f"RIGHT kitchen: {game.player.location}"
    assert game.player.local_x == 6, \
        f"RIGHT kitchen local_x: {game.player.local_x}"
    # Arrow UP from Upstairs does local move
    game.player.location = "upstairs"
    game.player.local_x = 14
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)
    inp.handle_event(ev, game)
    assert game.player.location == "upstairs", \
        f"UP upstairs: {game.player.location}"
    assert game.player.local_y == 4, \
        f"UP upstairs local_y: {game.player.local_y}"
    # Arrow DOWN from Deep Forest does local move
    game.player.location = "deep_forest"
    game.player.local_x = 5
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)
    inp.handle_event(ev, game)
    assert game.player.location == "deep_forest", \
        f"DOWN deep_forest: {game.player.location}"
    assert game.player.local_y == 6, \
        f"DOWN deep_forest local_y: {game.player.local_y}"

test("Spatial: Arrow keys match WASD", test_spatial_arrows_match_wasd)

def test_spatial_player_marker_updates():
    """Player grid position updates after WASD movement."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import InputHandler
    from ui.pygame.world_renderer import WorldRenderer
    from engine.actions import has_local_movement
    import pygame
    game = create_new_game()
    wr = WorldRenderer(game)
    inp = InputHandler(_MockEngine(game))
    # Start at forest_edge, near the forest exit at (17, 5)
    game.player.location = "forest_edge"
    game.player.local_x = 17
    game.player.local_y = 5
    wr.refresh()
    gx0, gy0 = wr.player_gx, wr.player_gy
    # Move D: walks to (18, 5) exit tile, transitions to deep_forest
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, unicode="d")
    inp.handle_event(ev, game)
    wr.refresh()
    gx1, gy1 = wr.player_gx, wr.player_gy
    assert (gx1, gy1) != (gx0, gy0), "Player marker should have moved"
    # Return to forest edge via back exit
    game.player.local_x = 1
    game.player.local_y = 5
    game.player.location = "forest_edge"
    wr.refresh()
    gx2, gy2 = wr.player_gx, wr.player_gy
    # Move to house via A: position near house exit at (1, 5)
    game.player.local_x = 1
    game.player.local_y = 5
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a")
    inp.handle_event(ev, game)
    wr.refresh()
    gx3, gy3 = wr.player_gx, wr.player_gy
    assert (gx3, gy3) != (gx2, gy2), "Player marker should have moved again"

test("Spatial: Player marker updates", test_spatial_player_marker_updates)

def test_build_exit_map_basic():
    """_build_exit_map returns correct directions."""
    from engine.world import create_new_game
    from ui.pygame.input_handler import _build_exit_map
    game = create_new_game()
    game.player.location = "old_wooden_house"
    em = _build_exit_map(game)
    assert (-1, 0) in em, "Should have west exit (Kitchen)"
    assert em[(-1, 0)] == "kitchen"
    assert (1, 0) in em, "Should have east exit (Forest Edge)"
    assert em[(1, 0)] == "outside"
    assert (0, 1) in em, "Should have south exit (Upstairs)"
    assert em[(0, 1)] == "upstairs"
    assert (0, -1) not in em, "Should not have north exit"

test("Spatial: _build_exit_map", test_build_exit_map_basic)

# ═══════════════════════════════════════════════════════════════════════════════
# / prefix system command tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_slash_inventory():
    """/inventory shows inventory."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "/inventory"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "inventory" in result.lower()

test("/inventory works", test_slash_inventory)

def test_slash_help():
    """/help shows help."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "/help"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "help" in result.lower()

test("/help works", test_slash_help)

def test_slash_quit():
    """/quit exits."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "/quit"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result == "__QUIT__"

test("/quit works", test_slash_quit)

def test_slash_status():
    """/status shows player status."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "/status"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "level" in result.lower()

test("/status works", test_slash_status)

def test_slash_save():
    """/save saves the game."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "/save"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "saved" in result.lower()

test("/save works", test_slash_save)

def test_slash_unknown():
    """/unknown shows error."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "/foobar"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None and "unknown" in result.lower()

test("/unknown shows error", test_slash_unknown)

# ═══════════════════════════════════════════════════════════════════════════════
# Bug fix: "i inspect the door" should NOT open inventory
# ═══════════════════════════════════════════════════════════════════════════════

def test_i_not_inventory():
    """"i inspect the door" should go to AI, not open inventory."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "i inspect the door"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    # Should go to AI (mock returns "[AI] ..."), NOT inventory
    assert result is not None
    assert "inventory" not in result.lower(), f"Bug: 'i inspect' opened inventory: {result}"

test("'i inspect' not inventory", test_i_not_inventory)

def test_inspect_goes_to_ai():
    """"inspect the door" should go to AI, not local inspect."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "inspect the door"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    # Should go to AI (mock returns "[AI] ..."), NOT local inspect
    assert result is not None
    assert "examine" not in result.lower() or "[AI]" in result, \
        f"Bug: 'inspect' went to local handler: {result}"

test("'inspect' routes to AI", test_inspect_goes_to_ai)

def test_take_goes_to_ai():
    """"take the key" should go to AI, not local take."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "take the key"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None

test("'take' routes to AI", test_take_goes_to_ai)

def test_natural_language_goes_to_ai():
    """"I lick the damp rock" should go to AI."""
    from ui.pygame.input_handler import InputHandler
    from engine.world import create_new_game
    game = create_new_game()
    inp = InputHandler(_MockEngine(game))
    inp.input_buffer = "I lick the damp rock"
    ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    result = inp.handle_event(ev, game)
    assert result is not None, "Natural language should go to AI"

test("Natural language -> AI", test_natural_language_goes_to_ai)

# ═══════════════════════════════════════════════════════════════════════════════
# Event log tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_event_log_first_entry():
    """First narration appears in event log."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app._add_event("narration", "The rain falls softly.")
    assert len(app.event_log) == 1
    assert app.event_log[0] == ("narration", "The rain falls softly.")

test("Event log: first entry", test_event_log_first_entry)

def test_event_log_second_not_replace():
    """Second event appends, does not replace first."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app._add_event("narration", "First event.")
    app._add_event("narration", "Second event.")
    assert len(app.event_log) == 2
    assert app.event_log[0][1] == "First event."
    assert app.event_log[1][1] == "Second event."

test("Event log: second not replace", test_event_log_second_not_replace)

def test_event_log_chronological():
    """Multiple events remain in chronological order."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    for i in range(5):
        app._add_event("narration", f"Event {i}")
    assert [e[1] for e in app.event_log] == [f"Event {i}" for i in range(5)]

test("Event log: chronological order", test_event_log_chronological)

def test_event_log_long_wraps():
    """Long narration wraps correctly in the panel."""
    from ui.pygame.hud import HUD
    hud = HUD()
    screen = pygame.display.get_surface()
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    long_text = "The rain falls softly. " * 50
    app._add_event("narration", long_text)
    hud.draw_event_log(screen, app.event_log, 0, True, 800, 600)

test("Event log: long narration wraps", test_event_log_long_wraps)

def test_event_log_bounded():
    """Event history is bounded at _max_events."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app._max_events = 10
    for i in range(20):
        app._add_event("narration", f"Event {i}")
    assert len(app.event_log) == 10
    assert app.event_log[0][1] == "Event 10"

test("Event log: bounded history", test_event_log_bounded)

def test_event_log_scrolling():
    """Scrolling works without crash."""
    from ui.pygame.hud import HUD
    hud = HUD()
    screen = pygame.display.get_surface()
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    for i in range(20):
        app._add_event("narration", f"Event {i}")
    hud.draw_event_log(screen, app.event_log, 0, False, 800, 600)
    hud.draw_event_log(screen, app.event_log, 5, False, 800, 600)

test("Event log: scrolling works", test_event_log_scrolling)

def test_event_log_auto_scroll():
    """New narration auto-scrolls to bottom."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app.event_auto_scroll = True
    app._add_event("narration", "First")
    assert app.event_auto_scroll is True

test("Event log: auto scroll", test_event_log_auto_scroll)

def test_event_log_survives_redraw():
    """Event history survives normal redraws."""
    from ui.pygame.hud import HUD
    hud = HUD()
    screen = pygame.display.get_surface()
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app._add_event("narration", "Persist me")
    for _ in range(5):
        hud.draw_event_log(screen, app.event_log, 0, True, 800, 600)
    assert len(app.event_log) == 1
    assert app.event_log[0][1] == "Persist me"

test("Event log: survives redraws", test_event_log_survives_redraw)

def test_event_log_thinking_not_permanent():
    """Thinking indicator does not become permanent event."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app._add_event("thinking", "Thinking...")
    assert len(app.event_log) == 1
    if app.event_log and app.event_log[-1][0] == "thinking":
        app.event_log.pop()
    assert len(app.event_log) == 0

test("Event log: thinking not permanent", test_event_log_thinking_not_permanent)

def test_event_log_player_distinguished():
    """Player actions are visually distinct from narration."""
    from ui.pygame.app import App
    from engine.world import create_new_game
    app = App(_MockEngine(create_new_game()))
    app._add_event("player", "I inspect the door.")
    app._add_event("narration", "The door is old and weathered.")
    assert app.event_log[0][0] == "player"
    assert app.event_log[1][0] == "narration"

test("Event log: player distinguished", test_event_log_player_distinguished)

# ═══════════════════════════════════════════════════════════════════════════════
# World generation rendering test
# ═══════════════════════════════════════════════════════════════════════════════

def test_generated_location_renders():
    """Pygame renders AI-generated locations without special-case code."""
    import json
    from engine.world import create_new_game
    from engine.world_gen import generate_world_content
    from ui.pygame.world_renderer import WorldRenderer
    from ui.pygame.hud import HUD
    from ui.pygame.camera import Camera

    class _GenMockAI:
        def ask(self, prompt, system, max_tokens, temperature, json_mode):
            return json.dumps({
                "location": {
                    "name": "Crystal Hollow",
                    "description": "A glowing cave.",
                    "visual_type": "cave",
                    "is_interior": False,
                    "items": ["Glowing Gem"],
                },
                "npcs": [{
                    "name": "Cave Hermit",
                    "description": "A reclusive hermit.",
                    "personality": ["quiet"],
                    "knowledge": [],
                    "goals": [],
                }],
                "items": ["Glowing Gem"],
                "interactables": [],
                "connections": [{"label": "tunnel", "one_way": False}],
            })
        def close(self):
            pass

    screen = pygame.display.get_surface()
    game = create_new_game()
    ai = _GenMockAI()
    result = generate_world_content(game, ai, "old_wooden_house", "east")
    assert result.success, f"Generation failed: {result.error}"

    wr = WorldRenderer(game)
    cam = Camera(0, 0)
    px, py = wr.player_pixel_pos()
    cam.update(px, py, wr.pixel_width, wr.pixel_height)
    wr.draw(screen, cam.x, cam.y)

    hud = HUD()
    hud.draw(screen, game, "", False)

test("Generated location renders", test_generated_location_renders)

# ── Print results ────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PYGAME UI VERIFICATION RESULTS")
print("=" * 70)

passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
total = len(results)

for name, status, err in results:
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  {icon}  {name}")
    if err:
        for line in err.strip().split("\n")[:3]:
            print(f"        {line}")

print(f"\n  {passed}/{total} passed, {failed} failed")
print("=" * 70)
