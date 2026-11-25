import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import ai_writer
import analyzer
import config
import discord_client
import github_client
import state

MAX_AI_DESCRIPTIONS = 3  # AI Gateway free tier allows 5 requests per minute
KNOWN_ERRORS = (github_client.GitHubError, discord_client.DiscordError)


# Alerts for what changed since the last run
def check():
    prs = github_client.fetch_open_prs()
    issues = github_client.fetch_open_issues()
    previous = state.load()
    events = analyzer.find_events(prs, issues, previous)

    if previous is None:
        log("Primeira execução: estado salvo, nenhum alerta enviado.")
    elif events:
        embeds = []
        described = 0
        for event in events:
            description = None
            if event["type"] == "new_issue" and described < MAX_AI_DESCRIPTIONS:
                description = _describe(event)
                described += 1
            embeds.append(discord_client.build_embed(event, description))
        # If this fails, the state below is not saved, so the alerts are retried next run
        discord_client.send_embeds(embeds)
        log(f"{len(events)} alerta(s) enviado(s) para o Discord.")
    else:
        log("Nada novo.")

    state.save(analyzer.build_state(prs, issues, previous))


# Morning digest with everything that is open right now
def digest():
    prs = github_client.fetch_open_prs()
    issues = github_client.fetch_open_issues()
    data = analyzer.build_digest(prs, issues)

    try:
        intro = ai_writer.write_digest_intro(data)
    except ai_writer.AIError as error:
        log(f"Aviso: IA indisponível, usando o texto padrão ({error})")
        intro = ai_writer.fallback_digest_intro(data)

    today = _now().strftime("%d/%m")
    discord_client.send_embeds([discord_client.build_digest_embed(data, intro, today)])
    log("Resumo enviado para o Discord.")


# Runs forever: check every N minutes and the digest once a day
def run():
    log(f"Dev Digest rodando: verificação a cada {config.CHECK_INTERVAL_MINUTES} min, "
        f"resumo às {config.DIGEST_TIME:%H:%M} ({config.TIMEZONE}).")

    # Started after the digest time? The first digest is tomorrow
    last_digest_day = _now().date() if _now().time() >= config.DIGEST_TIME else None

    while True:
        now = _now()
        if now.time() >= config.DIGEST_TIME and now.date() != last_digest_day:
            if _safe_run(digest):  # on failure, tries again on the next loop
                last_digest_day = now.date()
        _safe_run(check)
        time.sleep(config.CHECK_INTERVAL_MINUTES * 60)


# Runs a task without stopping the loop when it fails
def _safe_run(task):
    try:
        task()
        return True
    except KNOWN_ERRORS as error:
        log(f"Erro: {error}")
    except Exception as error:  # unexpected bug: log it and keep running
        log(f"Erro inesperado: {error!r}")
    return False


# AI sentence for a new issue; the alert still goes out without it
def _describe(event):
    try:
        return ai_writer.describe_issue(event["item"])
    except ai_writer.AIError as error:
        log(f"Aviso: alerta sem resumo da IA ({error})")
        return None


def _now():
    return datetime.now(ZoneInfo(config.TIMEZONE))


# Message with date and time; flush shows it right away (useful in Docker logs)
def log(message):
    print(f"[{_now():%d/%m %H:%M:%S}] {message}", flush=True)


COMMANDS = {"check": check, "digest": digest, "run": run}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in COMMANDS:
        print("Uso: python main.py check | digest | run")
        sys.exit(2)
    try:
        COMMANDS[command]()
    except KNOWN_ERRORS as error:
        log(f"Erro: {error}")
        sys.exit(1)
    except KeyboardInterrupt:  # Ctrl+C
        log("Encerrado.")
