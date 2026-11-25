import time
import requests
import config

TIMEOUT_SECONDS = 15
MAX_EMBEDS_PER_MESSAGE = 10  # Discord limit

TITLES = {
    "new_issue": "📬 Nova issue",
    "pr_conflict": "⚠️ PR com conflito",
    "pr_ready": "✅ PR pronta para merge",
}
COLORS = {
    "new_issue": 0x3498DB,  # blue
    "pr_conflict": 0xE74C3C,  # red
    "pr_ready": 0x2ECC71,  # green
}


# Any failure sending to Discord (network, invalid webhook, rate limit)
class DiscordError(Exception):
    pass


# One colored card (embed) per event
def build_embed(event):
    item = event["item"]
    return {
        "title": f"{TITLES[event['type']]}: {item['title']}"[:256],  # Discord title limit
        "url": item["url"],
        "color": COLORS[event["type"]],
        "fields": [
            {"name": "Repositório", "value": f"{item['repo']} #{item['number']}", "inline": True},
            {"name": "Autor", "value": item["author"], "inline": True},
        ],
    }


# Sends the embeds, split into messages of up to 10
def send_embeds(embeds):
    for start in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
        _post({"username": "Dev Digest", "embeds": embeds[start:start + MAX_EMBEDS_PER_MESSAGE]})


# POST to the webhook; waits and retries if Discord says "too many requests" (429)
def _post(payload):
    for attempt in range(3):
        try:
            response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as error:  # timeout, no internet, DNS
            raise DiscordError(f"falha de rede ao enviar para o Discord: {error}") from error

        if response.status_code == 429:
            time.sleep(response.json().get("retry_after", 1))
            continue
        if response.status_code >= 400:
            raise DiscordError(f"o Discord respondeu {response.status_code}: {response.text[:200]}")
        return

    raise DiscordError("o Discord continuou limitando as mensagens (429)")
