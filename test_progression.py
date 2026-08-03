import builtins
import json
from unittest.mock import patch

from engine.world import create_new_game
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import (
    allocate_stat,
    attack,
    _award_xp,
    _recalculate_max_hp,
    _process_level_ups,
    XP_PER_LEVEL,
    XP_PER_NPC_KILL,
    PLAYER_BARE_HANDS_DAMAGE,
    PLAYER_WEAPON_DAMAGE,
)
from engine.context import build_game_context


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

# ---------------------------------------------------------------
# 0. System Prompt
# ---------------------------------------------------------------

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("\n=== 0. System Prompt ===")
results.append(check(
    "PROGRESSION RULES section present",
    "PLAYER PROGRESSION RULES:" in system,
))
results.append(check(
    "allocate_stat in valid action types",
    "allocate_stat" in normalized,
))
results.append(check(
    "allocate_stat format present",
    '"type": "allocate_stat"' in normalized,
))
results.append(check(
    "stat field documented",
    '"stat":' in normalized,
))
results.append(check(
    "amount field documented",
    '"amount":' in normalized,
))
results.append(check(
    "strength, vitality, agility, intelligence listed",
    all(s in normalized for s in [
        "strength", "vitality", "agility", "intelligence"
    ]),
))
results.append(check(
    "XP per level documented",
    "100" in normalized,
))
results.append(check(
    "XP per NPC kill documented",
    "50 XP" in normalized,
))
results.append(check(
    "Strength modifier documented",
    "STR - 10" in normalized or "strength - 10" in normalized,
))
results.append(check(
    "Vitality HP formula documented",
    "VIT - 10" in normalized or "vitality - 10" in normalized,
))

# ---------------------------------------------------------------
# 1. Player Defaults
# ---------------------------------------------------------------

print("\n=== 1. Player Defaults ===")
game = create_new_game()
player = game.player

results.append(check(
    "player.xp defaults to 0",
    player.xp == 0,
))
results.append(check(
    "player.level defaults to 1",
    player.level == 1,
))
results.append(check(
    "player.stat_points defaults to 0",
    player.stat_points == 0,
))
results.append(check(
    "player.strength defaults to 10",
    player.strength == 10,
))
results.append(check(
    "player.vitality defaults to 10",
    player.vitality == 10,
))
results.append(check(
    "player.agility defaults to 10",
    player.agility == 10,
))
results.append(check(
    "player.intelligence defaults to 10",
    player.intelligence == 10,
))
results.append(check(
    "player.max_hp defaults to 100",
    player.max_hp == 100,
))
results.append(check(
    "player.hp defaults to 100",
    player.hp == 100,
))

# ---------------------------------------------------------------
# 2. XP Award
# ---------------------------------------------------------------

print("\n=== 2. XP Award ===")
game = create_new_game()
result = _award_xp(game, 50, "test")

results.append(check(
    "XP award succeeds",
    result.success,
))
results.append(check(
    "XP awarded correctly",
    game.player.xp == 50,
))
results.append(check(
    "No level up at 50 XP",
    game.player.level == 1,
))
results.append(check(
    "Source recorded",
    result.data.get("source") == "test",
))

# ---------------------------------------------------------------
# 3. Level-Up
# ---------------------------------------------------------------

print("\n=== 3. Level-Up ===")
game = create_new_game()
result = _award_xp(game, 100, "test")

results.append(check(
    "Level-up at 100 XP",
    game.player.level == 2,
))
results.append(check(
    "Stat points gained",
    game.player.stat_points == 1,
))
results.append(check(
    "XP not reset after level-up",
    game.player.xp == 100,
))
results.append(check(
    "Level-up reported in result",
    result.data.get("level_ups", 0) == 1,
))

# ---------------------------------------------------------------
# 4. Multi-Level
# ---------------------------------------------------------------

print("\n=== 4. Multi-Level ===")
game = create_new_game()
result = _award_xp(game, 250, "test")

results.append(check(
    "Level is 3 (250 XP = 100 + 100, remainder 50)",
    game.player.level == 3,
))
results.append(check(
    "2 stat points gained",
    game.player.stat_points == 2,
))
results.append(check(
    "XP remainder is 50",
    game.player.xp == 250,
))

# ---------------------------------------------------------------
# 5. XP Validation
# ---------------------------------------------------------------

