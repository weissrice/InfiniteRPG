# -*- coding: utf-8 -*-
"""Tests for Phase 1: Free Movement data structures."""

import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.state import (
    GameState, Player, NPC, Interactable, Location, World,
    LocalObject, ExitPoint, LocalMap,
)
from engine.world import create_new_game


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []


# --- 1. LocalObject instantiation ---
print("=== 1. LocalObject ===")
obj = LocalObject(id="chair_1", name="Chair", x=5, y=3, tile="C")
results.append(check("LocalObject created", obj is not None))
results.append(check("LocalObject.id", obj.id == "chair_1"))
results.append(check("LocalObject.name", obj.name == "Chair"))
results.append(check("LocalObject.x", obj.x == 5))
results.append(check("LocalObject.y", obj.y == 3))
results.append(check("LocalObject.tile", obj.tile == "C"))
results.append(check("LocalObject.blocking default False", obj.blocking is False))
results.append(check("LocalObject.interactable_id default None", obj.interactable_id is None))

obj2 = LocalObject(id="table", name="Table", x=8, y=2, tile="T", blocking=True, interactable_id="table_1")
results.append(check("LocalObject blocking=True", obj2.blocking is True))
results.append(check("LocalObject interactable_id set", obj2.interactable_id == "table_1"))


# --- 2. ExitPoint instantiation ---
print("\n=== 2. ExitPoint ===")
ep = ExitPoint(x=19, y=7, target_location_id="forest_edge", entry_name="east")
results.append(check("ExitPoint created", ep is not None))
results.append(check("ExitPoint.x", ep.x == 19))
results.append(check("ExitPoint.y", ep.y == 7))
results.append(check("ExitPoint.target_location_id", ep.target_location_id == "forest_edge"))
results.append(check("ExitPoint.entry_name", ep.entry_name == "east"))


# --- 3. LocalMap instantiation ---
print("\n=== 3. LocalMap ===")
terrain = [["." for _ in range(10)] for _ in range(8)]
collision = [[False for _ in range(10)] for _ in range(8)]
lm = LocalMap(width=10, height=8, terrain=terrain, collision=collision)
results.append(check("LocalMap created", lm is not None))
results.append(check("LocalMap.width", lm.width == 10))
results.append(check("LocalMap.height", lm.height == 8))
results.append(check("LocalMap.terrain length", len(lm.terrain) == 8))
results.append(check("LocalMap.terrain[0] length", len(lm.terrain[0]) == 10))
results.append(check("LocalMap.collision length", len(lm.collision) == 8))
results.append(check("LocalMap.objects default empty", lm.objects == []))
results.append(check("LocalMap.exits default empty", lm.exits == {}))
results.append(check("LocalMap.spawn default [0,0]", lm.spawn == [0, 0]))

# LocalMap with objects and exits
obj3 = LocalObject(id="door_east", name="East Door", x=9, y=4, tile="+", blocking=False)
ep2 = ExitPoint(x=9, y=4, target_location_id="deep_forest", entry_name="east")
lm2 = LocalMap(
    width=10, height=8, terrain=terrain, collision=collision,
    objects=[obj3], exits={"east": ep2}, spawn=(5, 4),
)
results.append(check("LocalMap with objects", len(lm2.objects) == 1))
results.append(check("LocalMap with exits", "east" in lm2.exits))
results.append(check("LocalMap spawn set", lm2.spawn == (5, 4)))


# --- 4. Player defaults ---
print("\n=== 4. Player defaults ===")
p = Player()
results.append(check("Player.local_x default 0", p.local_x == 0))
results.append(check("Player.local_y default 0", p.local_y == 0))
results.append(check("Player._area_positions default empty dict", p._area_positions == {}))
results.append(check("Player.location still works", p.location == "old_wooden_house"))
results.append(check("Player.name still works", p.name == "Traveler"))

p2 = Player(name="Test", local_x=5, local_y=3)
results.append(check("Player local_x set", p2.local_x == 5))
results.append(check("Player local_y set", p2.local_y == 3))


# --- 5. NPC defaults ---
print("\n=== 5. NPC defaults ===")
npc = NPC(id="test_npc", name="Test NPC", location="test_loc")
results.append(check("NPC.local_x default -1", npc.local_x == -1))
results.append(check("NPC.local_y default -1", npc.local_y == -1))
results.append(check("NPC.location still works", npc.location == "test_loc"))

