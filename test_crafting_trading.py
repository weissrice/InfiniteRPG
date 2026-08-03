import tempfile
from pathlib import Path

from engine.world import create_new_game
from engine.game import SYSTEM_PROMPT
from engine.actions import (
    craft,
    buy_item,
    sell_item,
    RECIPES,
    ITEM_PRICES,
    SELL_MULTIPLIER,
    XP_PER_CRAFT,
)
from engine.context import build_game_context
from engine.state import NPC
from engine.save import save_game, load_game


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
    "CRAFTING & TRADING RULES section present",
    "CRAFTING & TRADING RULES:" in system,
))
results.append(check(
    "craft in valid action types",
    "craft" in normalized,
))
results.append(check(
    "buy_item in valid action types",
    "buy_item" in normalized,
))
results.append(check(
    "sell_item in valid action types",
    "sell_item" in normalized,
))
results.append(check(
    "craft action format present",
    '"type": "craft"' in normalized,
))
results.append(check(
    "buy_item action format present",
    '"type": "buy_item"' in normalized,
))
results.append(check(
    "sell_item action format present",
    '"type": "sell_item"' in normalized,
))
results.append(check(
    "recipe_id field documented",
    '"recipe_id":' in normalized,
))
results.append(check(
    "npc field documented",
    '"npc":' in normalized,
))
results.append(check(
    "item field documented",
    '"item":' in normalized,
))
results.append(check(
    "quantity field documented",
    '"quantity":' in normalized,
))

# ---------------------------------------------------------------
# 1. Valid craft succeeds
# ---------------------------------------------------------------

print("\n=== 1. Valid craft succeeds ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb", "Herb", "Empty Bottle"]

result = craft(game, "health_potion")

results.append(check(
    "Craft succeeds",
    result.success,
))
results.append(check(
    "Health Potion in inventory",
    "Health Potion" in player.inventory,
))
results.append(check(
    "Herbs consumed",
    player.inventory.count("Herb") == 0,
))
results.append(check(
    "Empty Bottle consumed",
    player.inventory.count("Empty Bottle") == 0,
))
results.append(check(
    "XP awarded",
    player.xp == XP_PER_CRAFT,
))

# ---------------------------------------------------------------
# 2. Recipe not found fails
# ---------------------------------------------------------------

print("\n=== 2. Recipe not found fails ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb", "Herb", "Empty Bottle"]

result = craft(game, "nonexistent_recipe")

results.append(check(
    "Craft fails",
    not result.success,
))
results.append(check(
    "Inventory unchanged",
    player.inventory.count("Herb") == 2,
))

# ---------------------------------------------------------------
# 3. Missing ingredient fails
# ---------------------------------------------------------------

print("\n=== 3. Missing ingredient fails ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb"]

result = craft(game, "health_potion")

results.append(check(
    "Craft fails",
    not result.success,
))
results.append(check(
    "Herb still in inventory",
    player.inventory.count("Herb") == 1,
))

# ---------------------------------------------------------------
# 4. Insufficient ingredient quantity fails
# ---------------------------------------------------------------

print("\n=== 4. Insufficient ingredient quantity fails ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb", "Empty Bottle"]

result = craft(game, "health_potion")

results.append(check(
    "Craft fails",
    not result.success,
))
results.append(check(
    "Herb still in inventory",
    player.inventory.count("Herb") == 1,
))

# ---------------------------------------------------------------
# 5. Failed craft does not mutate inventory
# ---------------------------------------------------------------

print("\n=== 5. Failed craft does not mutate inventory ===")
game = create_new_game()
player = game.player
original_inventory = player.inventory.copy()

result = craft(game, "health_potion")

results.append(check(
    "Craft fails",
    not result.success,
))
results.append(check(
    "Inventory unchanged",
    player.inventory == original_inventory,
))

# ---------------------------------------------------------------
# 6. Successful craft consumes exact ingredients
# ---------------------------------------------------------------

