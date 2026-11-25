import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Check required environment variables
REQUIRED = ["GITHUB_USERNAME", "GITHUB_TOKEN", "AI_GATEWAY_API_KEY", "DISCORD_WEBHOOK_URL"]
missing = [name for name in REQUIRED if not os.getenv(name)]
if missing:
    sys.exit(f"Faltam variáveis no .env: {', '.join(missing)} (veja o .env.example)")

# GitHub
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Comma-separated repos to watch; empty = all repos
GITHUB_REPOS = [name.strip() for name in os.getenv("GITHUB_REPOS", "").split(",") if name.strip()]
WATCH_REVIEW_REQUESTS = os.getenv("WATCH_REVIEW_REQUESTS", "true").lower() == "true"

# AI
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "google/gemini-2.5-flash")

# Discord
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Other settings
DIGEST_TIME = os.getenv("DIGEST_TIME", "08:00")
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "2"))
STALE_PR_DAYS = int(os.getenv("STALE_PR_DAYS", "7"))
