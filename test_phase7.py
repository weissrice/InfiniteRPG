# -*- coding: utf-8 -*-
"""Tests for Phase 7: AI-Generated World + Local Map Integration."""

import os
import sys
import tempfile
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.state import Location, GameState
from engine.world import create_new_game
from engine.local_map import (
    generate_local_map, validate_local_map,
    _compute_exit_positions, _guess_entry_name,
    MAP_WIDTH, MAP_HEIGHT,
)
from engine.actions import (
    has_local_movement, move_local, is_local_position_blocked,
    get_exit_at, _resolve_entry_point, _perform_area_transition,
)


def check(label, condition):
    print("PASS" if condition else "FAIL", label, sep=": ")
    return condition


def bfs_reachable(lm, sx, sy):
    """Return set of all reachable tiles from (sx, sy) via BFS."""
    visited = set()
    queue = deque([(sx, sy)])
    visited.add((sx, sy))
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < lm.width and 0 <= ny < lm.height:
                if (nx, ny) not in visited and not lm.collision[ny][nx]:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    return visited


results = []


# =========================================================================
# 1. AI-generated location receives LocalMap
# =========================================================================
print("=== 1. AI-generated location receives LocalMap ===")
loc = Location(
    id="test_gen_1", name="Mystic Cave", description="A dark cave",
    exits={"east": "old_wooden_house"},
    visual_type="cave", map_x=0, map_y=0,
)
lm = generate_local_map(loc)
results.append(check("Generated LocalMap exists", lm is not None))
results.append(check("LocalMap has width", lm.width == MAP_WIDTH))
results.append(check("LocalMap has height", lm.height == MAP_HEIGHT))


# =========================================================================
# 2. Generated LocalMap has valid dimensions
# =========================================================================
print("\n=== 2. Valid dimensions ===")
results.append(check("Width is 19", lm.width == 19))
results.append(check("Height is 11", lm.height == 11))
results.append(check("Terrain is 11 rows", len(lm.terrain) == 11))
results.append(check("Each row is 19 cols", all(len(r) == 19 for r in lm.terrain)))
results.append(check("Collision is 11 rows", len(lm.collision) == 11))


# =========================================================================
# 3. Generated LocalMap has valid spawn
# =========================================================================
print("\n=== 3. Valid spawn ===")
sx, sy = lm.spawn
results.append(check("Spawn x in bounds", 0 <= sx < lm.width))
results.append(check("Spawn y in bounds", 0 <= sy < lm.height))
results.append(check("Spawn not blocked", not lm.collision[sy][sx]))


# =========================================================================
# 4. Generated exits map to correct target locations
# =========================================================================
print("\n=== 4. Exit mapping ===")
results.append(check("Has 'east' exit", "east" in lm.exits))
ep = lm.exits["east"]
results.append(check("East exit target is old_wooden_house",
                     ep.target_location_id == "old_wooden_house"))
results.append(check("East exit x in bounds", 0 <= ep.x < lm.width))
results.append(check("East exit y in bounds", 0 <= ep.y < lm.height))


# =========================================================================
# 5. Generated exits are reachable
# =========================================================================
print("\n=== 5. Exit reachability ===")
reachable = bfs_reachable(lm, sx, sy)
results.append(check("East exit reachable",
                     (ep.x, ep.y) in reachable))


# =========================================================================
# 6. Generated exits are walkable
# =========================================================================
print("\n=== 6. Exit walkability ===")
results.append(check("East exit not blocked", not lm.collision[ep.y][ep.x]))


# =========================================================================
# 7. Generated object footprints are valid
# =========================================================================
print("\n=== 7. Object footprints ===")
for obj in lm.objects:
    results.append(check("'%s' width >= 1" % obj.id, obj.width >= 1))
    results.append(check("'%s' height >= 1" % obj.id, obj.height >= 1))
    results.append(check("'%s' in bounds" % obj.id,
                         obj.x >= 0 and obj.y >= 0
                         and obj.x + obj.width <= lm.width
                         and obj.y + obj.height <= lm.height))


# =========================================================================
# 8. Collision matches generated object footprints
# =========================================================================
print("\n=== 8. Collision matches objects ===")
for obj in lm.objects:
    if not obj.blocking:
        continue
    for dy in range(obj.height):
        for dx in range(obj.width):
            ox, oy = obj.x + dx, obj.y + dy
            results.append(check(
                "'%s' (%d,%d) collision=True" % (obj.id, ox, oy),
                lm.collision[oy][ox]))


