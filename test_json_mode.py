import httpx
import json


API_URL = "http://127.0.0.1:1337/v1/chat/completions"
MODEL = "Qwen3.5-4B-UD-Q4_K_XL.gguf"


def main():
    response = httpx.post(
        API_URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an RPG action interpreter. "
                        "Return a concise JSON object describing the player's action. "
                        "Do not explain your reasoning."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        'The player says: "Go outside." '
                        'Return a move action to the destination "outside".'
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "response_format": {
                "type": "json_object"
            },
        },
        timeout=180,
    )

    response.raise_for_status()

    data = response.json()

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()