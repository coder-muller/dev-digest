import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import ai_writer
import analyzer
import config
import discord_client
import github_client
import state

MAX_AI_DESCRIPTIONS = 3  # AI Gateway free tier allows 5 requests per minute


# Alerts for what changed since the last run
def check():
    prs, issues = _fetch()
    previous = state.load()
    events = analyzer.find_events(prs, issues, previous)

    if previous is None:
        print("Primeira execução: estado salvo, nenhum alerta enviado.")
    elif events:
        # If sending fails, _send exits before saving, so these alerts are retried next run
        embeds = []
        described = 0
        for event in events:
            description = None
            if event["type"] == "new_issue" and described < MAX_AI_DESCRIPTIONS:
                description = _describe(event)
                described += 1
            embeds.append(discord_client.build_embed(event, description))
        _send(embeds)
        print(f"{len(events)} alerta(s) enviado(s) para o Discord.")
    else:
        print("Nada novo.")

    state.save(analyzer.build_state(prs, issues, previous))


# Morning digest with everything that is open right now
def digest():
    prs, issues = _fetch()
    data = analyzer.build_digest(prs, issues)

    try:
        intro = ai_writer.write_digest_intro(data)
    except ai_writer.AIError as error:
        print(f"Aviso: IA indisponível, usando o texto padrão ({error})")
        intro = ai_writer.fallback_digest_intro(data)

    today = datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%d/%m")
    _send([discord_client.build_digest_embed(data, intro, today)])
    print("Resumo enviado para o Discord.")


# AI sentence for a new issue; the alert still goes out without it
def _describe(event):
    try:
        return ai_writer.describe_issue(event["item"])
    except ai_writer.AIError as error:
        print(f"Aviso: alerta sem resumo da IA ({error})")
        return None


def _fetch():
    try:
        return github_client.fetch_open_prs(), github_client.fetch_open_issues()
    except github_client.GitHubError as error:
        print(f"Erro ao buscar dados no GitHub: {error}")
        sys.exit(1)


def _send(embeds):
    try:
        discord_client.send_embeds(embeds)
    except discord_client.DiscordError as error:
        print(f"Erro ao enviar para o Discord: {error}")
        sys.exit(1)


COMMANDS = {"check": check, "digest": digest}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in COMMANDS:
        print("Uso: python main.py check | digest")
        sys.exit(2)
    COMMANDS[command]()