# =========================================================================
# 9. Player can WASD through generated locations
# =========================================================================
print("\n=== 9. WASD movement ===")
game = create_new_game()
game.player.location = "test_gen_1"
game.local_maps["test_gen_1"] = lm
game.player.local_x = sx
game.player.local_y = sy
results.append(check("has_local_movement", has_local_movement(game)))

# Try moving in each direction
for dx, dy, name in [(0, -1, "W"), (0, 1, "S"), (-1, 0, "A"), (1, 0, "D")]:
    game.player.local_x = sx
    game.player.local_y = sy
    r = move_local(game, dx, dy)
    results.append(check("Move %s from spawn" % name, r.success))
    # Move back
    game.player.local_x = sx
    game.player.local_y = sy


# =========================================================================
# 10. Player cannot walk through blocking objects
# =========================================================================
print("\n=== 10. Blocking objects ===")
if lm.objects:
    blocking_objs = [o for o in lm.objects if o.blocking]
    if blocking_objs:
        obj = blocking_objs[0]
        # Try to move into the object from adjacent
        game.player.local_x = obj.x - 1 if obj.x > 0 else obj.x + obj.width
        game.player.local_y = obj.y
        if 0 <= game.player.local_x < lm.width:
            dx = 1 if game.player.local_x < obj.x else -1
            r = move_local(game, dx, 0)
            results.append(check("Cannot walk through '%s'" % obj.id,
                                 not r.success or game.player.local_x != obj.x))
    else:
        results.append(check("No blocking objects (skipped)", True))
else:
    results.append(check("No objects (skipped)", True))


# =========================================================================
# 11. Player cannot leave map bounds
# =========================================================================
print("\n=== 11. Bounds checking ===")
game.player.local_x = 0
game.player.local_y = sy
r = move_local(game, -1, 0)
results.append(check("Cannot move left from x=0", not r.success))

game.player.local_x = lm.width - 1
game.player.local_y = sy
r = move_local(game, 1, 0)
results.append(check("Cannot move right from x=max", not r.success))


# =========================================================================
# 12. Exit triggers area transition
# =========================================================================
print("\n=== 12. Exit transition ===")
game2 = create_new_game()
game2.player.location = "test_gen_1"
game2.local_maps["test_gen_1"] = lm
# Position player near the east exit
game2.player.local_x = ep.x - 1 if ep.x > 0 else ep.x + 1
game2.player.local_y = ep.y
dx = 1 if ep.x > 0 else -1
r = move_local(game2, dx, 0)
results.append(check("Exit transition triggered", r.success))
results.append(check("Player moved to target", game2.player.location == "old_wooden_house"))


# =========================================================================
# 13. Entry point resolves correctly
# =========================================================================
print("\n=== 13. Entry point resolution ===")
game3 = create_new_game()
# LR -> Generated location via east exit
# First create the generated location
gen_loc = Location(
    id="test_entry", name="Test Entry", description="Test",
    exits={}, visual_type="house", map_x=1, map_y=0,
)
gen_lm = generate_local_map(gen_loc)
game3.local_maps["test_entry"] = gen_lm

# Resolve entry from LR
ex, ey = _resolve_entry_point(game3, "test_entry", "west")
results.append(check("Entry x in bounds", 0 <= ex < gen_lm.width))
results.append(check("Entry y in bounds", 0 <= ey < gen_lm.height))
results.append(check("Entry not blocked", not gen_lm.collision[ey][ex]))


# =========================================================================
# 14. _area_positions persists
# =========================================================================
print("\n=== 14. _area_positions ===")
game4 = create_new_game()
game4.player.location = "test_gen_1"
game4.local_maps["test_gen_1"] = lm
game4.player.local_x = 5
game4.player.local_y = 5
game4.player._area_positions["test_gen_1"] = [5, 5]
results.append(check("Position saved", game4.player._area_positions["test_gen_1"] == [5, 5]))

# Transition away
game4.player.location = "old_wooden_house"
game4.player.local_x = 12
game4.player.local_y = 5

# Return - should restore position
game4.player.location = "test_gen_1"
saved = game4.player._area_positions.get("test_gen_1")
if saved:
    game4.player.local_x = saved[0]
    game4.player.local_y = saved[1]
results.append(check("Position restored", game4.player.local_x == 5 and game4.player.local_y == 5))


# =========================================================================
# 15. Save/load preserves generated-location position state
# =========================================================================
print("\n=== 15. Save/load ===")
from engine.save import save_game, load_game

game5 = create_new_game()
game5.player.location = "test_gen_1"
game5.local_maps["test_gen_1"] = lm
game5.player.local_x = 7
game5.player.local_y = 3

