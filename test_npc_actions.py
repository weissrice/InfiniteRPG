import builtins
import json

from engine.world import create_new_game
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import npc_interact


def check(label, condition):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    return condition


results = []

system = SYSTEM_PROMPT
normalized = " ".join(system.split())

print("=== 0. Prompt contains NPC ACTION RULES ===")
results.append(check(
    "NPC ACTION RULES section present",
    "NPC ACTION RULES:" in system,
))
results.append(check(
    "NPC actions are optional proposals",
    "optional action proposals" in normalized,
))
results.append(check(
    "Only implemented NPC action types permitted",
    "Only explicitly implemented NPC action types are permitted" in normalized,
))
results.append(check(
    "Python validates and executes them",
    "Python validates each NPC action" in normalized,
))
results.append(check(
    "Subjective state grants no permission",
    "personality do NOT grant permission to mutate game state" in normalized,
))
results.append(check(
    "Never assume success without result",
    "Never assume an NPC action succeeded unless the action result" in normalized,
))
results.append(check(
    "NPC actions do not happen autonomously",
    "NPC actions do not happen autonomously" in normalized,
))
results.append(check(
    "Player actions omit actor",
    "For ordinary player actions, omit the \"actor\" field entirely" in system,
))
results.append(check(
    "Direction rule: player question uses no actor field",
    "Emit a PLAYER action with NO \"actor\" field"
    in normalized,
))
results.append(check(
    "Direction rule: Player → NPC JSON example has no actor",
    '"type": "interact", "target": "old_man", "topic": "where were you earlier?"'
    in normalized,
))
results.append(check(
    "Direction rule: NPC → player JSON example has actor",
    '"type": "interact", "actor": "old_man", "target": "Traveler",'
    in normalized
    and '"asking the traveler to stay downstairs"}' in normalized,
))
results.append(check(
    "Direction rule: NPC named in command is not the actor",
    "The NPC named inside the player's command is NOT the actor"
    in normalized,
))
results.append(check(
    "Direction rule: addressing by name means the player is speaker",
    "means the PLAYER is the speaker" in normalized,
))
results.append(check(
    "Direction rule: only use actor for NPC-initiated interaction",
    "Use \"actor\" only when the NPC itself initiates the interaction"
    in normalized,
))
results.append(check(
    "Valid-target rule: target must be player or another NPC present",
    "\"target\" must be the player or another NPC present at the current location"
    in normalized,
))
results.append(check(
    "Valid-target rule: never target the actor NPC itself",
    "Never target the actor NPC itself" in normalized,
))


class MockAI:
    def __init__(self, action):
        self.action = action
        self.prompts = []

    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        self.prompts.append(prompt)
        return json.dumps({
            "narration": "The Old Man speaks quietly.",
            "actions": [self.action],
        })

    def close(self):
        pass


def run(action, game=None):
    engine = GameEngine()
    if game is not None:
        engine.game = game
    engine.ai = MockAI(action)
    old = builtins.input
    builtins.input = lambda _="": ""
    try:
        result = engine.process_input("test command")
        return result
    finally:
        builtins.input = old


print("\n=== 1. Existing player interact still works (no actor) ===")
engine = GameEngine()
engine.ai = MockAI({
    "type": "interact",
    "target": "old_man",
    "topic": "the upstairs door",
})
g = engine.game
old = builtins.input
builtins.input = lambda _="": ""
try:
    result = engine.process_input("Ask the Old Man about the upstairs door.")
finally:
    builtins.input = old
results.append(check(
    "Player interact succeeds",
    result["success"] is True
    and result["actions"][0]["success"] is True,
))
results.append(check(
    "Player interact records question memory",
    "The player asked Old Man about the upstairs door." in g.world.npcs["old_man"].memory,
))

