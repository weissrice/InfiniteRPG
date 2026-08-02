import os
from pathlib import Path

from engine.world import create_new_game
from engine.context import build_game_context
from engine.game import SYSTEM_PROMPT
from engine.actions import (
    wait,
    move_player,
    npc_interact,
)
from engine.save import save_game, load_game


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    if detail and not condition:
        print(f"    detail: {detail}")
    return condition


def kitchen_evening():
    game = create_new_game()
    wait(game, 360)
    move_player(game, "kitchen")
    return game


def edges(game):
    om = game.world.npcs["old_man"]
    sa = game.world.npcs["sarah"]
    return {
        "om->sa": om.relationships.get("Sarah"),
        "sa->om": sa.relationships.get("Old Man"),
    }


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt - NPC RELATIONSHIP EVOLUTION RULES ===")
results.append(check(
    "NPC RELATIONSHIP EVOLUTION RULES section present",
    "NPC RELATIONSHIP EVOLUTION RULES:" in system,
))
results.append(check(
    "AI never chooses, emits, or predicts scores",
    "The AI never chooses, emits, or predicts these scores" in normalized
    or "never chooses, emits, or predicts" in normalized,
))
results.append(check(
    "AI must not narrate a mechanism for change",
    "without narrating the change itself" in normalized,
))
results.append(check(
    "Python remains authoritative",
    "Python/game state remains authoritative" in normalized,
))