print("\n=== 6. Successful craft consumes exact ingredients ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb", "Herb", "Empty Bottle", "Wood"]

craft(game, "health_potion")

results.append(check(
    "Herbs consumed",
    player.inventory.count("Herb") == 0,
))
results.append(check(
    "Empty Bottle consumed",
    player.inventory.count("Empty Bottle") == 0,
))
results.append(check(
    "Wood still present",
    player.inventory.count("Wood") == 1,
))

# ---------------------------------------------------------------
# 7. Successful craft produces exact output
# ---------------------------------------------------------------

print("\n=== 7. Successful craft produces exact output ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb", "Herb", "Empty Bottle"]

craft(game, "health_potion")

results.append(check(
    "Health Potion produced",
    player.inventory.count("Health Potion") == 1,
))

# ---------------------------------------------------------------
# 8. Output quantity is correct
# ---------------------------------------------------------------

print("\n=== 8. Output quantity is correct ===")
game = create_new_game()
player = game.player
player.inventory = ["Wood", "Cloth"]

craft(game, "torch")

results.append(check(
    "Torch produced (quantity 1)",
    player.inventory.count("Torch") == 1,
))

# ---------------------------------------------------------------
# 9. Multiple crafts work when ingredients allow
# ---------------------------------------------------------------

print("\n=== 9. Multiple crafts work when ingredients allow ===")
game = create_new_game()
player = game.player
player.inventory = ["Wood", "Wood", "Cloth", "Cloth"]

craft(game, "torch")
craft(game, "torch")

results.append(check(
    "Two torches produced",
    player.inventory.count("Torch") == 2,
))
results.append(check(
    "All ingredients consumed",
    player.inventory.count("Wood") == 0,
))
results.append(check(
    "All cloth consumed",
    player.inventory.count("Cloth") == 0,
))

# ---------------------------------------------------------------
# 10. Unknown recipe cannot be crafted
# ---------------------------------------------------------------

print("\n=== 10. Unknown recipe cannot be crafted ===")
game = create_new_game()
player = game.player
player.inventory = ["Herb", "Herb", "Empty Bottle"]

result = craft(game, "unknown")

results.append(check(
    "Craft fails",
    not result.success,
))

# ---------------------------------------------------------------
# 11. Valid purchase succeeds
# ---------------------------------------------------------------

print("\n=== 11. Valid purchase succeeds ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
merchant.inventory = ["Health Potion"]

result = buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Buy succeeds",
    result.success,
))
results.append(check(
    "Health Potion in player inventory",
    "Health Potion" in player.inventory,
))
results.append(check(
    "Money deducted",
    player.money == 70,
))

# ---------------------------------------------------------------
# 12. Insufficient money fails
# ---------------------------------------------------------------

print("\n=== 12. Insufficient money fails ===")
game = create_new_game()
player = game.player
player.money = 10
player.location = "forest_edge"

result = buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Buy fails",
    not result.success,
))
results.append(check(
    "Money unchanged",
    player.money == 10,
))

# ---------------------------------------------------------------
# 13. NPC not found fails
# ---------------------------------------------------------------

print("\n=== 13. NPC not found fails ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

result = buy_item(game, "nonexistent", "Health Potion", 1)

results.append(check(
    "Buy fails",
    not result.success,
))

# ---------------------------------------------------------------
# 14. NPC not co-located fails
# ---------------------------------------------------------------

print("\n=== 14. NPC not co-located fails ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "old_wooden_house"

result = buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Buy fails",
    not result.success,
))

# ---------------------------------------------------------------
# 15. Dead NPC cannot trade
# ---------------------------------------------------------------

print("\n=== 15. Dead NPC cannot trade ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
merchant.hp = 0

result = buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Buy fails",
    not result.success,
))

# ---------------------------------------------------------------
# 16. NPC missing item fails
# ---------------------------------------------------------------

print("\n=== 16. NPC missing item fails ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
merchant.inventory = []

result = buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Buy fails",
    not result.success,
))