npc2 = NPC(id="placed", name="Placed NPC", location="loc", local_x=3, local_y=7)
results.append(check("NPC local_x set", npc2.local_x == 3))
results.append(check("NPC local_y set", npc2.local_y == 7))


# --- 6. Interactable defaults ---
print("\n=== 6. Interactable defaults ===")
inter = Interactable(id="test_obj", name="Test Object", description="A test.", location="test_loc")
results.append(check("Interactable.local_x default -1", inter.local_x == -1))
results.append(check("Interactable.local_y default -1", inter.local_y == -1))
results.append(check("Interactable.location still works", inter.location == "test_loc"))

inter2 = Interactable(id="placed_obj", name="Placed", description="Placed.", location="loc", local_x=2, local_y=4)
results.append(check("Interactable local_x set", inter2.local_x == 2))
results.append(check("Interactable local_y set", inter2.local_y == 4))


# --- 7. GameState.local_maps default ---
print("\n=== 7. GameState.local_maps ===")
gs = GameState()
results.append(check("GameState.local_maps default empty dict", gs.local_maps == {}))

# Verify empty GameState has no current location (no world locations yet)
loc = gs.current_location()
results.append(check("Empty GameState.current_location() is None", loc is None))

# Verify with a real game
game_real = create_new_game()
loc_real = game_real.current_location()
results.append(check("GameState.current_location() works with real game", loc_real is not None))
results.append(check("GameState.current_location().id", loc_real.id == "old_wooden_house"))
results.append(check("GameState.local_maps accessible on real game", isinstance(game_real.local_maps, dict)))


# --- 8. Serialization with dataclasses.asdict() ---
print("\n=== 8. Serialization ===")

# Test LocalObject serialization
obj_dict = asdict(obj)
results.append(check("LocalObject serializes to dict", isinstance(obj_dict, dict)))
results.append(check("LocalObject dict has id", obj_dict["id"] == "chair_1"))
results.append(check("LocalObject dict has blocking", obj_dict["blocking"] is False))

# Test ExitPoint serialization
ep_dict = asdict(ep)
results.append(check("ExitPoint serializes to dict", isinstance(ep_dict, dict)))
results.append(check("ExitPoint dict has x", ep_dict["x"] == 19))
results.append(check("ExitPoint dict has target_location_id", ep_dict["target_location_id"] == "forest_edge"))

# Test LocalMap serialization
lm_dict = asdict(lm)
results.append(check("LocalMap serializes to dict", isinstance(lm_dict, dict)))
results.append(check("LocalMap dict has width", lm_dict["width"] == 10))
results.append(check("LocalMap dict has terrain", isinstance(lm_dict["terrain"], list)))
results.append(check("LocalMap dict has objects", lm_dict["objects"] == []))
results.append(check("LocalMap dict has exits", lm_dict["exits"] == {}))
results.append(check("LocalMap dict has spawn", lm_dict["spawn"] == [0, 0]))

# Test LocalMap with objects serializes
lm2_dict = asdict(lm2)
results.append(check("LocalMap with objects serializes", isinstance(lm2_dict, dict)))
results.append(check("LocalMap objects list has 1 entry", len(lm2_dict["objects"]) == 1))
results.append(check("LocalMap exits dict has 1 entry", len(lm2_dict["exits"]) == 1))

# Test Player serialization
p_dict = asdict(p)
results.append(check("Player serializes to dict", isinstance(p_dict, dict)))
results.append(check("Player dict has local_x", p_dict["local_x"] == 0))
results.append(check("Player dict has local_y", p_dict["local_y"] == 0))
results.append(check("Player dict has _area_positions", p_dict["_area_positions"] == {}))

# Test NPC serialization
npc_dict = asdict(npc)
results.append(check("NPC serializes to dict", isinstance(npc_dict, dict)))
results.append(check("NPC dict has local_x", npc_dict["local_x"] == -1))
results.append(check("NPC dict has local_y", npc_dict["local_y"] == -1))

# Test Interactable serialization
inter_dict = asdict(inter)
results.append(check("Interactable serializes to dict", isinstance(inter_dict, dict)))
results.append(check("Interactable dict has local_x", inter_dict["local_x"] == -1))
results.append(check("Interactable dict has local_y", inter_dict["local_y"] == -1))

# Test full GameState serialization
gs_dict = asdict(gs)
results.append(check("GameState serializes to dict", isinstance(gs_dict, dict)))
results.append(check("GameState dict has local_maps", "local_maps" in gs_dict))
results.append(check("GameState local_maps is empty dict", gs_dict["local_maps"] == {}))

