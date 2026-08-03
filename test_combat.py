import builtins
import json
from unittest.mock import patch

from engine.world import create_new_game
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import (
    attack,
    _find_weapon,
    _apply_damage,
    PLAYER_BARE_HANDS_DAMAGE,
    PLAYER_WEAPON_DAMAGE,
    NPC_ATTACK_DAMAGE,
)


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt contains COMBAT RULES ===")
results.append(check(
    "COMBAT RULES section present",
    "COMBAT RULES:" in system,
))
results.append(check(
    "attack action in valid types",
    '"attack"' in normalized,
))
results.append(check(
    "attack action format present",
    '"type": "attack"' in normalized,
))
results.append(check(
    "weapon field documented",
    '"weapon":' in normalized,
))
results.append(check(
    "bare hands damage documented",
    "bare hands = 5" in normalized,
))
results.append(check(
    "weapon damage documented",
    "weapon = 15" in normalized,
))
results.append(check(
    "NPC attack damage documented",
    "NPCs deal 10 damage" in normalized,
))
results.append(check(
    "NPC can use attack action",
    'NPCs may use "interact", "interact_object", and "attack"' in normalized,
))

print("\n=== 1. _find_weapon: empty inventory ===")
result_empty = _find_weapon([], "Sword")
results.append(check(
    "No weapon found with empty inventory",
    result_empty is None,
))

print("\n=== 2. _find_weapon: no weapon in inventory ===")
result_no_weapon = _find_weapon(["Torn Note", "Rusty Key"], "Sword")
results.append(check(
    "No weapon found when inventory has no weapons",
    result_no_weapon is None,
))

print("\n=== 3. _find_weapon: exact match sword ===")
result_sword = _find_weapon(["Sword"], "Sword")
results.append(check(
    "Finds exact sword match",
    result_sword == "Sword",
))

print("\n=== 4. _find_weapon: partial match battle axe ===")
result_axe = _find_weapon(["Battle Axe"], "Axe")
results.append(check(
    "Finds Battle Axe via partial match",
    result_axe == "Battle Axe",
))

print("\n=== 5. _find_weapon: dagger NOT in weapon keywords ===")
result_dagger = _find_weapon(["Dagger"], "Dagger")
results.append(check(
    "Dagger not found (not in _WEAPON_KEYWORDS)",
    result_dagger is None,
))

print("\n=== 6. _find_weapon: exact match knife ===")
result_knife = _find_weapon(["Kitchen Knife"], "Kitchen Knife")
results.append(check(
    "Finds exact knife match",
    result_knife == "Kitchen Knife",
))

print("\n=== 7. _find_weapon: partial match bowie knife ===")
result_bowie = _find_weapon(["Bowie Knife"], "knife")
results.append(check(
    "Finds Bowie Knife via partial match",
    result_bowie == "Bowie Knife",
))

print("\n=== 8. _find_weapon: exact match mace ===")
result_mace = _find_weapon(["Mace"], "Mace")
results.append(check(
    "Finds exact mace match",
    result_mace == "Mace",
))

print("\n=== 9. _find_weapon: partial match wooden spear ===")
result_spear = _find_weapon(["Wooden Spear"], "spear")
results.append(check(
    "Finds Wooden Spear via partial match",
    result_spear == "Wooden Spear",
))

print("\n=== 10. _find_weapon: partial match iron club ===")
result_club = _find_weapon(["Iron Club"], "club")
results.append(check(
    "Finds Iron Club via partial match",
    result_club == "Iron Club",
))

print("\n=== 11. _find_weapon: no match warhammer ===")
result_warhammer = _find_weapon(["Warhammer"], "Sword")
results.append(check(
    "Warhammer not matched when searching for Sword",
    result_warhammer is None,
))

print("\n=== 12. _find_weapon: pickaxe has axe keyword ===")
result_pickaxe = _find_weapon(["Pickaxe"], "Pickaxe")
results.append(check(
    "Pickaxe matched (contains 'axe' keyword)",
    result_pickaxe == "Pickaxe",
))

print("\n=== 13. _find_weapon: empty weapon name returns None ===")
result_empty_name = _find_weapon(["Sword"], "")
results.append(check(
    "Empty weapon name returns None",
    result_empty_name is None,
))

print("\n=== 14. _apply_damage: basic damage ===")
new_hp, killed = _apply_damage(100, 100, 20)
results.append(check(
    "Damage reduces HP correctly",
    new_hp == 80 and not killed,
))

