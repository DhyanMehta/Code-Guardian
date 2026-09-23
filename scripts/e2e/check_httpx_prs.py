from backend.tools.github_app import get_installation_github

INSTALLATION_ID = 161715271
print("Connecting to GitHub App for installation 161715271...", flush=True)
g = get_installation_github(INSTALLATION_ID)
repo = g.get_repo("DhyanMehta/httpx")
print(f"Repo: {repo.full_name}, default_branch: {repo.default_branch}", flush=True)

for p in repo.get_pulls(state="open"):
    print(f"OPEN PR #{p.number}: '{p.title}'", flush=True)
    print(f"  Head SHA: {p.head.sha}", flush=True)
    print(f"  Head Ref: {p.head.ref}", flush=True)
    print(f"  Base Ref: {p.base.ref}", flush=True)
    print(f"  URL: {p.html_url}", flush=True)
    break