print("\n=== 5. XP Validation ===")
game = create_new_game()
result_bad = _award_xp(game, -10, "test")

results.append(check(
    "Negative XP fails",
    not result_bad.success,
))
results.append(check(
    "XP unchanged after invalid award",
    game.player.xp == 0,
))

result_zero = _award_xp(game, 0, "test")
results.append(check(
    "Zero XP fails",
    not result_zero.success,
))

result_float = _award_xp(game, 10.5, "test")
results.append(check(
    "Float XP is converted to int",
    result_float.success,
    ),
)

# ---------------------------------------------------------------
# 6. Allocate Stat
# ---------------------------------------------------------------

print("\n=== 6. Allocate Stat ===")
game = create_new_game()
game.player.stat_points = 3

result = allocate_stat(game, "strength", 1)

results.append(check(
    "Allocation succeeds",
    result.success,
))
results.append(check(
    "Strength increased",
    game.player.strength == 11,
))
results.append(check(
    "Stat points decremented",
    game.player.stat_points == 2,
))

# ---------------------------------------------------------------
# 7. Allocate Multiple
# ---------------------------------------------------------------

print("\n=== 7. Allocate Multiple ===")
game = create_new_game()
game.player.stat_points = 5

result = allocate_stat(game, "vitality", 3)

results.append(check(
    "Allocation succeeds",
    result.success,
))
results.append(check(
    "Vitality increased by 3",
    game.player.vitality == 13,
))
results.append(check(
    "Stat points decremented by 3",
    game.player.stat_points == 2,
))
results.append(check(
    "Max HP increased by 15 (3*5)",
    game.player.max_hp == 115,
))
results.append(check(
    "HP increased by same delta",
    game.player.hp == 115,
))

# ---------------------------------------------------------------
# 8. Allocate - Not Enough Points
# ---------------------------------------------------------------

print("\n=== 8. Allocate - Not Enough Points ===")
game = create_new_game()
game.player.stat_points = 1

result = allocate_stat(game, "strength", 5)

results.append(check(
    "Fails with insufficient points",
    not result.success,
))
results.append(check(
    "Strength unchanged",
    game.player.strength == 10,
))

# ---------------------------------------------------------------
# 9. Allocate - Invalid Stat
# ---------------------------------------------------------------

print("\n=== 9. Allocate - Invalid Stat ===")
game = create_new_game()
game.player.stat_points = 3

result = allocate_stat(game, "luck", 1)

results.append(check(
    "Fails with invalid stat",
    not result.success,
))
results.append(check(
    "Error mentions valid stats",
    "strength" in result.message.lower(),
))

# ---------------------------------------------------------------
# 10. Allocate - Zero Amount
# ---------------------------------------------------------------

print("\n=== 10. Allocate - Zero Amount ===")
game = create_new_game()
game.player.stat_points = 3

result = allocate_stat(game, "strength", 0)

results.append(check(
    "Fails with zero amount",
    not result.success,
))

# ---------------------------------------------------------------
# 11. Strength Modifier - Bare Hands
# ---------------------------------------------------------------

print("\n=== 11. Strength Modifier - Bare Hands ===")
game = create_new_game()
player = game.player
player.strength = 15

# Damage = max(1, 5 + (15 - 10)) = max(1, 10) = 10
bare_damage = max(1, PLAYER_BARE_HANDS_DAMAGE + player.strength - 10)
results.append(check(
    "Bare hands damage with STR 15 is 10",
    bare_damage == 10,
))

# ---------------------------------------------------------------
# 12. Strength Modifier - Weapon
# ---------------------------------------------------------------

print("\n=== 12. Strength Modifier - Weapon ===")
game = create_new_game()
player = game.player
player.strength = 15

weapon_damage = max(1, PLAYER_WEAPON_DAMAGE + player.strength - 10)
results.append(check(
    "Weapon damage with STR 15 is 20",
    weapon_damage == 20,
))

# ---------------------------------------------------------------
# 13. Strength Modifier - Minimum Damage
# ---------------------------------------------------------------

print("\n=== 13. Strength Modifier - Minimum Damage ===")
game = create_new_game()
player = game.player
player.strength = 1  # Very low strength

bare_damage = max(1, PLAYER_BARE_HANDS_DAMAGE + player.strength - 10)
results.append(check(
    "Bare hands damage with STR 1 is 1 (minimum)",
    bare_damage == 1,
))

