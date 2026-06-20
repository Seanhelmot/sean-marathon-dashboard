#!/usr/bin/env python3
"""
create_athlete.py — spin up a new athlete dashboard in ~2 minutes.

Usage:
    python scripts/create_athlete.py \
        --name "Jane Smith" \
        --garmin-email jane@example.com \
        --garmin-password "secret" \
        --github-token "ghp_..." \
        --github-owner "YourGitHubUsername" \
        --template-repo "sean-marathon-dashboard"

What it does:
  1. Creates a new GitHub repo from the template repo
  2. Sets GARMIN_EMAIL + GARMIN_PASSWORD as Actions secrets
  3. Enables GitHub Pages (deploy from main branch root)
  4. Fires the first workflow_dispatch to pull Garmin data
  5. Prints the live URL

Requirements:
    pip install requests PyNaCl
"""

import argparse
import base64
import json
import re
import sys
import time

import requests
from nacl import encoding, public  # PyNaCl — for encrypting secrets


def slug(name: str) -> str:
    """'Jane Smith' → 'jane-smith-marathon-dashboard'"""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + "-marathon-dashboard"


def gh(method, path, token, **kwargs):
    url = f"https://api.github.com{path}"
    resp = getattr(requests, method)(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        **kwargs,
    )
    if not resp.ok:
        print(f"  GitHub API error {resp.status_code}: {resp.text[:400]}", file=sys.stderr)
        sys.exit(1)
    return resp.json() if resp.content else {}


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt a secret using the repo's public key (GitHub's libsodium approach)."""
    pk = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder)
    box = public.SealedBox(pk)
    encrypted = box.encrypt(secret_value.encode())
    return base64.b64encode(encrypted).decode()


def main():
    ap = argparse.ArgumentParser(description="Create a new athlete marathon dashboard")
    ap.add_argument("--name",            required=True,  help="Athlete full name, e.g. 'Jane Smith'")
    ap.add_argument("--garmin-email",    required=True,  help="Athlete's Garmin Connect email")
    ap.add_argument("--garmin-password", required=True,  help="Athlete's Garmin Connect password")
    ap.add_argument("--github-token",    required=True,  help="GitHub personal access token (repo + secrets scope)")
    ap.add_argument("--github-owner",    required=True,  help="GitHub username or org that owns the template")
    ap.add_argument("--template-repo",   default="sean-marathon-dashboard", help="Template repo name")
    ap.add_argument("--repo-name",       default=None,   help="New repo name (auto-derived from athlete name if omitted)")
    ap.add_argument("--private",         action="store_true", help="Make the new repo private")
    args = ap.parse_args()

    token  = args.github_token
    owner  = args.github_owner
    repo   = args.repo_name or slug(args.name)

    print(f"\n🏃 Creating dashboard for: {args.name}")
    print(f"   Repo: {owner}/{repo}")

    # 1. Create repo from template
    print("\n1/4  Creating repo from template…")
    gh("post", f"/repos/{owner}/{args.template_repo}/generate", token, json={
        "owner": owner,
        "name":  repo,
        "description": f"Marathon training dashboard — {args.name}",
        "private": args.private,
        "include_all_branches": False,
    })
    print(f"     ✓ https://github.com/{owner}/{repo}")

    # Brief pause — repo takes a moment to be ready
    time.sleep(3)

    # 2. Encrypt and set secrets
    print("\n2/4  Setting Garmin secrets…")
    key_info = gh("get", f"/repos/{owner}/{repo}/actions/secrets/public-key", token)
    key_id   = key_info["key_id"]
    pub_key  = key_info["key"]

    for secret_name, secret_val in [
        ("GARMIN_EMAIL",    args.garmin_email),
        ("GARMIN_PASSWORD", args.garmin_password),
    ]:
        gh("put", f"/repos/{owner}/{repo}/actions/secrets/{secret_name}", token, json={
            "encrypted_value": encrypt_secret(pub_key, secret_val),
            "key_id": key_id,
        })
        print(f"     ✓ {secret_name} set")

    # 3. Enable GitHub Pages
    print("\n3/4  Enabling GitHub Pages…")
    try:
        gh("post", f"/repos/{owner}/{repo}/pages", token, json={
            "source": {"branch": "main", "path": "/"},
        })
        print(f"     ✓ Pages enabled")
    except SystemExit:
        print("     ⚠ Pages may already be enabled, or requires manual activation in repo Settings → Pages")

    # 4. Trigger first Garmin pull
    print("\n4/4  Triggering first Garmin data pull…")
    try:
        gh("post", f"/repos/{owner}/{repo}/actions/workflows/refresh-data.yml/dispatches", token,
           json={"ref": "main"})
        print("     ✓ Workflow dispatched — data will appear within ~2 minutes")
    except SystemExit:
        print("     ⚠ Could not trigger workflow — run it manually from GitHub → Actions → refresh-data")

    pages_url = f"https://{owner}.github.io/{repo}/"
    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Dashboard created for {args.name}

  Repo:      https://github.com/{owner}/{repo}
  Live URL:  {pages_url}
             (live in ~2 min after Pages builds)

  Next steps:
  1. Edit data/plan.json in the new repo — add the
     athlete's training plan, name, location, goals
  2. The Garmin workflow runs every 6h automatically
  3. Add the URL to your coach hub
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


if __name__ == "__main__":
    main()