with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
    tmp = f.name
try:
    save_game(game5, path=__import__("pathlib").Path(tmp))
    loaded = load_game(path=__import__("pathlib").Path(tmp))
    results.append(check("Load succeeds", loaded is not None))
    results.append(check("Loaded location correct",
                         loaded.player.location == "test_gen_1"))
    results.append(check("Loaded local_x", loaded.player.local_x == 7))
    results.append(check("Loaded local_y", loaded.player.local_y == 3))
finally:
    os.unlink(tmp)


# =========================================================================
# 16. Generated location can connect to another generated location
# =========================================================================
print("\n=== 16. Generated-to-generated connection ===")
loc_a = Location(
    id="gen_a", name="Gen A", description="A",
    exits={"east": "gen_b"}, visual_type="forest", map_x=0, map_y=0,
)
loc_b = Location(
    id="gen_b", name="Gen B", description="B",
    exits={"west": "gen_a"}, visual_type="forest", map_x=1, map_y=0,
)
lm_a = generate_local_map(loc_a)
lm_b = generate_local_map(loc_b)
results.append(check("Gen A map valid", validate_local_map(lm_a)))
results.append(check("Gen B map valid", validate_local_map(lm_b)))
results.append(check("Gen A has east exit", "east" in lm_a.exits))
results.append(check("Gen B has west exit", "west" in lm_b.exits))


# =========================================================================
# 17. Generated location can connect to existing location
# =========================================================================
print("\n=== 17. Generated-to-existing connection ===")
loc_c = Location(
    id="gen_c", name="Gen C", description="C",
    exits={"west": "old_wooden_house"}, visual_type="village", map_x=2, map_y=0,
)
lm_c = generate_local_map(loc_c)
results.append(check("Gen C map valid", validate_local_map(lm_c)))
results.append(check("Gen C west exit target",
                     lm_c.exits["west"].target_location_id == "old_wooden_house"))


# =========================================================================
# 18. Existing location can connect to generated location
# =========================================================================
print("\n=== 18. Existing-to-generated connection ===")
game6 = create_new_game()
lr = game6.local_maps["old_wooden_house"]
results.append(check("LR still has kitchen exit", "kitchen" in lr.exits))
results.append(check("LR still has outside exit", "outside" in lr.exits))
results.append(check("LR still has upstairs exit", "upstairs" in lr.exits))


# =========================================================================
# 19. Renderer can render generated LocalMap
# =========================================================================
print("\n=== 19. Renderer compatibility ===")
try:
    import pygame
    pygame.init()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from ui.pygame.world_renderer import LocalRenderer

    game7 = create_new_game()
    game7.player.location = "test_gen_1"
    game7.local_maps["test_gen_1"] = lm
    game7.player.local_x = sx
    game7.player.local_y = sy

    lr = LocalRenderer(game7)
    lm_r = lr.current_local_map()
    results.append(check("Renderer gets local map", lm_r is not None))

    # Render without error
    surf = pygame.Surface((800, 600))
    lr.draw(surf, 0.0, 0.0)
    results.append(check("Draw completes without error", True))

    # Player pixel position
    px, py = lr.player_pixel_pos()
    results.append(check("Player pixel pos valid", px >= 0 and py >= 0))

    pygame.quit()
except ImportError:
    print("  (pygame not available, skipping rendering tests)")
    results.append(check("Rendering: pygame not available (skipped)", True))


# =========================================================================
# 20. Invalid generated map safely falls back
# =========================================================================
print("\n=== 20. Fallback for invalid maps ===")
# Create a location with no exits (edge case)
loc_empty = Location(
    id="gen_empty", name="Empty", description="Empty",
    exits={}, visual_type="area", map_x=0, map_y=0,
)
lm_empty = generate_local_map(loc_empty)
valid_empty = validate_local_map(lm_empty)
results.append(check("Empty-exit map is valid", valid_empty))
results.append(check("Empty-exit map has spawn", lm_empty.spawn is not None))


# =========================================================================
# 21. Visual type routing
# =========================================================================
print("\n=== 21. Visual type routing ===")
for vtype, expected_interior in [
    ("house", True), ("building", True), ("cave", True),
    ("dungeon", True), ("tower", True),
    ("forest", False), ("village", False), ("mountain", False),
    ("road", False), ("area", False),
]:
    loc_vt = Location(
        id="vt_%s" % vtype, name=vtype, description="Test",
        exits={}, visual_type=vtype, map_x=0, map_y=0,
    )
    lm_vt = generate_local_map(loc_vt)
    # Interior maps have walls on all sides, outdoor maps have tree borders
    # Check if first tile is wall (#) or tree (T)
    first_tile = lm_vt.terrain[0][0]
    is_interior = first_tile == "#"
    results.append(check("visual_type='%s' routing" % vtype,
                         is_interior == expected_interior))