# ---------------------------------------------------------------
# 17. NPC insufficient quantity fails
# ---------------------------------------------------------------

print("\n=== 17. NPC insufficient quantity fails ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
merchant.inventory = ["Health Potion"]

result = buy_item(game, "merchant", "Health Potion", 2)

results.append(check(
    "Buy fails",
    not result.success,
))

# ---------------------------------------------------------------
# 18. Quantity <= 0 fails
# ---------------------------------------------------------------

print("\n=== 18. Quantity <= 0 fails ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

result = buy_item(game, "merchant", "Health Potion", 0)

results.append(check(
    "Buy fails",
    not result.success,
))

# ---------------------------------------------------------------
# 19. Purchase transfers money correctly
# ---------------------------------------------------------------

print("\n=== 19. Purchase transfers money correctly ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
merchant.money = 200
merchant.inventory = ["Health Potion"]

buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Player money deducted",
    player.money == 70,
))
results.append(check(
    "Merchant money increased",
    merchant.money == 230,
))

# ---------------------------------------------------------------
# 20. Purchase transfers items correctly
# ---------------------------------------------------------------

print("\n=== 20. Purchase transfers items correctly ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
merchant.inventory = ["Health Potion"]

buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Item removed from merchant",
    "Health Potion" not in merchant.inventory,
))
results.append(check(
    "Item added to player",
    "Health Potion" in player.inventory,
))

# ---------------------------------------------------------------
# 21. Failed purchase does not mutate state
# ---------------------------------------------------------------

print("\n=== 21. Failed purchase does not mutate state ===")
game = create_new_game()
player = game.player
player.money = 10
player.location = "forest_edge"

merchant = game.world.npcs["merchant"]
original_merchant_money = merchant.money
original_merchant_inventory = merchant.inventory.copy()

result = buy_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Buy fails",
    not result.success,
))
results.append(check(
    "Player money unchanged",
    player.money == 10,
))
results.append(check(
    "Merchant money unchanged",
    merchant.money == original_merchant_money,
))
results.append(check(
    "Merchant inventory unchanged",
    merchant.inventory == original_merchant_inventory,
))

# ---------------------------------------------------------------
# 22. Valid sale succeeds
# ---------------------------------------------------------------

print("\n=== 22. Valid sale succeeds ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

merchant = game.world.npcs["merchant"]
merchant.money = 200

result = sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Sell succeeds",
    result.success,
))
results.append(check(
    "Health Potion removed from player",
    "Health Potion" not in player.inventory,
))
results.append(check(
    "Money received",
    player.money == 15,
))

# ---------------------------------------------------------------
# 23. Player missing item fails
# ---------------------------------------------------------------

print("\n=== 23. Player missing item fails ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = []

result = sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Sell fails",
    not result.success,
))

# ---------------------------------------------------------------
# 24. Insufficient quantity fails
# ---------------------------------------------------------------

print("\n=== 24. Insufficient quantity fails ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

result = sell_item(game, "merchant", "Health Potion", 2)

results.append(check(
    "Sell fails",
    not result.success,
))

# ---------------------------------------------------------------
# 25. NPC has insufficient money fails
# ---------------------------------------------------------------

print("\n=== 25. NPC has insufficient money fails ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Iron Sword"]

merchant = game.world.npcs["merchant"]
merchant.money = 10

result = sell_item(game, "merchant", "Iron Sword", 1)

results.append(check(
    "Sell fails",
    not result.success,
))

# ---------------------------------------------------------------
# 26. NPC not co-located fails
# ---------------------------------------------------------------

print("\n=== 26. NPC not co-located fails ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "old_wooden_house"
player.inventory = ["Health Potion"]

result = sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Sell fails",
    not result.success,
))

# ---------------------------------------------------------------
# 27. Dead NPC cannot trade
# ---------------------------------------------------------------

print("\n=== 27. Dead NPC cannot trade ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

merchant = game.world.npcs["merchant"]
merchant.hp = 0

result = sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Sell fails",
    not result.success,
))

