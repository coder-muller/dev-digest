import sys

import analyzer
import discord_client
import github_client
import state


# Step 2: find what changed since the last run and alert on Discord
def check():
    try:
        prs = github_client.fetch_open_prs()
        issues = github_client.fetch_open_issues()
    except github_client.GitHubError as error:
        print(f"Erro ao buscar dados no GitHub: {error}")
        sys.exit(1)

    previous = state.load()
    events = analyzer.find_events(prs, issues, previous)

    if previous is None:
        print("Primeira execução: estado salvo, nenhum alerta enviado.")
    elif events:
        try:
            discord_client.send_embeds([discord_client.build_embed(event) for event in events])
        except discord_client.DiscordError as error:
            # State is not saved, so these alerts are retried on the next run
            print(f"Erro ao enviar para o Discord: {error}")
            sys.exit(1)
        print(f"{len(events)} alerta(s) enviado(s) para o Discord.")
    else:
        print("Nada novo.")

    state.save(analyzer.build_state(prs, issues, previous))


if __name__ == "__main__":
    check()