print("\n=== 2. NPC interact with a valid NPC actor is accepted ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
result = run({
    "type": "interact",
    "actor": "old_man",
    "target": "Traveler",
    "topic": "asking the traveler to stay downstairs",
}, game=game)
results.append(check(
    "NPC interact succeeds",
    result["success"] is True
    and result["actions"][0]["success"] is True,
))
results.append(check(
    "NPC interact result carries actor",
    result["actions"][0]["data"].get("actor") == "old_man",
))

print("\n=== 3. NPC actor must exist ===")
game = create_new_game()
result = run({
    "type": "interact",
    "actor": "ghost",
    "target": "Traveler",
    "topic": "anything",
}, game=game)
results.append(check(
    "Unknown actor rejected",
    result["actions"][0]["success"] is False,
))
results.append(check(
    "No memory recorded for unknown actor",
    len(game.world.npcs["old_man"].memory) == 0,
))

print("\n=== 4. NPC actor must be an NPC ===")
game = create_new_game()
result = run({
    "type": "interact",
    "actor": "Traveler",
    "target": "Traveler",
    "topic": "anything",
}, game=game)
results.append(check(
    "Player-name actor rejected (not an NPC)",
    result["actions"][0]["success"] is False,
))

print("\n=== 5. NPC must be at the current location ===")
game = create_new_game()
game.player.location = "forest_edge"
game.world.locations["forest_edge"].npcs = []
result = run({
    "type": "interact",
    "actor": "old_man",
    "target": "Traveler",
    "topic": "anything",
}, game=game)
results.append(check(
    "NPC not at current location rejected",
    result["actions"][0]["success"] is False,
))

print("\n=== 6-11. NPCs cannot use player action types ===")
banned = [
    ("move", {"type": "move", "destination": "kitchen"}),
    ("take_item", {"type": "take_item", "item": "Rusty Key"}),
    ("drop_item", {"type": "drop_item", "item": "Rusty Key"}),
    ("use_item", {"type": "use_item", "item": "Rusty Key", "target": "locked_upstairs_door"}),
    ("open", {"type": "open", "target": "locked_upstairs_door"}),
    ("wait", {"type": "wait", "minutes": 10}),
]
for label, action in banned:
    game = create_new_game()
    action = dict(action)
    action["actor"] = "old_man"
    result = run(action, game=game)
    results.append(check(
        f"NPC cannot {label}",
        result["actions"][0]["success"] is False,
    ))

print("\n=== 12. Invalid NPC actions do not mutate game state ===")
game = create_new_game()
door = game.world.interactables["locked_upstairs_door"]
before = (
    game.player.location,
    list(game.player.inventory),
    door.state,
    door.used,
    door.discovered,
    game.world.time,
    list(game.world.npcs["old_man"].memory),
    list(game.world.locations["old_wooden_house"].items),
)
run({
    "type": "move",
    "actor": "old_man",
    "destination": "kitchen",
}, game=game)
run({
    "type": "use_item",
    "actor": "old_man",
    "item": "Rusty Key",
    "target": "locked_upstairs_door",
}, game=game)
run({
    "type": "open",
    "actor": "old_man",
    "target": "locked_upstairs_door",
}, game=game)
run({
    "type": "take_item",
    "actor": "old_man",
    "item": "Rusty Key",
}, game=game)
after = (
    game.player.location,
    list(game.player.inventory),
    door.state,
    door.used,
    door.discovered,
    game.world.time,
    list(game.world.npcs["old_man"].memory),
    list(game.world.locations["old_wooden_house"].items),
)
results.append(check(
    "State identical after invalid NPC actions",
    before == after,
))

print("\n=== 13. NPC interaction records correct event memory ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
result = run({
    "type": "interact",
    "actor": "old_man",
    "target": "Traveler",
    "topic": "staying downstairs",
}, game=game)
results.append(check(
    "Actor-specific memory wording",
    "Old Man spoke to the player about staying downstairs." in old_man.memory,
))
results.append(check(
    "No 'player asked' wording for NPC actor",
    not any("The player asked Old Man" in m for m in old_man.memory),
))

print("\n=== 14. Existing conversation memory behavior remains intact ===")


class QuotingAI:
    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        return json.dumps({
            "narration": (
                "The Old Man looks up from the fire. "
                "\"The upstairs door is old and has a lock.\""
            ),
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "what he knows about the upstairs door",
            }],
        })

    def close(self):
        pass


engine = GameEngine()
engine.ai = QuotingAI()
g = engine.game
old_man = g.world.npcs["old_man"]
old = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("Ask the Old Man what he knows about the upstairs door.")
finally:
    builtins.input = old
results.append(check(
    "Player question memory still recorded",
    "The player asked Old Man about what he knows about the upstairs door." in old_man.memory,
))
results.append(check(
    "Player response summary still recorded",
    any(m.startswith("Old Man told the player that") for m in old_man.memory),
))

print("\n=== 15. npc_interact unit behavior ===")
game = create_new_game()
old_man = game.world.npcs["old_man"]
res = npc_interact(game, "old_man", "the traveler", "staying downstairs")
results.append(check(
    "npc_interact direct call succeeds",
    res.success is True and res.data["actor"] == "old_man",
))
results.append(check(
    "Direct call records memory with 'the player' label",
    "Old Man spoke to the player about staying downstairs." in old_man.memory,
))
res = npc_interact(game, "old_man", "nonexistent_entity", "anything")
results.append(check(
    "Invalid target rejected",
    res.success is False,
))
res = npc_interact(game, "ghost", "Traveler", "anything")
results.append(check(
    "Unknown actor rejected at unit level",
    res.success is False,
))

print("\n=== 16. Manual-test repros: player commands naming an NPC must not flip actor ===")


class CaptureAI:
    def __init__(self):
        self.sent = []

    def ask(self, prompt, system, max_tokens, temperature, json_mode):
        self.sent.append((prompt, system))
        return json.dumps({
            "narration": "The Old Man nods.",
            "actions": [{
                "type": "interact",
                "target": "old_man",
                "topic": "anything",
            }],
        })

    def close(self):
        pass


for player_input in [
    "where were you earlier?",
    "tell old man I'm going upstairs",
]:
    engine = GameEngine()
    engine.ai = CaptureAI()
    old = builtins.input
    builtins.input = lambda _="": ""
    try:
        engine.process_input(player_input)
    finally:
        builtins.input = old
    sent_system = " ".join(engine.ai.sent[-1][1].split())
    results.append(check(
        f"No-actor rule carried for repro '{player_input}'",
        "The NPC named inside the player's command is NOT the actor"
        in sent_system,
    ))
    results.append(check(
        f"Player → NPC mapping carried for repro '{player_input}'",
        'Emit a PLAYER action with NO "actor" field'
        in sent_system
        and '"type": "interact", "target": "old_man",' in sent_system,
    ))
    results.append(check(
        f"Address-by-name = player speaker carried for repro '{player_input}'",
        "means the PLAYER is the speaker" in sent_system,
    ))

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