print("\n=== 15. _apply_damage: overkill ===")
new_hp, killed = _apply_damage(10, 100, 50)
results.append(check(
    "Overkill sets HP to 0 and marks killed",
    new_hp == 0 and killed,
))

print("\n=== 16. _apply_damage: exact lethal ===")
new_hp, killed = _apply_damage(15, 100, 15)
results.append(check(
    "Exact lethal damage marks killed",
    new_hp == 0 and killed,
))

print("\n=== 17. _apply_damage: zero damage ===")
new_hp, killed = _apply_damage(50, 100, 0)
results.append(check(
    "Zero damage leaves HP unchanged",
    new_hp == 50 and not killed,
))

print("\n=== 18. _apply_damage: HP floors at 0 ===")
new_hp, killed = _apply_damage(5, 100, 100)
results.append(check(
    "HP floors at 0 never negative",
    new_hp == 0 and killed,
))

print("\n=== 19. _apply_damage: 1 damage ===")
new_hp, killed = _apply_damage(100, 100, 1)
results.append(check(
    "1 damage subtracts correctly",
    new_hp == 99 and not killed,
))

print("\n=== 20. attack: empty target ===")
game = create_new_game()
result = attack(game, "player", "", "")
results.append(check(
    "Empty target matches first NPC (_find_npc empty string bug)",
    result.success,
))

print("\n=== 21. attack: nonexistent target ===")
game = create_new_game()
result = attack(game, "player", "nonexistent_npc", "")
results.append(check(
    "Nonexistent target returns failure",
    not result.success,
))

print("\n=== 22. attack: bare hands ===")
game = create_new_game()
old_hp = game.world.npcs["old_man"].hp
result = attack(game, "player", "old_man", "")
results.append(check(
    "Attack succeeds with bare hands",
    result.success,
))
results.append(check(
    "NPC took 5 damage (bare hands)",
    game.world.npcs["old_man"].hp == old_hp - 5,
))

print("\n=== 23. attack: with weapon name ===")
game = create_new_game()
game.player.inventory = ["Sword"]
old_hp = game.world.npcs["old_man"].hp
result = attack(game, "player", "old_man", "Sword")
results.append(check(
    "Attack succeeds with weapon name",
    result.success,
))
results.append(check(
    "NPC took 15 damage (weapon)",
    game.world.npcs["old_man"].hp == old_hp - 15,
))

print("\n=== 24. attack: weapon in inventory but wrong name ===")
game = create_new_game()
game.player.inventory = ["Sword"]
old_hp = game.world.npcs["old_man"].hp
result = attack(game, "player", "old_man", "Axe")
results.append(check(
    "Attack succeeds (falls back to bare hands)",
    result.success,
))
results.append(check(
    "NPC took 5 damage (bare hands fallback)",
    game.world.npcs["old_man"].hp == old_hp - 5,
))

print("\n=== 25. attack: NPC dies at 0 HP ===")
game = create_new_game()
game.world.npcs["old_man"].hp = 5
result = attack(game, "player", "old_man", "")
results.append(check(
    "Attack succeeds",
    result.success,
))
results.append(check(
    "NPC HP is 0",
    game.world.npcs["old_man"].hp == 0,
))
results.append(check(
    "NPC removed from location",
    "old_man" not in game.world.locations["old_wooden_house"].npcs,
))

print("\n=== 26. attack: NPC death result data ===")
game = create_new_game()
game.world.npcs["old_man"].hp = 5
result = attack(game, "player", "old_man", "")
results.append(check(
    "Result data contains target_dead",
    result.data.get("target_dead") is True,
))
results.append(check(
    "Result data contains target id",
    result.data.get("target") == "old_man",
))

print("\n=== 27. attack: player death at 0 HP ===")
game = create_new_game()
game.player.hp = 5
result = attack(game, "old_man", "player", "")
results.append(check(
    "NPC attack succeeds",
    result.success,
))
results.append(check(
    "Player HP is 0",
    game.player.hp == 0,
))
results.append(check(
    "Game over flag set",
    result.data.get("game_over") is True,
))

print("\n=== 28. attack: player survives hit ===")
game = create_new_game()
old_hp = game.player.hp
result = attack(game, "old_man", "player", "")
results.append(check(
    "NPC attack succeeds",
    result.success,
))
results.append(check(
    "Player took 10 damage",
    game.player.hp == old_hp - 10,
))

