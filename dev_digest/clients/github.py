import requests
from dev_digest import config

API_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {config.GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
TIMEOUT_SECONDS = 15


# Any failure talking to GitHub (network, bad token, rate limit)
class GitHubError(Exception):
    pass


# GET request to the GitHub API, returns the parsed JSON
def _get(path, params=None):
    try:
        response = requests.get(f"{API_URL}{path}", headers=HEADERS, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as error:  # timeout, no internet, DNS
        raise GitHubError(f"falha de rede ao acessar o GitHub: {error}") from error

    if response.status_code == 401:
        raise GitHubError("token do GitHub inválido ou expirado (401)")
    if response.status_code in (403, 429):
        raise GitHubError(f"acesso negado ou limite de requisições atingido ({response.status_code})")
    if response.status_code >= 400:
        raise GitHubError(f"o GitHub respondeu {response.status_code}: {response.text[:200]}")
    return response.json()


# Search filter: all your repos, or only the ones listed in .env
def _scope():
    if config.GITHUB_REPOS:
        return " ".join(f"repo:{config.GITHUB_USERNAME}/{name}" for name in config.GITHUB_REPOS)
    return f"user:{config.GITHUB_USERNAME}"


# Same syntax as the GitHub search bar
def _search(query):
    data = _get("/search/issues", {"q": query, "per_page": 100, "sort": "updated"})
    return data["items"]


# Keep only the fields we use from the GitHub JSON
def _simplify(item):
    owner, repo = item["repository_url"].split("/")[-2:]  # ".../repos/owner/name"
    return {
        "repo": f"{owner}/{repo}",
        "number": item["number"],
        "title": item["title"],
        "author": item["user"]["login"],
        "url": item["html_url"],
        "labels": [label["name"] for label in item["labels"]],
        "body": (item.get("body") or "")[:500],  # first 500 chars, for the AI
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


# Search results don't include conflicts, so fetch the full PR
def _merge_status(repo, number):
    pr = _get(f"/repos/{repo}/pulls/{number}")
    return {
        "draft": pr["draft"],
        "mergeable": pr["mergeable"],  # True, False or None (still computing)
        "mergeable_state": pr["mergeable_state"],  # clean, dirty (conflict), blocked, unstable, unknown...
    }


# Open issues in the watched repos
def fetch_open_issues():
    items = _search(f"is:issue is:open archived:false {_scope()}")
    return [_simplify(item) for item in items]


# Open PRs in your repos, plus review requests if enabled
def fetch_open_prs():
    prs = {}  # keyed by URL to avoid duplicates

    for item in _search(f"is:pr is:open archived:false {_scope()}"):
        pr = _simplify(item)
        pr["review_requested"] = False
        prs[pr["url"]] = pr

    if config.WATCH_REVIEW_REQUESTS:
        query = f"is:pr is:open archived:false review-requested:{config.GITHUB_USERNAME}"
        for item in _search(query):
            pr = _simplify(item)
            pr["review_requested"] = True
            prs[pr["url"]] = pr

    for pr in prs.values():
        pr.update(_merge_status(pr["repo"], pr["number"]))

    return list(prs.values())