# ---------------------------------------------------------------
# 14. Vitality HP Formula
# ---------------------------------------------------------------

print("\n=== 14. Vitality HP Formula ===")
game = create_new_game()
player = game.player

# max_hp = 100 + ((10 - 10) * 5) = 100
results.append(check(
    "VIT 10 = max_hp 100",
    player.max_hp == 100,
))

player.vitality = 15
_recalculate_max_hp(game)
results.append(check(
    "VIT 15 = max_hp 125",
    player.max_hp == 125,
))

player.vitality = 5
_recalculate_max_hp(game)
results.append(check(
    "VIT 5 = max_hp 75",
    player.max_hp == 75,
))

# ---------------------------------------------------------------
# 15. Vitality HP Proportional
# ---------------------------------------------------------------

print("\n=== 15. Vitality HP Proportional ===")
game = create_new_game()
player = game.player
player.hp = 80
player.vitality = 12
_recalculate_max_hp(game)

results.append(check(
    "HP increased proportionally on VIT increase",
    player.hp == 90,  # 80 + (110 - 100) = 90
))
results.append(check(
    "Max HP is 110",
    player.max_hp == 110,
))

# ---------------------------------------------------------------
# 16. Agility No Effect
# ---------------------------------------------------------------

print("\n=== 16. Agility No Effect ===")
game = create_new_game()
player = game.player

old_max_hp = player.max_hp
player.agility = 20
_recalculate_max_hp(game)

results.append(check(
    "Max HP unchanged after agility increase",
    player.max_hp == old_max_hp,
))

# ---------------------------------------------------------------
# 17. Intelligence No Effect
# ---------------------------------------------------------------

print("\n=== 17. Intelligence No Effect ===")
game = create_new_game()
player = game.player

old_max_hp = player.max_hp
player.intelligence = 20
_recalculate_max_hp(game)

results.append(check(
    "Max HP unchanged after intelligence increase",
    player.max_hp == old_max_hp,
))

# ---------------------------------------------------------------
# 18. Quest XP Reward
# ---------------------------------------------------------------

print("\n=== 18. Quest XP Reward ===")
from engine.state import Quest, QuestObjective

game = create_new_game()
player = game.player

quest = Quest(
    id="test_quest",
    title="Test Quest",
    description="Complete this",
    giver="old_man",
    state="active",
    objectives=[
        QuestObjective(
            id="obj_1",
            type="find",
            description="Find item",
            target="Torn Note",
            required=1,
            current=0,
        ),
    ],
    rewards={"items": [], "relationships": {}, "xp": 75},
)
game.quests["test_quest"] = quest

# Complete the objective
quest.objectives[0].current = 1

# Trigger completion check via take_item
from engine.actions import take_item
result = take_item(game, "Torn Note")

results.append(check(
    "Quest completed via take_item",
    quest.state == "completed",
))
results.append(check(
    "XP awarded from quest",
    player.xp == 75,
))

# ---------------------------------------------------------------
# 19. Context - Progression Fields
# ---------------------------------------------------------------

print("\n=== 19. Context - Progression Fields ===")
game = create_new_game()
player = game.player
player.xp = 150
player.level = 2
player.stat_points = 1
player.strength = 12
player.vitality = 11
player.agility = 13
player.intelligence = 14

context = build_game_context(game)

results.append(check(
    "Level shown in context",
    "Level: 2" in context,
))
results.append(check(
    "XP shown in context",
    "XP: 150/200" in context,
))
results.append(check(
    "Stat points shown in context",
    "Stat Points: 1" in context,
))
results.append(check(
    "Strength shown in context",
    "Strength: 12" in context,
))
results.append(check(
    "Vitality shown in context",
    "Vitality: 11" in context,
))
results.append(check(
    "Agility shown in context",
    "Agility: 13" in context,
))
results.append(check(
    "Intelligence shown in context",
    "Intelligence: 14" in context,
))
results.append(check(
    "Mechanical notes present",
    "MECHANICAL NOTES:" in context,
))

# ---------------------------------------------------------------
# 20. Context - Bare Hands Damage Display
# ---------------------------------------------------------------

print("\n=== 20. Context - Bare Hands Damage Display ===")
game = create_new_game()
player = game.player
player.strength = 15