# Test JSON round-trip for GameState (visited_locations set needs list conversion)
gs_dict_converted = dict(gs_dict)
gs_dict_converted["visited_locations"] = list(gs_dict_converted["visited_locations"])
gs_json = json.dumps(gs_dict_converted, ensure_ascii=False)
gs_loaded = json.loads(gs_json)
results.append(check("GameState JSON round-trip", gs_loaded == gs_dict_converted))

# Test full GameState with a complete world
game = create_new_game()
game_dict = asdict(game)
results.append(check("Full GameState serializes", isinstance(game_dict, dict)))
results.append(check("Full GameState has local_maps", "local_maps" in game_dict))
results.append(check("Full GameState player has local_x", "local_x" in game_dict["player"]))
results.append(check("Full GameState NPC has local_x", "local_x" in game_dict["world"]["npcs"]["old_man"]))

# JSON round-trip for full game (visited_locations set needs list conversion)
game_dict_converted = dict(game_dict)
game_dict_converted["visited_locations"] = list(game_dict_converted["visited_locations"])
game_json = json.dumps(game_dict_converted, ensure_ascii=False)
game_loaded = json.loads(game_json)
results.append(check("Full GameState JSON round-trip", game_loaded == game_dict_converted))


# --- 9. Backward compatibility: constructing from old-style dicts ---
print("\n=== 9. Backward compatibility ===")

# Simulate old save data (no local_x, local_y, _area_positions, local_maps)
old_player_data = {
    "name": "Traveler",
    "hp": 100,
    "max_hp": 100,
    "location": "old_wooden_house",
    "inventory": ["Rusty Key", "Torn Note"],
    "xp": 0,
    "level": 1,
    "stat_points": 0,
    "strength": 10,
    "vitality": 10,
    "agility": 10,
    "intelligence": 10,
    "money": 0,
}
old_player = Player(**old_player_data)
results.append(check("Old player data loads", old_player is not None))
results.append(check("Old player local_x defaults to 0", old_player.local_x == 0))
results.append(check("Old player local_y defaults to 0", old_player.local_y == 0))
results.append(check("Old player _area_positions defaults to {}", old_player._area_positions == {}))

old_npc_data = {
    "id": "old_man",
    "name": "Old Man",
    "location": "old_wooden_house",
    "description": "An elderly man.",
    "disposition": 10,
}
old_npc = NPC(**old_npc_data)
results.append(check("Old NPC data loads", old_npc is not None))
results.append(check("Old NPC local_x defaults to -1", old_npc.local_x == -1))
results.append(check("Old NPC local_y defaults to -1", old_npc.local_y == -1))

old_inter_data = {
    "id": "locked_door",
    "name": "Locked Door",
    "description": "A locked door.",
    "location": "upstairs",
    "state": "locked",
}
old_inter = Interactable(**old_inter_data)
results.append(check("Old interactable data loads", old_inter is not None))
results.append(check("Old interactable local_x defaults to -1", old_inter.local_x == -1))
results.append(check("Old interactable local_y defaults to -1", old_inter.local_y == -1))


# --- 10. Save/load with save.py (existing format) ---
print("\n=== 10. Save/load integration ===")
from engine.save import save_game, load_game, SAVE_FILE
import tempfile

# Create a temp save file
with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
    tmp_path = f.name

try:
    save_game(game, path=SAVE_FILE.__class__(tmp_path))
    loaded = load_game(path=SAVE_FILE.__class__(tmp_path))
    results.append(check("Save/load round-trip succeeds", loaded is not None))
    results.append(check("Loaded player location", loaded.player.location == "old_wooden_house"))
    results.append(check("Loaded player local_x", loaded.player.local_x == game.player.local_x))
    results.append(check("Loaded player local_y", loaded.player.local_y == game.player.local_y))
    results.append(check("Loaded local_maps is populated", len(loaded.local_maps) > 0))
    results.append(check("Loaded NPC local_x", loaded.world.npcs["old_man"].local_x == game.world.npcs["old_man"].local_x))
    results.append(check("Loaded NPC local_y", loaded.world.npcs["old_man"].local_y == game.world.npcs["old_man"].local_y))
finally:
    os.unlink(tmp_path)


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for r in results if r)
total = len(results)
print(f"{passed}/{total} checks passed, {total - passed} failed")
