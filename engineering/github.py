"""GitHub adapter. Read-only by default. Writes need token + owner approval.
HARD RULE: never touch /root/rayvice-live or production. Plans/patches live in agent workspace drafts only."""
import json
import os
import urllib.request
import urllib.parse

import config

API = "https://api.github.com"

def _headers():
    h = {"User-Agent": "Rayvice-Agent/1.0", "Accept": "application/vnd.github+json"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h

def _get(path):
    try:
        req = urllib.request.Request(API + path, headers=_headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, json.loads(r.read().decode())
    except Exception as e:
        return False, str(e)[:300]

def status():
    if not config.GITHUB_REPO:
        return "GitHub connected nahi hai bhai (GITHUB_REPO khali hai). Repo naam `.env` me daloge tab read-only check chalu hoga. Token ke bina public repo bhi dekh sakta hu."
    ok, repo = _get(f"/repos/{config.GITHUB_REPO}")
    if not ok:
        return f"GitHub repo nahi khul raha: {repo}"
    return f"GitHub OK bhai: {repo.get('full_name')} | ⭐ {repo.get('stargazers_count')} | open issues: {repo.get('open_issues_count')}"

def list_issues(limit=10):
    if not config.GITHUB_REPO:
        return []
    ok, data = _get(f"/repos/{config.GITHUB_REPO}/issues?state=open&per_page={limit}")
    if not ok or not isinstance(data, list):
        return []
    return [{"number": i.get("number"), "title": i.get("title"), "labels": [l.get("name") for l in i.get("labels", [])]} for i in data]

def file_tree(limit=30):
    if not config.GITHUB_REPO:
        return []
    ok, data = _get(f"/repos/{config.GITHUB_REPO}/contents/")
    if not ok or not isinstance(data, list):
        return []
    return [x.get("path") for x in data][:limit]

def prepare_pr_plan(issue, root_cause, files, fix, tests, risk="MEDIUM"):
    return (f"PR PLAN (merge se pehle approval chahiye, main pe direct kuch nahi):\n"
            f"Issue: {issue}\nRoot cause: {root_cause}\nFiles: {files}\nFix: {fix}\nTests: {tests}\n"
            f"Risk: {risk}\nFlow: branch → implement → test → review → PR → APPROVAL → merge.\n"
            f"Note: Rayvice production repo ko haath nahi lagega bina tere haan ke.")
