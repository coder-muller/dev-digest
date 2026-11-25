import time
import requests
from dev_digest import config

TIMEOUT_SECONDS = 15
MAX_EMBEDS_PER_MESSAGE = 10  # Discord limit
MAX_LIST_ITEMS = 5
DIGEST_COLOR = 0xF1C40F  # yellow

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


# One colored card (embed) per event, with an optional AI description
def build_embed(event, description=None):
    item = event["item"]
    embed = {
        "title": f"{TITLES[event['type']]}: {item['title']}"[:256],  # Discord title limit
        "url": item["url"],
        "color": COLORS[event["type"]],
        "fields": [
            {"name": "Repositório", "value": f"{item['repo']} #{item['number']}", "inline": True},
            {"name": "Autor", "value": item["author"], "inline": True},
        ],
    }
    if description:
        embed["description"] = description[:4096]  # Discord description limit
    return embed


# Morning digest card: AI intro on top, then one field per section
def build_digest_embed(digest, intro, date_label):
    sections = [
        ("✅ Prontas para merge", digest["ready"]),
        ("⚠️ Com conflito", digest["conflict"]),
        ("👀 Pedem sua revisão", digest["review_requested"]),
        ("📬 Issues novas (24h)", digest["new_issues"]),
        (f"💤 PRs paradas há mais de {config.STALE_PR_DAYS} dias", digest["stale"]),
    ]
    fields = [
        {"name": f"{title} ({len(items)})", "value": _item_list(items)}
        for title, items in sections
        if items  # skip empty sections
    ]

    if digest["issues_by_repo"]:
        top_repos = " · ".join(f"{repo.split('/')[1]} {count}" for repo, count in digest["issues_by_repo"])
        fields.append({"name": f"📊 Issues abertas ({digest['total_issues']})", "value": top_repos})

    return {
        "title": f"☀️ Resumo do dia · {date_label}",
        "description": intro[:4096],
        "color": DIGEST_COLOR,
        "fields": fields,
    }


# Clickable list of up to 5 items for an embed field
def _item_list(items):
    lines = [
        f"[{item['repo'].split('/')[1]}#{item['number']}]({item['url']}) {item['title'][:50]}"
        for item in items[:MAX_LIST_ITEMS]
    ]
    if len(items) > MAX_LIST_ITEMS:
        lines.append(f"…e mais {len(items) - MAX_LIST_ITEMS}")
    return "\n".join(lines)[:1024]  # Discord field limit


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
