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


print("=== 1. Automated activity sequence (no manual typing) ===")
engine = GameEngine()
engine.game = setup()
game = engine.game
old_man = game.world.npcs["old_man"]
results.append(check(
    "Old Man moved to Kitchen and memory recorded",
    old_man.location == "kitchen"
    and "Old Man went to Kitchen." in old_man.memory,
    f"location={old_man.location!r} memory={old_man.memory!r}",
))
results.append(check(
    "Player is in the Kitchen with Old Man at 18:00",
    game.player.location == "kitchen"
    and game.world.time == "18:00",
    f"player.location={game.player.location!r} time={game.world.time!r}",
))
results.append(check(
    "Python set the 18:00 current activity",
    old_man.current_activity == "preparing the evening meal",
    f"current_activity={old_man.current_activity!r}",
))

ai = RecordingAI()
engine.ai = ai

inputs = [
    "ask old man: what are you doing?",
    "ask old man: what do you usually do around here?",
]

print("\n=== 2. Real-model activity questions ===")

for player_input in inputs:
    old_input = builtins.input
    builtins.input = lambda _="": ""
    try:
        engine.process_input(player_input)
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

    narration = call["raw"]
    try:
        narration = parsed.get("narration", "")
    except AttributeError:
        pass

    results.append(check(
        f"[{player_input!r}] emitted a PLAYER action (no actor field)",
        raw_ok and actions and not has_actor,
        f"raw={call['raw'][:400]}",
    ))
    results.append(check(
        f"[{player_input!r}] interact targeting the Old Man",
        raw_ok and actions
        and action_type == "interact"
        and action_target == "old_man",
        f"type={action_type!r} target={action_target!r}",
    ))
    results.append(check(
        f"[{player_input!r}] narration includes a spoken reply",
        '"' in narration,
        f"narration={narration!r}",
    ))

first = ai.calls[0]
results.append(check(
    "['what are you doing?'] narration reflects the current activity",
    any(
        keyword in first["raw"].lower()
        for keyword in (
            "preparing", "meal", "cook", "stir", "pot",
            "kitchen", "dinner", "supper",
        )
    ),
    f"narration={first['raw']!r}",
))

second = ai.calls[1]
results.append(check(
    "['what do you usually do?'] narration does not deny the kitchen visit",
    "haven't been" not in second["raw"].lower()
    and "haven't gone" not in second["raw"].lower()
    and "been here all along" not in second["raw"].lower(),
    f"narration={second['raw']!r}",
))

results.append(check(
    "AI never mutated the authoritative current activity",
    old_man.current_activity == "preparing the evening meal",
    f"current_activity={old_man.current_activity!r}",
))

print("\n=== 3. Real-model request carried the activity grounding ===")
sent_system = " ".join(first["system"].split())
results.append(check(
    "RULES section carried in real request",
    "RULES:" in first["system"]
    and "answer from the Current Activity in first person"
    in sent_system,
))
results.append(check(
    "Current Activity present in real context",
    "Current Activity: preparing the evening meal" in first["prompt"],
))
results.append(check(
    "Activity marked authoritative in real context",
    "(authoritative current state)" in first["prompt"],
))
results.append(check(
    "Schedule + descriptive Routine still present in real context",
    "18:00 → Kitchen" in first["prompt"]
    and "Tends the fire" in first["prompt"],
))

print("\n--- Real-model raw responses (for investigation) ---")
for i, player_input in enumerate(inputs, start=1):
    print(f"\nINPUT {i}: {player_input!r}")
    print(ai.calls[i - 1]["raw"])

engine.close()

print()
print(f"RESULT: {sum(results)}/{len(results)} checks passed")
