import json
import re
import requests
import config

API_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"  # OpenAI-compatible API
TIMEOUT_SECONDS = 30
MAX_EXAMPLES = 5
MAX_ISSUE_CHARS = 200
MAX_INTRO_CHARS = 500

SYSTEM_PROMPT = """Você escreve avisos curtos sobre o GitHub de um desenvolvedor. Eles aparecem no Discord.

Regras:
- Português do Brasil, frases curtas e simples, tom amigável e direto.
- Use só os dados recebidos. Nunca invente números, nomes, títulos ou links.
- Texto corrido: sem listas, títulos, markdown, emojis, aspas, despedidas ou assinaturas.
- Se aparecer um termo técnico difícil, explique de forma simples."""

ISSUE_PROMPT = """Em uma frase de até 25 palavras, diga o que esta issue pede ou qual problema ela relata.
Vá direto ao assunto, sem começar com "Esta issue" ou "A issue".
Comece com "Urgente:" só se o texto disser que o sistema está fora do ar, perdendo dados ou com falha de segurança.

Issue:
{issue}"""

DIGEST_PROMPT = """Escreva a abertura do resumo matinal em até 3 frases curtas:
1. Comece com "Bom dia!".
2. Diga o que precisa de atenção, nesta ordem: PRs com conflito, PRs que pedem revisão, issues novas, PRs prontas para merge.
3. Termine com uma sugestão clara do que fazer primeiro.

Ignore itens com total 0. Não liste PRs nem issues: os detalhes já aparecem abaixo da mensagem.

Dados (JSON):
{facts}"""


# Any failure talking to the AI (network, bad key, no credits, empty answer)
class AIError(Exception):
    pass


# Sends a prompt to the model chosen in .env and returns the text answer
def _ask(prompt):
    payload = {
        "model": config.AI_MODEL,
        "max_tokens": 1000,
        "temperature": 0.3,  # low = more consistent answers
        "reasoning": {"enabled": False},  # no "thinking" step: faster, cheaper, never cut off
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {config.AI_GATEWAY_API_KEY}"}

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:  # timeout, no internet, DNS
        raise AIError(f"falha de rede ao acessar a IA: {error}") from error

    if response.status_code >= 400:
        raise AIError(f"a IA respondeu {response.status_code}: {response.text[:200]}")

    try:
        choice = response.json()["choices"][0]
        text = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:  # unexpected JSON
        raise AIError("resposta da IA em formato inesperado") from error
    if choice.get("finish_reason") == "length":
        raise AIError("a resposta da IA foi cortada (limite de tokens)")
    if not text or not text.strip():
        raise AIError("a IA devolveu uma resposta vazia")
    return text


# Guarantees a clean answer even if the model ignores the rules
def clean_text(text, max_chars):
    text = re.sub(r"[*_`#>]", "", text)  # markdown symbols
    text = re.sub(r"\s+", " ", text).strip()  # line breaks and extra spaces
    text = text.strip("\"'“”")  # quotes around the whole answer
    if len(text) > max_chars:
        return text[:max_chars].rsplit(" ", 1)[0] + "…"  # cut at a word boundary
    if text and text[-1] not in ".!?…":
        text += "."  # always end the sentence
    return text


# One short sentence about what a new issue is
def describe_issue(issue):
    details = (
        f"Repositório: {issue['repo']}\n"
        f"Título: {issue['title']}\n"
        f"Labels: {', '.join(issue['labels']) or 'nenhuma'}\n"
        f"Descrição: {issue['body'] or '(sem descrição)'}"
    )
    return clean_text(_ask(ISSUE_PROMPT.format(issue=details)), MAX_ISSUE_CHARS)


# Opening text of the morning digest
def write_digest_intro(digest):
    facts = {
        "prs_abertas": digest["total_prs"],
        "issues_abertas": digest["total_issues"],
        "prs_com_conflito": _summary(digest["conflict"]),
        "prs_que_pedem_revisao": _summary(digest["review_requested"]),
        "issues_novas_nas_ultimas_24h": _summary(digest["new_issues"]),
        "prs_prontas_para_merge": _summary(digest["ready"]),
        f"prs_paradas_ha_mais_de_{config.STALE_PR_DAYS}_dias": _summary(digest["stale"]),
    }
    prompt = DIGEST_PROMPT.format(facts=json.dumps(facts, ensure_ascii=False, indent=2))
    return clean_text(_ask(prompt), MAX_INTRO_CHARS)


# Plain text used when the AI is unavailable
def fallback_digest_intro(digest):
    return (
        f"Bom dia! Você tem {digest['total_prs']} PRs e {digest['total_issues']} issues abertas: "
        f"{len(digest['ready'])} PRs prontas para merge, {len(digest['conflict'])} com conflito "
        f"e {len(digest['new_issues'])} issues novas nas últimas 24h."
    )


# Total plus a few titles, so the prompt stays small
def _summary(items):
    examples = [f"{item['repo']}#{item['number']}: {item['title']}" for item in items[:MAX_EXAMPLES]]
    return {"total": len(items), "exemplos": examples}