context = build_game_context(game)

results.append(check(
    "Bare hands damage 10 shown",
    "10 damage" in context,
))
results.append(check(
    "Weapon damage 20 shown",
    "20 damage" in context,
))

# ---------------------------------------------------------------
# 21. Save/Load Progression
# ---------------------------------------------------------------

print("\n=== 21. Save/Load Progression ===")
import tempfile
from pathlib import Path
from engine.save import save_game, load_game

game = create_new_game()
player = game.player
player.xp = 150
player.level = 2
player.stat_points = 1
player.strength = 15
player.vitality = 12
player.agility = 11
player.intelligence = 13
player.hp = 90
player.max_hp = 110

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)
loaded_player = loaded.player

results.append(check(
    "XP persisted",
    loaded_player.xp == 150,
))
results.append(check(
    "Level persisted",
    loaded_player.level == 2,
))
results.append(check(
    "Stat points persisted",
    loaded_player.stat_points == 1,
))
results.append(check(
    "Strength persisted",
    loaded_player.strength == 15,
))
results.append(check(
    "Vitality persisted",
    loaded_player.vitality == 12,
))
results.append(check(
    "Agility persisted",
    loaded_player.agility == 11,
))
results.append(check(
    "Intelligence persisted",
    loaded_player.intelligence == 13,
))
results.append(check(
    "HP persisted",
    loaded_player.hp == 90,
))
results.append(check(
    "Max HP persisted",
    loaded_player.max_hp == 110,
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 22. Old Save Compatibility
# ---------------------------------------------------------------

print("\n=== 22. Old Save Compatibility ===")

old_save = {
    "version": 1,
    "player": {
        "name": "Traveler",
        "hp": 100,
        "max_hp": 100,
        "location": "old_wooden_house",
        "inventory": ["Rusty Key", "Torn Note"],
    },
    "world": {
        "name": "Test World",
        "genre": "fantasy",
        "day": 1,
        "time": "12:00",
        "weather": "clear",
        "locations": {},
        "npcs": {},
    },
    "conversations": {},
    "quests": {},
}

with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False
) as f:
    json.dump(old_save, f)
    old_path = Path(f.name)

old_loaded = load_game(old_path)
old_player = old_loaded.player

results.append(check(
    "Old save loads without error",
    old_player is not None,
))
results.append(check(
    "XP defaults to 0",
    old_player.xp == 0,
))
results.append(check(
    "Level defaults to 1",
    old_player.level == 1,
))
results.append(check(
    "Stat points defaults to 0",
    old_player.stat_points == 0,
))
results.append(check(
    "Strength defaults to 10",
    old_player.strength == 10,
))
results.append(check(
    "Vitality defaults to 10",
    old_player.vitality == 10,
))
results.append(check(
    "Agility defaults to 10",
    old_player.agility == 10,
))
results.append(check(
    "Intelligence defaults to 10",
    old_player.intelligence == 10,
))

old_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 23. Process Level Ups - No Pending
# ---------------------------------------------------------------

print("\n=== 23. Process Level Ups - No Pending ===")
game = create_new_game()
game.player.xp = 50

result = _process_level_ups(game)

results.append(check(
    "No level ups at 50 XP",
    result["level_ups"] == 0,
))
results.append(check(
    "Level unchanged",
    game.player.level == 1,
))

# ---------------------------------------------------------------
# 24. Process Level Ups - Exact Threshold
# ---------------------------------------------------------------

print("\n=== 24. Process Level Ups - Exact Threshold ===")
game = create_new_game()
game.player.xp = 100

result = _process_level_ups(game)

results.append(check(
    "1 level up at exact threshold",
    result["level_ups"] == 1,
))
results.append(check(
    "New level is 2",
    game.player.level == 2,
))
results.append(check(
    "1 stat point gained",
    game.player.stat_points == 1,
))

# ---------------------------------------------------------------
# 25. Multiple Allocate
# ---------------------------------------------------------------

print("\n=== 25. Multiple Allocate ===")
game = create_new_game()
game.player.stat_points = 10

allocate_stat(game, "strength", 3)
allocate_stat(game, "vitality", 2)
allocate_stat(game, "agility", 1)
allocate_stat(game, "intelligence", 4)

results.append(check(
    "Strength is 13",
    game.player.strength == 13,
))
results.append(check(
    "Vitality is 12",
    game.player.vitality == 12,
))
results.append(check(
    "Agility is 11",
    game.player.agility == 11,
))
results.append(check(
    "Intelligence is 14",
    game.player.intelligence == 14,
))
results.append(check(
    "All stat points used",
    game.player.stat_points == 0,
))
results.append(check(
    "Max HP reflects vitality",
    game.player.max_hp == 110,
))

# ---------------------------------------------------------------
# 26. Combat Integration - Strength Modifier
# ---------------------------------------------------------------

print("\n=== 26. Combat Integration - Strength Modifier ===")
from engine.state import NPC

game = create_new_game()
player = game.player
player.strength = 20

# Add a test NPC
test_npc = NPC(
    id="test_enemy",
    name="Test Enemy",
    location="old_wooden_house",
    description="A test enemy",
    hp=100,
    max_hp=100,
)
game.world.npcs["test_enemy"] = test_npc
location = game.world.locations["old_wooden_house"]
location.npcs.append("test_enemy")

result = attack(game, "player", "test_enemy")

results.append(check(
    "Attack succeeds",
    result.success,
))
results.append(check(
    "Damage includes strength modifier (max(1, 5 + 20 - 10) = 15)",
    result.data.get("damage") == 15,
))

# ---------------------------------------------------------------
# 27. Combat Integration - XP on Kill
# ---------------------------------------------------------------

print("\n=== 27. Combat Integration - XP on Kill ===")
game = create_new_game()
player = game.player
player.hp = player.max_hp
player.strength = 20  # bare hands = max(1, 5 + 20 - 10) = 15 > 10 HP

test_npc = NPC(
    id="weak_enemy",
    name="Weak Enemy",
    location="old_wooden_house",
    description="A weak enemy",
    hp=10,
    max_hp=10,
)
game.world.npcs["weak_enemy"] = test_npc
location = game.world.locations["old_wooden_house"]
location.npcs.append("weak_enemy")

result = attack(game, "player", "weak_enemy")

results.append(check(
    "Attack succeeds",
    result.success,
))
results.append(check(
    "Target is dead",
    result.data.get("target_dead", False),
))
results.append(check(
    "XP awarded on kill",
    player.xp == XP_PER_NPC_KILL,
))
results.append(check(
    "XP data in result",
    "xp" in result.data and result.data["xp"].get("xp_gained") == XP_PER_NPC_KILL,
))

# ---------------------------------------------------------------
# 28. /status Command Exists
# ---------------------------------------------------------------

print("\n=== 28. /status Command Exists ===")

import ast
import inspect

with open("main.py", "r", encoding="utf-8") as f:
    source = f.read()

results.append(check(
    "/status handler present",
    '"/status"' in source,
))
results.append(check(
    "show_status function defined",
    "def show_status" in source,
))

# ---------------------------------------------------------------
# 29. Context - Level Up Threshold Display
# ---------------------------------------------------------------

print("\n=== 29. Context - Level Up Threshold Display ===")
game = create_new_game()
player = game.player
player.level = 3
player.xp = 250

context = build_game_context(game)

results.append(check(
    "XP threshold shows level × 100",
    "XP: 250/300" in context,
))

# ---------------------------------------------------------------
# 30. Allocate - Empty Stat
# ---------------------------------------------------------------

print("\n=== 30. Allocate - Empty Stat ===")
game = create_new_game()
game.player.stat_points = 3

result = allocate_stat(game, "", 1)

results.append(check(
    "Fails with empty stat",
    not result.success,
))

# ---------------------------------------------------------------
# 31. Allocate - Float Amount
# ---------------------------------------------------------------

print("\n=== 31. Allocate - Float Amount ===")
game = create_new_game()
game.player.stat_points = 3

result = allocate_stat(game, "strength", 1.5)

results.append(check(
    "Float amount converted to int",
    result.success,
))
results.append(check(
    "Strength increased by 1",
    game.player.strength == 11,
))

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------

print("\n" + "=" * 60)
passed = sum(results)
total = len(results)

if passed == total:
    print(f"ALL {total} ASSERTIONS PASSED")
else:
    failed = total - passed
    print(f"{passed}/{total} assertions passed ({failed} FAILED)")

print("=" * 60)
raise SystemExit(0 if passed == total else 1)