print("\n=== 1. Seed values and directionality ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
results.append(check(
    "Seeded directional edges present and asymmetric",
    old_man.relationships.get("Sarah") == 3
    and sarah.relationships.get("Old Man") == 10,
    f"edges={edges(game)!r}",
))

print("\n=== 2. A genuinely new NPC->NPC conversation advances both edges +1 ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "sarah", "the meal")
results.append(check(
    "Conversation succeeded",
    res.success is True,
))
results.append(check(
    "Old Man -> Sarah edge gained exactly +1",
    old_man.relationships.get("Sarah") == 4,
))
results.append(check(
    "Sarah -> Old Man edge gained exactly +1",
    sarah.relationships.get("Old Man") == 11,
))
results.append(check(
    "No other relationship edges appeared",
    set(old_man.relationships) == {"Sarah", "Traveler"}
    and set(sarah.relationships) == {"Old Man", "Traveler"},
    f"old_man={sorted(old_man.relationships)!r} "
    f"sarah={sorted(sarah.relationships)!r}",
))
results.append(check(
    "relationship_update datum carries delta, target, and new scores",
    res.data.get("relationship_update") == {
        "delta": 1,
        "target": "Sarah",
        "actor_score": 4,
        "target_score": 11,
    },
))

print("\n=== 3. Repeating the exact same event is gated by the dedupe ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the evening meal")
res2 = npc_interact(game, "old_man", "sarah", "the evening meal")
results.append(check(
    "Second identical conversation still succeeds",
    res2.success is True,
))
results.append(check(
    "No additional relationship delta on the repeat",
    old_man.relationships.get("Sarah") == 4
    and sarah.relationships.get("Old Man") == 11,
    f"edges={edges(game)!r}",
))
results.append(check(
    "No relationship_update datum on the repeat",
    res2.data.get("relationship_update") is None,
))

print("\n=== 4. Different topics count as separate events ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the stew")
npc_interact(game, "old_man", "sarah", "the weather")
results.append(check(
    "Each novel topic applied exactly +1 (2 topics -> +2)",
    old_man.relationships.get("Sarah") == 5
    and sarah.relationships.get("Old Man") == 12,
    f"edges={edges(game)!r}",
))

print("\n=== 5. Reverse initiator, same topic: distinct event ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the kitchen")
npc_interact(game, "sarah", "old_man", "the kitchen")
results.append(check(
    "Both directions advanced independently (+1 each)",
    old_man.relationships.get("Sarah") == 5
    and sarah.relationships.get("Old Man") == 12,
    f"edges={edges(game)!r}",
))

print("\n=== 6. Bounds clamp at -100 / +100 ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
old_man.relationships["Sarah"] = 99
sarah.relationships["Old Man"] = -99
npc_interact(game, "old_man", "sarah", "topic a")
npc_interact(game, "old_man", "sarah", "topic b")
npc_interact(game, "old_man", "sarah", "topic c")
results.append(check(
    "Score clamps at the upper bound",
    old_man.relationships.get("Sarah") == 100,
    f"om->sa={old_man.relationships.get('Sarah')}",
))
results.append(check(
    "Score clamps at the lower bound",
    sarah.relationships.get("Old Man") == -96,
    f"sa->om={sarah.relationships.get('Old Man')}",
))

print("\n=== 7. Rejections never touch relationships or memory ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
res = npc_interact(game, "old_man", "old_man", "the meal")
results.append(check(
    "Self-target rejected",
    res.success is False,
))
res = npc_interact(game, "ghost", "sarah", "the meal")
results.append(check(
    "Unknown actor rejected",
    res.success is False,
))
before_mem_om = list(old_man.memory)
before_mem_sa = list(sarah.memory)
before_edges = edges(game)
results.append(check(
    "All rejections left relationships untouched",
    edges(game) == before_edges,
    f"edges={edges(game)!r}",
))
results.append(check(
    "Rejected memory untouched",
    list(old_man.memory) == before_mem_om
    and list(sarah.memory) == before_mem_sa,
))

print("\n=== 7b. Empty-topic conversations are still distinct events ===")
res = npc_interact(game, "old_man", "sarah", "")
results.append(check(
    "Empty topic still succeeds",
    res.success is True,
))
results.append(check(
    "Empty-topic event applied exactly +1 (entry-level gate)",
    old_man.relationships.get("Sarah") == 4
    and sarah.relationships.get("Old Man") == 11,
    f"edges={edges(game)!r}",
))
res = npc_interact(game, "old_man", "sarah", "   ")
results.append(check(
    "Whitespace-only topic dedupes against the empty-topic entry",
    old_man.relationships.get("Sarah") == 4
    and sarah.relationships.get("Old Man") == 11,
    f"edges={edges(game)!r}",
))

print("\n=== 8. Player edges never change ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
res = npc_interact(game, "old_man", "traveler", "the meal")
results.append(check(
    "NPC -> player succeeds",
    res.success is True,
))
results.append(check(
    "NPC -> player produces no relationship_update",
    res.data.get("relationship_update") is None,
))
results.append(check(
    "Traveler edge untouched by NPC -> player dialogue",
    old_man.relationships.get("Traveler") == 10,
    f"om->Traveler={old_man.relationships.get('Traveler')}",
))
results.append(check(
    "NPC edges untouched by NPC -> player dialogue",
    old_man.relationships.get("Sarah") == 3,
    f"om->sa={old_man.relationships.get('Sarah')}",
))

print("\n=== 9. Atomicity: one failure leaves every dimension intact ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "sarah", "old_man", "the meal")
before_mem_om = list(old_man.memory)
before_mem_sa = list(sarah.memory)
before_edges = edges(game)
sarah.location = "old_wooden_house"
from_location = game.world.locations["kitchen"]
from_location.npcs.remove("sarah")
game.world.locations["old_wooden_house"].npcs.append("sarah")
res = npc_interact(game, "old_man", "sarah", "the meal")
results.append(check(
    "Interrupted action failed cleanly",
    res.success is False,
))
results.append(check(
    "No memory written on the failed action",
    list(old_man.memory) == before_mem_om
    and list(sarah.memory) == before_mem_sa,
))
results.append(check(
    "No relationship delta on the failed action",
    edges(game) == before_edges,
    f"edges={edges(game)!r}",
))

print("\n=== 10. Save/load persists evolved scores; context renders them ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
sarah = game.world.npcs["sarah"]
npc_interact(game, "old_man", "sarah", "the meal")
npc_interact(game, "sarah", "old_man", "the meal")
path = Path(os.environ.get("TEMP", ".")) / "test_relationship_evolution.json"
save_game(game, path)
loaded = load_game(path)
try:
    path.unlink()
except OSError:
    pass
loaded_old = loaded.world.npcs["old_man"]
loaded_sa = loaded.world.npcs["sarah"]
results.append(check(
    "Evolved scores persisted through save/load",
    loaded_old.relationships.get("Sarah") == 5
    and loaded_sa.relationships.get("Old Man") == 12,
    f"loaded edges={edges(loaded)!r}",
))
ctx = build_game_context(loaded)
results.append(check(
    "Evolved scores rendered into the context",
    "- Sarah: 5" in ctx and "- Old Man: 12" in ctx,
    f"ctx snippet={ctx[ctx.find('Relationships'):ctx.find('Relationships') + 400]!r}",
))

print("\n=== 11. The old player-directed relationship model is untouched ===")
game = kitchen_evening()
old_man = game.world.npcs["old_man"]
npc_interact(game, "old_man", "traveler", "hello")
npc_interact(game, "old_man", "traveler", "hello")
npc_interact(game, "old_man", "traveler", "goodbye")
results.append(check(
    "Repeated player-directed dialogue changes nothing at all",
    old_man.relationships.get("Traveler") == 10
    and old_man.memory.count("Old Man spoke to the player about hello.") == 1
    and old_man.memory.count("Old Man spoke to the player about goodbye.") == 1
    and len(old_man.memory) == 4,
    f"Traveler={old_man.relationships.get('Traveler')} "
    f"mem={old_man.memory!r}",
))

fails = [r for r in results if not r]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
raise SystemExit(1 if fails else 0)