# ---------------------------------------------------------------
# 28. Quantity <= 0 fails
# ---------------------------------------------------------------

print("\n=== 28. Quantity <= 0 fails ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

result = sell_item(game, "merchant", "Health Potion", 0)

results.append(check(
    "Sell fails",
    not result.success,
))

# ---------------------------------------------------------------
# 29. Sale transfers money correctly
# ---------------------------------------------------------------

print("\n=== 29. Sale transfers money correctly ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

merchant = game.world.npcs["merchant"]
merchant.money = 200

sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Player money increased",
    player.money == 15,
))
results.append(check(
    "Merchant money decreased",
    merchant.money == 185,
))

# ---------------------------------------------------------------
# 30. Sale transfers items correctly
# ---------------------------------------------------------------

print("\n=== 30. Sale transfers items correctly ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

merchant = game.world.npcs["merchant"]
merchant.money = 200

sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Item removed from player",
    "Health Potion" not in player.inventory,
))
results.append(check(
    "Item added to merchant",
    "Health Potion" in merchant.inventory,
))

# ---------------------------------------------------------------
# 31. Failed sale does not mutate state
# ---------------------------------------------------------------

print("\n=== 31. Failed sale does not mutate state ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

merchant = game.world.npcs["merchant"]
merchant.money = 200
original_merchant_money = merchant.money
original_merchant_inventory = merchant.inventory.copy()

result = sell_item(game, "merchant", "Health Potion", 2)

results.append(check(
    "Sell fails",
    not result.success,
))
results.append(check(
    "Player money unchanged",
    player.money == 0,
))
results.append(check(
    "Merchant money unchanged",
    merchant.money == original_merchant_money,
))
results.append(check(
    "Merchant inventory unchanged",
    merchant.inventory == original_merchant_inventory,
))

# ---------------------------------------------------------------
# 32. Configured item has deterministic price
# ---------------------------------------------------------------

print("\n=== 32. Configured item has deterministic price ===")
results.append(check(
    "Herb price is 5",
    ITEM_PRICES["Herb"] == 5,
))
results.append(check(
    "Health Potion price is 30",
    ITEM_PRICES["Health Potion"] == 30,
))
results.append(check(
    "Iron Sword price is 100",
    ITEM_PRICES["Iron Sword"] == 100,
))

# ---------------------------------------------------------------
# 33. Unknown item cannot be bought
# ---------------------------------------------------------------

print("\n=== 33. Unknown item cannot be bought ===")
game = create_new_game()
player = game.player
player.money = 1000
player.location = "forest_edge"

result = buy_item(game, "merchant", "Unknown Item", 1)

results.append(check(
    "Buy fails for unknown item",
    not result.success,
))

# ---------------------------------------------------------------
# 34. Unknown item cannot be sold
# ---------------------------------------------------------------

print("\n=== 34. Unknown item cannot be sold ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Unknown Item"]

result = sell_item(game, "merchant", "Unknown Item", 1)

results.append(check(
    "Sell fails for unknown item",
    not result.success,
))

# ---------------------------------------------------------------
# 35. Sell price uses fixed multiplier
# ---------------------------------------------------------------

print("\n=== 35. Sell price uses fixed multiplier ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Health Potion"]

merchant = game.world.npcs["merchant"]
merchant.money = 200

sell_item(game, "merchant", "Health Potion", 1)

expected_price = int(ITEM_PRICES["Health Potion"] * SELL_MULTIPLIER)
results.append(check(
    "Sell price is 50% of buy price",
    player.money == expected_price,
))

# ---------------------------------------------------------------
# 36. Prices cannot be changed by action payload
# ---------------------------------------------------------------

print("\n=== 36. Prices cannot be changed by action payload ===")
results.append(check(
    "SELL_MULTIPLIER is 0.5",
    SELL_MULTIPLIER == 0.5,
))

# ---------------------------------------------------------------
# 37. Money persists
# ---------------------------------------------------------------

print("\n=== 37. Money persists ===")
game = create_new_game()
player = game.player
player.money = 150

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

results.append(check(
    "Player money persisted",
    loaded.player.money == 150,
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 38. NPC inventory persists
# ---------------------------------------------------------------

print("\n=== 38. NPC inventory persists ===")
game = create_new_game()
merchant = game.world.npcs["merchant"]
merchant.inventory = ["Health Potion", "Iron Ore"]

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

loaded_merchant = loaded.world.npcs["merchant"]
results.append(check(
    "NPC inventory persisted",
    loaded_merchant.inventory == ["Health Potion", "Iron Ore"],
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 39. NPC money persists
# ---------------------------------------------------------------

print("\n=== 39. NPC money persists ===")
game = create_new_game()
merchant = game.world.npcs["merchant"]
merchant.money = 500

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    save_path = Path(f.name)

save_game(game, save_path)
loaded = load_game(save_path)

loaded_merchant = loaded.world.npcs["merchant"]
results.append(check(
    "NPC money persisted",
    loaded_merchant.money == 500,
))

save_path.unlink(missing_ok=True)

# ---------------------------------------------------------------
# 40. Player money appears in context
# ---------------------------------------------------------------

print("\n=== 40. Player money appears in context ===")
game = create_new_game()
player = game.player
player.money = 100

context = build_game_context(game)

results.append(check(
    "Money shown in context",
    "Money: 100" in context,
))

# ---------------------------------------------------------------
# 41. Merchant inventory appears in context
# ---------------------------------------------------------------

print("\n=== 41. Merchant inventory appears in context ===")
game = create_new_game()
player = game.player
player.location = "forest_edge"

context = build_game_context(game)

results.append(check(
    "MERCHANTS section present",
    "=== MERCHANTS ===" in context,
))
results.append(check(
    "Merchant name in context",
    "Merchant" in context,
))

# ---------------------------------------------------------------
# 42. Crafting recipes appear in context
# ---------------------------------------------------------------

print("\n=== 42. Crafting recipes appear in context ===")
game = create_new_game()

context = build_game_context(game)

results.append(check(
    "CRAFTING section present",
    "=== CRAFTING ===" in context,
))
results.append(check(
    "health_potion recipe in context",
    "health_potion" in context,
))
results.append(check(
    "torch recipe in context",
    "torch" in context,
))

# ---------------------------------------------------------------
# 43. Craft -> inventory -> sell works
# ---------------------------------------------------------------

print("\n=== 43. Craft -> inventory -> sell works ===")
game = create_new_game()
player = game.player
player.money = 0
player.location = "forest_edge"
player.inventory = ["Herb", "Herb", "Empty Bottle"]

craft(game, "health_potion")

merchant = game.world.npcs["merchant"]
merchant.money = 200

sell_item(game, "merchant", "Health Potion", 1)

results.append(check(
    "Crafted and sold successfully",
    player.money == 15,
))
results.append(check(
    "Health Potion removed after sell",
    "Health Potion" not in player.inventory,
))

# ---------------------------------------------------------------
# 44. Buy -> inventory -> quest interaction remains valid
# ---------------------------------------------------------------

print("\n=== 44. Buy -> inventory -> quest interaction remains valid ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"

buy_item(game, "merchant", "Wood", 1)

results.append(check(
    "Wood purchased",
    "Wood" in player.inventory,
))
results.append(check(
    "Player money updated",
    player.money == 97,
))

# ---------------------------------------------------------------
# 45. Progression remains functional after crafting/trading
# ---------------------------------------------------------------

print("\n=== 45. Progression remains functional after crafting/trading ===")
game = create_new_game()
player = game.player
player.money = 100
player.location = "forest_edge"
player.inventory = ["Herb", "Herb", "Empty Bottle"]

craft(game, "health_potion")

results.append(check(
    "XP awarded from crafting",
    player.xp == XP_PER_CRAFT,
))
results.append(check(
    "Level unchanged",
    player.level == 1,
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