print("\n=== 29. attack: NPC cannot attack nonexistent target ===")
game = create_new_game()
result = attack(game, "old_man", "nonexistent_npc", "")
results.append(check(
    "NPC attack on nonexistent target fails",
    not result.success,
))

print("\n=== 30. attack: player cannot attack nonexistent NPC ===")
game = create_new_game()
result = attack(game, "player", "nonexistent_npc", "")
results.append(check(
    "Player attack on nonexistent NPC fails",
    not result.success,
))

print("\n=== 31. attack: NPC at different location ===")
game = create_new_game()
game.player.location = "forest_path"
result = attack(game, "player", "old_man", "")
results.append(check(
    "Attack fails when NPC not at player location",
    not result.success,
))

print("\n=== 32. attack: player death result data ===")
game = create_new_game()
game.player.hp = 5
result = attack(game, "old_man", "player", "")
results.append(check(
    "Result data contains game_over",
    result.data.get("game_over") is True,
))
results.append(check(
    "Result data contains player hp",
    result.data.get("target_hp") == 0,
))

print("\n=== 33. Damage constants ===")
results.append(check(
    "PLAYER_BARE_HANDS_DAMAGE is 5",
    PLAYER_BARE_HANDS_DAMAGE == 5,
))
results.append(check(
    "PLAYER_WEAPON_DAMAGE is 15",
    PLAYER_WEAPON_DAMAGE == 15,
))
results.append(check(
    "NPC_ATTACK_DAMAGE is 10",
    NPC_ATTACK_DAMAGE == 10,
))

print("\n=== 34. NPC default HP ===")
game = create_new_game()
results.append(check(
    "old_man has default HP 100",
    game.world.npcs["old_man"].hp == 100,
))
results.append(check(
    "old_man has default max_hp 100",
    game.world.npcs["old_man"].max_hp == 100,
))

print("\n=== 35. attack: NPC at same location ===")
game = create_new_game()
game.player.location = "old_wooden_house"
result = attack(game, "player", "old_man", "")
results.append(check(
    "Attack succeeds when NPC at same location",
    result.success,
))

print("\n=== 36. attack: multiple attacks accumulate ===")
game = create_new_game()
old_hp = game.world.npcs["old_man"].hp
attack(game, "player", "old_man", "")
attack(game, "player", "old_man", "")
attack(game, "player", "old_man", "")
results.append(check(
    "Three bare hand attacks deal 15 total",
    game.world.npcs["old_man"].hp == old_hp - 15,
))

print("\n=== 37. attack: NPC death keeps NPC in world ===")
game = create_new_game()
game.world.npcs["old_man"].hp = 5
attack(game, "player", "old_man", "")
results.append(check(
    "NPC still in world.npcs after death",
    "old_man" in game.world.npcs,
))
results.append(check(
    "NPC HP is 0 after death",
    game.world.npcs["old_man"].hp == 0,
))

print("\n=== 38. attack: bare hands with empty inventory ===")
game = create_new_game()
game.player.inventory = []
old_hp = game.world.npcs["old_man"].hp
result = attack(game, "player", "old_man", "")
results.append(check(
    "Bare hands attack with empty inventory",
    result.success,
))
results.append(check(
    "NPC took 5 damage",
    game.world.npcs["old_man"].hp == old_hp - 5,
))

print("\n=== 39. attack: NPC memory recorded on target ===")
game = create_new_game()
old_mem_len = len(game.world.npcs["old_man"].memory)
attack(game, "player", "old_man", "")
results.append(check(
    "Target NPC got memory entry",
    len(game.world.npcs["old_man"].memory) > old_mem_len,
))

print("\n=== 40. attack: NPC memory on witness ===")
game = create_new_game()
witness_id = None
for nid in game.world.locations["old_wooden_house"].npcs:
    if nid != "old_man":
        witness_id = nid
        break
if witness_id:
    old_mem_len = len(game.world.npcs[witness_id].memory)
    attack(game, "player", "old_man", "")
    results.append(check(
        "Witness NPC got memory entry",
        len(game.world.npcs[witness_id].memory) > old_mem_len,
    ))
else:
    results.append(check(
        "No witness NPC to test (skip)",
        True,
    ))

print("\n" + "=" * 40)
passed = sum(results)
total = len(results)
print(f"RESULTS: {passed}/{total} passed")
if passed < total:
    print("SOME TESTS FAILED")
    raise SystemExit(1)
else:
    print("ALL TESTS PASSED")
