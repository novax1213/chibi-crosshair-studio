"""Show publishing controls only for the GitHub repository owner."""

import json
import os
import subprocess
from urllib.request import Request, urlopen

OWNER_LOGIN = "novax1213"


def is_repository_owner():
    """Use the local Git credential to verify the signed-in GitHub account."""
    env = dict(os.environ, GCM_INTERACTIVE="Never")
    try:
        credential = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True, capture_output=True, timeout=15, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if credential.returncode:
            return False
        fields = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
        token = fields.get("password")
        if not token:
            return False
        request = Request("https://api.github.com/user", headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Chibi-Crosshair-Studio",
        })
        with urlopen(request, timeout=15) as response:
            account = json.load(response)
        return account.get("login", "").lower() == OWNER_LOGIN
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return False
