# -*- coding: utf-8 -*-
"""Tests for Phase 2: Local map generation for existing locations."""

import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.world import create_new_game
from engine.state import GameState, LocalMap, LocalObject, ExitPoint
from engine.local_map import (
    generate_local_map, MAP_WIDTH, MAP_HEIGHT,
    _generate_living_room, _generate_kitchen, _generate_upstairs,
    _generate_forest_edge, _generate_deep_forest,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

EXPECTED_LOCATIONS = [
    "old_wooden_house",
    "kitchen",
    "upstairs",
    "forest_edge",
    "deep_forest",
]


# --- 1. Map existence ---
print("=== 1. Map existence ===")
game = create_new_game()

for loc_id in EXPECTED_LOCATIONS:
    results.append(check(f"{loc_id} has local_map", loc_id in game.local_maps))
    results.append(check(f"{loc_id} local_map is LocalMap",
                         isinstance(game.local_maps.get(loc_id), LocalMap)))

results.append(check("Total local maps = 5", len(game.local_maps) == 5))


# --- 2. Dimensions ---
print("\n=== 2. Dimensions ===")
for loc_id in EXPECTED_LOCATIONS:
    lm = game.local_maps[loc_id]
    results.append(check(f"{loc_id}: width == {MAP_WIDTH}", lm.width == MAP_WIDTH))
    results.append(check(f"{loc_id}: height == {MAP_HEIGHT}", lm.height == MAP_HEIGHT))
    results.append(check(f"{loc_id}: terrain rows == {MAP_HEIGHT}", len(lm.terrain) == MAP_HEIGHT))
    results.append(check(f"{loc_id}: terrain[0] cols == {MAP_WIDTH}", len(lm.terrain[0]) == MAP_WIDTH))
    results.append(check(f"{loc_id}: collision rows == {MAP_HEIGHT}", len(lm.collision) == MAP_HEIGHT))
    results.append(check(f"{loc_id}: collision[0] cols == {MAP_WIDTH}", len(lm.collision[0]) == MAP_WIDTH))


# --- 3. Collision: boundary tiles are blocked (except at exits) ---
print("\n=== 3. Collision: boundaries ===")
for loc_id in EXPECTED_LOCATIONS:
    lm = game.local_maps[loc_id]
    w, h = lm.width, lm.height

    # Collect exit positions for this location
    exit_positions = {(ep.x, ep.y) for ep in lm.exits.values()}

    # Top and bottom rows (excluding exit tiles)
    top_blocked = all(
        lm.collision[0][x] or (x, 0) in exit_positions
        for x in range(w)
    )
    bot_blocked = all(
        lm.collision[h - 1][x] or (x, h - 1) in exit_positions
        for x in range(w)
    )
    results.append(check(f"{loc_id}: top row blocked (excl exits)", top_blocked))
    results.append(check(f"{loc_id}: bottom row blocked (excl exits)", bot_blocked))

    # Left and right columns (excluding exit tiles)
    left_blocked = all(
        lm.collision[y][0] or (0, y) in exit_positions
        for y in range(h)
    )
    right_blocked = all(
        lm.collision[y][w - 1] or (w - 1, y) in exit_positions
        for y in range(h)
    )
    results.append(check(f"{loc_id}: left col blocked (excl exits)", left_blocked))
    results.append(check(f"{loc_id}: right col blocked (excl exits)", right_blocked))


# --- 4. Interior maps have walkable floor ---
print("\n=== 4. Interior walkable areas ===")
interior_ids = ["old_wooden_house", "kitchen", "upstairs"]
for loc_id in interior_ids:
    lm = game.local_maps[loc_id]
    # Interior maps should have walkable tiles in the open areas
    # Check a few known-open spots
    open_spot = not lm.collision[2][2] or not lm.collision[5][12] or not lm.collision[7][7]
    results.append(check(f"{loc_id}: has open walkable area", open_spot))

    # Count walkable tiles
    walkable = sum(1 for y in range(lm.height) for x in range(lm.width)
                   if not lm.collision[y][x])
    results.append(check(f"{loc_id}: has walkable tiles ({walkable})", walkable > 20))


# --- 5. Outdoor maps have trees ---
print("\n=== 5. Outdoor terrain ===")
outdoor_ids = ["forest_edge", "deep_forest"]
for loc_id in outdoor_ids:
    lm = game.local_maps[loc_id]
    tree_count = sum(1 for y in range(lm.height) for x in range(lm.width)
                     if lm.terrain[y][x] == "T")
    results.append(check(f"{loc_id}: has trees ({tree_count})", tree_count > 5))


# --- 6. Objects exist ---
print("\n=== 6. Objects ===")
results.append(check("Living Room has objects", len(game.local_maps["old_wooden_house"].objects) > 0))
results.append(check("Kitchen has objects", len(game.local_maps["kitchen"].objects) > 0))
results.append(check("Upstairs has objects", len(game.local_maps["upstairs"].objects) > 0))
results.append(check("Forest Edge has objects", len(game.local_maps["forest_edge"].objects) > 0))
results.append(check("Deep Forest has objects", len(game.local_maps["deep_forest"].objects) > 0))

# Verify objects have required fields
for loc_id in EXPECTED_LOCATIONS:
    lm = game.local_maps[loc_id]
    for obj in lm.objects:
        results.append(check(f"{loc_id}/{obj.id}: has name", obj.name != ""))
        results.append(check(f"{loc_id}/{obj.id}: tile is str", isinstance(obj.tile, str)))
        results.append(check(f"{loc_id}/{obj.id}: x in bounds", 0 <= obj.x < lm.width))
        results.append(check(f"{loc_id}/{obj.id}: y in bounds", 0 <= obj.y < lm.height))


# --- 7. Exits ---
print("\n=== 7. Exits ===")

# Living Room: kitchen, outside, upstairs
lr = game.local_maps["old_wooden_house"]
results.append(check("Living Room: 3 exits", len(lr.exits) == 3))
results.append(check("Living Room: has kitchen exit", "kitchen" in lr.exits))
results.append(check("Living Room: has outside exit", "outside" in lr.exits))
results.append(check("Living Room: has upstairs exit", "upstairs" in lr.exits))

if "kitchen" in lr.exits:
    ep = lr.exits["kitchen"]
    results.append(check("LR kitchen exit -> kitchen", ep.target_location_id == "kitchen"))
    results.append(check("LR kitchen exit in bounds", 0 <= ep.x < lr.width and 0 <= ep.y < lr.height))
    results.append(check("LR kitchen exit walkable", not lr.collision[ep.y][ep.x]))

if "outside" in lr.exits:
    ep = lr.exits["outside"]
    results.append(check("LR outside exit -> forest_edge", ep.target_location_id == "forest_edge"))
    results.append(check("LR outside exit in bounds", 0 <= ep.x < lr.width and 0 <= ep.y < lr.height))
    results.append(check("LR outside exit walkable", not lr.collision[ep.y][ep.x]))

if "upstairs" in lr.exits:
    ep = lr.exits["upstairs"]
    results.append(check("LR upstairs exit -> upstairs", ep.target_location_id == "upstairs"))
    results.append(check("LR upstairs exit in bounds", 0 <= ep.x < lr.width and 0 <= ep.y < lr.height))
    results.append(check("LR upstairs exit walkable", not lr.collision[ep.y][ep.x]))

# Kitchen: outside -> old_wooden_house
kt = game.local_maps["kitchen"]
results.append(check("Kitchen: 1 exit", len(kt.exits) == 1))
results.append(check("Kitchen: has outside exit", "outside" in kt.exits))
if "outside" in kt.exits:
    ep = kt.exits["outside"]
    results.append(check("Kitchen outside exit -> old_wooden_house", ep.target_location_id == "old_wooden_house"))
    results.append(check("Kitchen outside exit walkable", not kt.collision[ep.y][ep.x]))

# Upstairs: downstairs -> old_wooden_house
up = game.local_maps["upstairs"]
results.append(check("Upstairs: 1 exit", len(up.exits) == 1))
results.append(check("Upstairs: has downstairs exit", "downstairs" in up.exits))
if "downstairs" in up.exits:
    ep = up.exits["downstairs"]
    results.append(check("Upstairs downstairs exit -> old_wooden_house", ep.target_location_id == "old_wooden_house"))
    results.append(check("Upstairs downstairs exit walkable", not up.collision[ep.y][ep.x]))

# Forest Edge: house, forest
fe = game.local_maps["forest_edge"]
results.append(check("Forest Edge: 2 exits", len(fe.exits) == 2))
results.append(check("Forest Edge: has house exit", "house" in fe.exits))
results.append(check("Forest Edge: has forest exit", "forest" in fe.exits))
if "house" in fe.exits:
    ep = fe.exits["house"]
    results.append(check("FE house exit -> old_wooden_house", ep.target_location_id == "old_wooden_house"))
    results.append(check("FE house exit walkable", not fe.collision[ep.y][ep.x]))
if "forest" in fe.exits:
    ep = fe.exits["forest"]
    results.append(check("FE forest exit -> deep_forest", ep.target_location_id == "deep_forest"))
    results.append(check("FE forest exit walkable", not fe.collision[ep.y][ep.x]))

# Deep Forest: back -> forest_edge
df = game.local_maps["deep_forest"]
results.append(check("Deep Forest: 1 exit", len(df.exits) == 1))
results.append(check("Deep Forest: has back exit", "back" in df.exits))
if "back" in df.exits:
    ep = df.exits["back"]
    results.append(check("DF back exit -> forest_edge", ep.target_location_id == "forest_edge"))
    results.append(check("DF back exit walkable", not df.collision[ep.y][ep.x]))


# --- 8. World graph exits match local map exits ---
print("\n=== 8. World graph <-> local map exit consistency ===")
for loc_id in EXPECTED_LOCATIONS:
    loc = game.world.locations[loc_id]
    lm = game.local_maps[loc_id]

    for world_exit_name, target_id in loc.exits.items():
        results.append(check(
            f"{loc_id}: world exit '{world_exit_name}' has local exit",
            world_exit_name in lm.exits,
        ))
        if world_exit_name in lm.exits:
            ep = lm.exits[world_exit_name]
            results.append(check(
                f"{loc_id}: exit '{world_exit_name}' -> {target_id}",
                ep.target_location_id == target_id,
            ))


# --- 9. Spawn positions ---
print("\n=== 9. Spawn positions ===")
for loc_id in EXPECTED_LOCATIONS:
    lm = game.local_maps[loc_id]
    sx, sy = lm.spawn
    results.append(check(f"{loc_id}: spawn in bounds (x)", 0 <= sx < lm.width))
    results.append(check(f"{loc_id}: spawn in bounds (y)", 0 <= sy < lm.height))
    results.append(check(f"{loc_id}: spawn walkable", not lm.collision[sy][sx]))

    # Spawn doesn't overlap a blocking object
    spawnBlocked = any(
        obj.blocking and obj.x == sx and obj.y == sy
        for obj in lm.objects
    )
    results.append(check(f"{loc_id}: spawn not on blocking object", not spawnBlocked))


# --- 10. Serialization ---
print("\n=== 10. Serialization ===")

# Test asdict on each LocalMap
for loc_id in EXPECTED_LOCATIONS:
    lm = game.local_maps[loc_id]
    lm_dict = asdict(lm)
    results.append(check(f"{loc_id}: asdict works", isinstance(lm_dict, dict)))
    results.append(check(f"{loc_id}: has width", lm_dict["width"] == MAP_WIDTH))
    results.append(check(f"{loc_id}: has terrain", isinstance(lm_dict["terrain"], list)))
    results.append(check(f"{loc_id}: has collision", isinstance(lm_dict["collision"], list)))

# Test full GameState serialization
game_dict = asdict(game)
results.append(check("Full GameState asdict works", isinstance(game_dict, dict)))
results.append(check("GameState has local_maps", "local_maps" in game_dict))
results.append(check("local_maps has 5 entries", len(game_dict["local_maps"]) == 5))

# JSON round-trip (convert sets to lists)
game_dict_converted = dict(game_dict)
game_dict_converted["visited_locations"] = list(game_dict_converted["visited_locations"])
game_json = json.dumps(game_dict_converted, ensure_ascii=False)
game_loaded = json.loads(game_json)
results.append(check("JSON round-trip succeeds", game_loaded == game_dict_converted))


# --- 11. Backward compatibility ---
print("\n=== 11. Backward compatibility ===")

# Old save without local_maps
old_data = {
    "player": {"name": "Test", "hp": 100, "max_hp": 100, "location": "test",
               "inventory": [], "xp": 0, "level": 1, "stat_points": 0,
               "strength": 10, "vitality": 10, "agility": 10, "intelligence": 10,
               "money": 0},
    "world": {"name": "W", "genre": "F", "time": "12:00", "day": 1,
              "weather": {"condition": "clear", "temperature": 25}, "seed": 0,
              "locations": {}, "npcs": {}, "interactables": {}},
}
old_player = __import__("engine.state", fromlist=["Player"]).Player(**old_data["player"])
results.append(check("Old player data loads", old_player is not None))
results.append(check("Old player local_x defaults", old_player.local_x == 0))

old_game = GameState()
results.append(check("Old GameState has empty local_maps", old_game.local_maps == {}))


# --- 12. WASD/input unchanged ---
print("\n=== 12. Verify no input/rendering changes ===")
# This is a meta-check: the files that should NOT have changed
import importlib
input_handler = importlib.import_module("ui.pygame.input_handler")
world_renderer = importlib.import_module("ui.pygame.world_renderer")
camera = importlib.import_module("ui.pygame.camera")
# Just verify they import without error
results.append(check("input_handler imports OK", input_handler is not None))
results.append(check("world_renderer imports OK", world_renderer is not None))
results.append(check("camera imports OK", camera is not None))


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print(f"{passed}/{total} checks passed, {total - passed} failed")
