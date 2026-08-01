import json
from typing import Any

from .save import save_game, load_game
from .actions import (
    drop_item,
    inspect,
    interact,
    move_player,
    open_interactable,
    take_item,
    use_item,
    wait,
)
from .ai import AIClient
from .context import build_game_context
from .state import GameState
from .world import create_new_game


SYSTEM_PROMPT = """
You are the action interpreter for an interactive RPG.

You are a fast action parser.
Do not perform extended reasoning.
Do not deliberate internally.
Immediately identify the player's intended action and output the JSON.

Your job is to convert the player's command into a JSON action.

Return ONLY valid JSON.
Do not write explanations.
Do not write reasoning.
Do not use Markdown.

Use exactly:

{
  "narration": "Short description of what happens.",
  "actions": [
    {
      "type": "move",
      "destination": "location_id_or_direction"
    }
  ]
}

Valid action types:

move
take_item
drop_item
inspect
interact
use_item
open
wait

ACTION FORMATS:

move:
{
  "type": "move",
  "destination": "north"
}

take_item:
{
  "type": "take_item",
  "item": "Rusty Key"
}

drop_item:
{
  "type": "drop_item",
  "item": "Rusty Key"
}

inspect:
{
  "type": "inspect",
  "item": "door"
}

interact:
{
  "type": "interact",
  "target": "door"
}

use_item:
{
  "type": "use_item",
  "item": "Rusty Key",
  "target": "door"
}

open:
{
  "type": "open",
  "target": "door"
}

wait:
{
  "type": "wait",
  "minutes": 10
}

IMPORTANT MOVEMENT RULES:

- Only use entities that exist in the supplied game state.
- If the player names an EXISTING location or an EXISTING exit, use it.
- If the player gives a direction such as north, south, east, west,
  northeast, northwest, southeast, southwest, up, or down, preserve
  that direction exactly as the destination if that direction is not
  already an exit.
- NEVER replace an unexplored direction with a different existing
  location.
- NEVER assume that a direction corresponds to a particular location
  unless the current game state's exits say so.
- If a requested direction does not exist in the current exits,
  return that direction as the destination anyway.
- Python will determine whether that direction already exists or
  whether a new location must be generated.
- For phrases such as "go back", "return", "go inside", "leave",
  "go outside", etc., resolve the meaning using the available exits
  in the current location.
- Do not invent existing location IDs.
- Do not redirect the player to another location simply because it
  seems geographically reasonable.

ITEM RULES:

- Only use items that exist in the player's inventory for use_item.
- Only use items that exist in the current location for take_item.
- Only use items that exist in the player's inventory for drop_item.
- When the player says "use X on Y", use X as the item and Y as
  the target.
- When the player says "use X" without a target, leave "target"
  as an empty string.
- Do not invent item names.

INTERACTION RULES:

- Only interact with objects that exist in the supplied game state.
- Use "inspect" when the player wants to look at, examine, investigate,
  study, or check something.
- Use "interact" when the player wants to manipulate or interact with
  an object without explicitly using an inventory item.
- Use "open" when the player wants to open a door, container, or other
  openable object.
- Do not invent object IDs or names.
- Object names may describe their original/default state (e.g., "Locked Door").
  ALWAYS trust the explicit CURRENT STATE field over the object's name or description.
  If CURRENT STATE says "unlocked", the object is unlocked regardless of its name.
  If CURRENT STATE says "open", the object is open and can be passed through.

DOOR STATE MACHINE:
- locked → cannot open, requires key or unlocking
- unlocked → can be opened with "open" action
- open → can be passed through (use "move" with the door's direction)

OTHER RULES:

- Only use entities that exist in the supplied game state.
- Python will validate and execute the action.
- Keep narration to one short sentence.
- Encourage creative interpretation of the player's intent while
  remaining consistent with the actual game state.
- Return the JSON immediately.
"""


class GameEngine:
    """Main coordinator for the Infinite RPG."""

    def __init__(self):
        self.game: GameState = create_new_game()
        self.ai = AIClient()

    def save(self):
        """Save the current game."""
        save_game(self.game)

    def load(self):
        """Load a saved game."""
        self.game = load_game()

    def close(self):
        """Close the AI client."""
        self.ai.close()

    def process_input(self, player_input: str) -> dict[str, Any]:
        """Process one player command."""

        context = build_game_context(self.game)

        prompt = f"""
CURRENT GAME STATE:

{context}

PLAYER ACTION:

{player_input}

Interpret the player's action and return the required JSON.
"""

        response = self.ai.ask(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.5,
            json_mode=True,
        )

        
        with open("debug_ai.txt", "w", encoding="utf-8") as debug_file:
            debug_file.write(response)

        print()
        print("DEBUG AI RESPONSE:")
        print(response)
        print()
        input("Press ENTER to continue...")



        result = self._parse_response(response)



        if result is None:
            return {
                "success": False,
                "narration": (
                    "The world seems to hesitate for a moment. "
                    "Something went wrong while interpreting your action."
                ),
                "actions": [],
            }

        applied_actions = []

        for action in result.get("actions", []):
            action_result = self._execute_action(action)

            applied_actions.append(
                {
                    "requested": action,
                    "success": action_result.success,
                    "message": action_result.message,
                    "data": action_result.data,
                }
            )

        
        print()
        print("DEBUG DOOR STATE:")

        for object_id, obj in self.game.world.interactables.items():
            print(
                f"{object_id}: "
                f"state={obj.state}, "
                f"used={obj.used}, "
                f"discovered={obj.discovered}"
            )

        print()

        
        narration = result.get(
            "narration",
            "Nothing happens.",
        )

        self.game.last_narration = narration

        return {
            "success": True,
            "narration": narration,
            "actions": applied_actions,
        }


    def _parse_response(
        self,
        response: str,
    ) -> dict[str, Any] | None:
        """Parse the AI's JSON response."""

        try:
            parsed = json.loads(response)

            if not isinstance(parsed, dict):
                return None

            if "narration" not in parsed:
                parsed["narration"] = ""

            if "actions" not in parsed:
                parsed["actions"] = []

            return parsed

        except json.JSONDecodeError:
            return None

    def _execute_action(
        self,
        action: dict[str, Any],
    ):
        """Execute one AI-requested action."""

        action_type = action.get("type")

        if action_type == "move":
            return move_player(
                self.game,
                action.get("destination", ""),
                self.ai,
            )

        if action_type == "take_item":
            return take_item(
                self.game,
                action.get("item", ""),
            )

        if action_type == "drop_item":
            return drop_item(
                self.game,
                action.get("item", ""),
            )

        if action_type == "inspect":
            return inspect(
                self.game,
                action.get("item", ""),
            )

        if action_type == "interact":
            return interact(
                self.game,
                action.get("target", ""),
            )

        if action_type == "use_item":
            print()
            print("DEBUG: EXECUTING USE_ITEM")
            print(f"Item: {action.get('item', '')}")
            print(f"Target: {action.get('target', '')}")
            print()

            return use_item(
                self.game,
                action.get("item", ""),
                action.get("target", ""),
            )

        if action_type == "open":
            return open_interactable(
                self.game,
                action.get("target", ""),
                self.ai,
            )

        if action_type == "wait":
            return wait(
                self.game,
                int(action.get("minutes", 10)),
            )

        return type(
            "UnknownActionResult",
            (),
            {
                "success": False,
                "message": f"Unknown action type: {action_type}",
                "data": {},
            },
        )()