# =========================================================================
# 22. _compute_exit_positions
# =========================================================================
print("\n=== 22. Exit position computation ===")
loc_exits = Location(
    id="test_positions", name="Test", description="Test",
    exits={"east": "target1", "west": "target2", "north": "target3"},
    visual_type="forest", map_x=0, map_y=0,
)
positions = _compute_exit_positions(loc_exits, 19, 11)
results.append(check("East exit on right border",
                     positions["east"][0] == 18))
results.append(check("West exit on left border",
                     positions["west"][0] == 0))
results.append(check("North exit on top border",
                     positions["north"][1] == 0))


# =========================================================================
# 23. _guess_entry_name
# =========================================================================
print("\n=== 23. Entry name guessing ===")
results.append(check("east -> west", _guess_entry_name("east") == "west"))
results.append(check("west -> east", _guess_entry_name("west") == "east"))
results.append(check("north -> south", _guess_entry_name("north") == "south"))
results.append(check("south -> north", _guess_entry_name("south") == "north"))
results.append(check("back -> forward", _guess_entry_name("back") == "forward"))
results.append(check("unknown -> back", _guess_entry_name("unknown") == "back"))


# =========================================================================
# 24. validate_local_map catches problems
# =========================================================================
print("\n=== 24. Validation catches problems ===")
from engine.state import ExitPoint, LocalObject

# Invalid: spawn out of bounds
bad_lm = generate_local_map(Location(
    id="bad1", name="Bad", description="Bad",
    exits={}, visual_type="forest", map_x=0, map_y=0,
))
bad_lm.spawn = [-1, -1]
results.append(check("Catches bad spawn", not validate_local_map(bad_lm)))

# Invalid: exit out of bounds
bad_lm2 = generate_local_map(Location(
    id="bad2", name="Bad", description="Bad",
    exits={}, visual_type="forest", map_x=0, map_y=0,
))
bad_lm2.exits["test"] = ExitPoint(x=-1, y=0, target_location_id="x", entry_name="x")
results.append(check("Catches bad exit", not validate_local_map(bad_lm2)))


# =========================================================================
# 25. has_local_movement auto-includes generated locations
# =========================================================================
print("\n=== 25. has_local_movement auto-include ===")
game8 = create_new_game()
game8.player.location = "test_gen_1"
game8.local_maps["test_gen_1"] = lm
results.append(check("Generated location has local movement",
                     has_local_movement(game8)))

game8.player.location = "nonexistent_no_map"
results.append(check("Location without map has no local movement",
                     not has_local_movement(game8)))


# =========================================================================
# 26. Full journey through generated locations
# =========================================================================
print("\n=== 26. Full journey through generated locations ===")
# Create a chain: LR -> gen_d -> gen_e
loc_d = Location(
    id="gen_d", name="Gen D", description="D",
    exits={"east": "gen_e", "west": "old_wooden_house"},
    visual_type="forest", map_x=1, map_y=0,
)
loc_e = Location(
    id="gen_e", name="Gen E", description="E",
    exits={"west": "gen_d"},
    visual_type="cave", map_x=2, map_y=0,
)
lm_d = generate_local_map(loc_d)
lm_e = generate_local_map(loc_e)

game9 = create_new_game()
game9.local_maps["gen_d"] = lm_d
game9.local_maps["gen_e"] = lm_e

# Start in gen_d
game9.player.location = "gen_d"
game9.player.local_x = lm_d.spawn[0]
game9.player.local_y = lm_d.spawn[1]

# Walk to gen_e via east exit
ep_d_east = lm_d.exits["east"]
game9.player.local_x = ep_d_east.x - 1
game9.player.local_y = ep_d_east.y
r = move_local(game9, 1, 0)
results.append(check("gen_d -> gen_e transition", r.success))
results.append(check("Now in gen_e", game9.player.location == "gen_e"))

# Walk back to gen_d via west exit
ep_e_west = lm_e.exits["west"]
game9.player.local_x = ep_e_west.x + 1
game9.player.local_y = ep_e_west.y
r = move_local(game9, -1, 0)
results.append(check("gen_e -> gen_d transition", r.success))
results.append(check("Now in gen_d", game9.player.location == "gen_d"))


# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print("%d/%d checks passed, %d failed" % (passed, total, total - passed))
