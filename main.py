import sys

import github_client


# Step 1: fetch data from GitHub and print it
def main():
    try:
        prs = github_client.fetch_open_prs()
        issues = github_client.fetch_open_issues()
    except github_client.GitHubError as error:
        print(f"Erro ao buscar dados no GitHub: {error}")
        sys.exit(1)

    print(f"{len(prs)} PRs abertas:")
    for pr in prs:
        print(f"  {pr['repo']} #{pr['number']} [{pr['mergeable_state']}] {pr['title']}")

    print(f"\n{len(issues)} issues abertas:")
    for issue in issues:
        print(f"  {issue['repo']} #{issue['number']} {issue['title']}")


if __name__ == "__main__":
    main()
