# Compares current data with the last run and returns what changed
def find_events(prs, issues, previous):
    if previous is None:
        return []  # first run: nothing to compare with

    events = []

    known_issues = set(previous["issues"])
    for issue in issues:
        if issue["url"] not in known_issues:
            events.append({"type": "new_issue", "item": issue})

    for pr in prs:
        before = previous["prs"].get(pr["url"])
        now = pr["mergeable_state"]
        if before is None or now == "unknown" or now == before:
            continue  # new PR, still computing, or no change
        if now == "dirty":
            events.append({"type": "pr_conflict", "item": pr})
        elif now == "clean":
            events.append({"type": "pr_ready", "item": pr})

    return events


# What we save for the next run: issue URLs and each PR's merge state
def build_state(prs, issues, previous):
    old_prs = previous["prs"] if previous else {}
    pr_states = {}

    for pr in prs:
        if pr["mergeable_state"] != "unknown":
            pr_states[pr["url"]] = pr["mergeable_state"]
        elif pr["url"] in old_prs:
            pr_states[pr["url"]] = old_prs[pr["url"]]  # keep the last known value

    return {"issues": [issue["url"] for issue in issues], "prs": pr_states}
