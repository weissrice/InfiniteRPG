import json

from engine.ai import AIClient
from engine.context import build_game_context
from engine.world import create_new_game


SYSTEM_PROMPT = """
You are the action interpreter for a text-based RPG.

Your job is to interpret the player's action and return a JSON object.

Return ONLY valid JSON.
Do not use Markdown.
Do not explain your reasoning.

The JSON must have exactly this structure:

{
  "narration": "short description of what happens",
  "actions": [
    {
      "type": "action_type",
      "item": "optional item name",
      "destination": "optional destination"
    }
  ]
}

Valid action types:
- move
- take_item
- drop_item
- inspect
- wait

If the player is only observing or asking a question, use:
"actions": []

Do not invent items, locations, or characters that aren't present
in the supplied game state.
"""


def main():
    game = create_new_game()

    context = build_game_context(game)

    player_input = "Take the rusty key."

    prompt = f"""
GAME STATE:

{context}

PLAYER ACTION:

{player_input}

Interpret the player's action according to the game state.
"""

    ai = AIClient()

    try:
        response = ai.ask(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=4096,
            temperature=0.2,
        )

        print("RAW AI RESPONSE:")
        print(response)

        print("\nPARSED JSON:")

        parsed = json.loads(response)

        print(json.dumps(parsed, indent=2))

    finally:
        ai.close()


if __name__ == "__main__":
    main()