import builtins
import json
import socket

from engine.world import create_new_game
from engine.game import SYSTEM_PROMPT, GameEngine
from engine.actions import wait, move_player
from engine.ai import AIClient


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    if detail and not condition:
        print(f"    detail: {detail}")
    return condition


def server_available(host="127.0.0.1", port=1337, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


results = []

if not server_available():
    print("SKIP: AI server not running at http://127.0.0.1:1337")
    print("      Real-model regression cannot run; unit suite covers the prompt rules.")
    print()
    print("RESULT: 0/0 checks passed (skipped)")
    raise SystemExit(0)


class RecordingAI(AIClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    def ask(self, prompt, system=None, max_tokens=2048, temperature=0.5, json_mode=False):
        raw = super().ask(
            prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
        self.calls.append({"system": system, "prompt": prompt, "raw": raw})
        return raw

    def close(self):
        super().close()


def setup():
    game = create_new_game()
    wait(game, 360)                 # 12:00 -> 18:00; Old Man moves to Kitchen
    move_player(game, "kitchen")    # player follows him there
    return game


def parse(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"__parse_error__": str(exc), "raw": raw}


print("=== 1. Automated world-interaction sequence (no manual typing) ===")
engine = GameEngine()
engine.game = setup()
game = engine.game
old_man = game.world.npcs["old_man"]
pot = game.world.interactables["kitchen_stew_pot"]
results.append(check(
    "Old Man is in the Kitchen at 18:00",
    old_man.location == "kitchen"
    and game.player.location == "kitchen"
    and game.world.time == "18:00",
    f"old_man={old_man.location!r} player={game.player.location!r} "
    f"time={game.world.time!r}",
))
results.append(check(
    "Python bound the activity to the Stew Pot",
    old_man.current_activity_object == "kitchen_stew_pot",
    f"current_activity_object={old_man.current_activity_object!r}",
))
results.append(check(
    "Stew Pot is at the kitchen in default state",
    pot.location == "kitchen"
    and pot.state == "default"
    and pot.used is False
    and pot.discovered is False,
    f"state={pot.state!r} used={pot.used!r} discovered={pot.discovered!r}",
))

ai = RecordingAI()
engine.ai = ai

print("\n=== 2. Player->NPC grounding on the activity object ===")
old_input = builtins.input
builtins.input = lambda _="": ""
try:
    engine.process_input("ask old man: what are you doing with the stew pot?")
finally:
    builtins.input = old_input

call = ai.calls[-1]
parsed = parse(call["raw"])
raw_ok = "__parse_error__" not in parsed
actions = parsed.get("actions", []) if raw_ok else []
has_actor = False
action_type = None
action_target = None
for action in actions:
    if "actor" in action:
        has_actor = True
    action_type = action.get("type")
    action_target = action.get("target")
narration = parsed.get("narration", "") if raw_ok else call["raw"]

results.append(check(
    "Player question emits a PLAYER action (no actor field)",
    raw_ok and actions and not has_actor,
    f"raw={call['raw'][:400]}",
))
results.append(check(
    "Player action is an interact targeting the Old Man",
    raw_ok and actions
    and action_type == "interact"
    and action_target == "old_man",
    f"type={action_type!r} target={action_target!r}",
))
results.append(check(
    "Narration is grounded in Current Activity + Activity Object",
    any(
        keyword in narration.lower()
        for keyword in (
            "stew", "pot", "meal", "preparing", "cook", "stir",
            "simmer", "dinner",
        )
    ),
    f"narration={narration!r}",
))
results.append(check(
    "Narration includes a spoken reply",
    '"' in narration,
    f"narration={narration!r}",
))
results.append(check(
    "Request carried the Activity Object binding",
    "Activity Object: Stew Pot (id: kitchen_stew_pot)" in call["prompt"],
))
results.append(check(
    "Request carried the Used by line",
    "Used by: Old Man" in call["prompt"],
))

print("\n=== 3. NPC-initiated interact_object preserves direction rules ===")
initiation_inputs = [
    "the old man moves to the stew pot on his own and stirs it",
    "the old man gets up and stirs the stew pot",
    "of his own accord, the old man goes back to stirring the stew pot",
]

proposed = False
illegal_proposed = False
executed_ok = False
executed_target = None
allowed_ok = True

for player_input in initiation_inputs:
    old_input = builtins.input
    builtins.input = lambda _="": ""
    try:
        result = engine.process_input(player_input)
    finally:
        builtins.input = old_input

    call = ai.calls[-1]
    parsed = parse(call["raw"])
    actions = parsed.get("actions", []) if "__parse_error__" not in parsed else []

    for action in actions:
        if action.get("actor"):
            if action.get("type") not in {"interact", "interact_object"}:
                allowed_ok = False
            if action.get("type") == "interact_object":
                if action.get("target") == "kitchen_stew_pot":
                    proposed = True
                else:
                    illegal_proposed = True

    for item in result.get("actions", []):
        requested = item.get("requested", {})
        if (
            requested.get("type") == "interact_object"
            and item.get("success") is True
        ):
            executed_ok = True
            executed_target = item.get("data", {}).get("target")

results.append(check(
    "NPC-initiated actions stay within allowed types",
    allowed_ok,
    f"actions={actions!r}",
))
results.append(check(
    "AI proposed an NPC interact_object on the activity object",
    proposed,
    "No initiation input produced an NPC interact_object this run "
    "(real-model nondeterminism); unit suite covers the execution path.",
))
results.append(check(
    "No illegal interact_object target proposed",
    not illegal_proposed,
    f"illegal_proposed={illegal_proposed!r}",
))
results.append(check(
    "Python validated and executed the NPC object interaction",
    executed_ok and executed_target == "kitchen_stew_pot",
    f"executed={executed_ok!r} target={executed_target!r}",
))
results.append(check(
    "Interaction effect recorded on the NPC",
    "Old Man used the Stew Pot." in old_man.memory,
    f"memory={old_man.memory!r}",
))
results.append(check(
    "Interaction effect recorded on the object",
    "Old Man used this." in pot.memory,
    f"memory={pot.memory!r}",
))
results.append(check(
    "AI never mutated the activity object binding",
    old_man.current_activity_object == "kitchen_stew_pot",
    f"current_activity_object={old_man.current_activity_object!r}",
))
results.append(check(
    "AI never changed the object's authoritative state",
    pot.state == "default",
    f"state={pot.state!r}",
))

print("\n=== 4. Real-model request carried the world-interaction grounding ===")
sent_system = " ".join(ai.calls[1]["system"].split())
results.append(check(
    "NPC WORLD INTERACTION RULES carried in real request",
    "NPC WORLD INTERACTION RULES:" in ai.calls[1]["system"]
    and "cannot use interact_object" in sent_system,
))

print("\n--- Real-model raw responses (for investigation) ---")
for i, player_input in enumerate(
    ["ask old man: what are you doing with the stew pot?"]
    + initiation_inputs,
    start=1,
):
    print(f"\nINPUT {i}: {player_input!r}")
    print(ai.calls[i - 1]["raw"])

engine.close()

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
