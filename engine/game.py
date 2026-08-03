import json
from pathlib import Path
from typing import Any

from .save import save_game, load_game
from .actions import (
    drop_item,
    inspect,
    interact,
    move_player,
    npc_interact,
    npc_interact_object,
    open_interactable,
    record_conversation_response,
    take_item,
    use_item,
    wait,
)
from .ai import AIClient
from .context import build_game_context
from .state import GameState
from .world import create_new_game



_PROMPT_FILE = Path(__file__).resolve().parent.parent / "assets" / "system_prompt.txt"


def _load_system_prompt() -> str:
    """Load the system prompt from the external resource file."""
    return _PROMPT_FILE.read_text(encoding="utf-8")


SYSTEM_PROMPT = _load_system_prompt()


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
        
        narration = result.get(
            "narration",
            "Nothing happens.",
        )

        for action in result.get("actions", []):
            if action.get("type") == "interact" and not action.get("actor"):
                topic = action.get("topic", "")

                if topic.strip():
                    record_conversation_response(
                        self.game,
                        action.get("target", ""),
                        narration,
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
        actor = action.get("actor")

        if actor:
            return self._execute_npc_action(action)

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
                action.get("topic", ""),
            )

        if action_type == "use_item":
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

    def _execute_npc_action(
        self,
        action: dict[str, Any],
    ):
        """Execute one NPC-proposed action (V1: interact only)."""

        action_type = action.get("type")

        if action_type != "interact" and action_type != "interact_object":
            return type(
                "NpcActionNotAllowed",
                (),
                {
                    "success": False,
                    "message": (
                        f"NPCs cannot perform action type: {action_type}"
                    ),
                    "data": {},
                },
            )()

        if action_type == "interact":
            return npc_interact(
                self.game,
                action.get("actor", ""),
                action.get("target", ""),
                action.get("topic", ""),
                action.get("knowledge_transfer", ""),
                action.get("belief_transfer", ""),
                action.get("goal_transfer", ""),
            )

        return npc_interact_object(
            self.game,
            action.get("actor", ""),
            action.get("target", ""),
        )