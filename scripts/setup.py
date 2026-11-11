"""One-time local setup for Relay: `python scripts/setup.py`.

Checks the tools you need, writes backend/.env and frontend/.env.local (keeping any values
you already have), generates the local secrets, starts PostgreSQL, installs dependencies and
runs the migrations. Safe to run again. Standard library only.

You need a free WorkOS account for sign-in (Relay never handles passwords). The script asks
for its client ID and API key; see README "Run it yourself" for the two-minute setup.
Optional: a Gemini API key turns on the AI features (everything else works without it).
"""

import argparse
import base64
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND, FRONTEND = ROOT / "backend", ROOT / "frontend"
TOOLS = {
    "docker": "Docker Desktop (or Docker Engine with Compose): https://docs.docker.com/get-docker/",
    "uv": "uv: https://docs.astral.sh/uv/getting-started/installation/",
    "node": "Node.js 22+: https://nodejs.org/",
    "pnpm": "pnpm 10: run `corepack enable` or see https://pnpm.io/installation",
}


def step(text: str) -> None:
    print(f"\n==> {text}", flush=True)


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("   $", " ".join(cmd), flush=True)
    # shell=True on Windows so pnpm/uv shims (.cmd) resolve.
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
            if m:
                values[m.group(1)] = m.group(2).strip().strip('"')
    return values


def write_env(example: Path, target: Path, values: dict[str, str]) -> None:
    """Start from the example, keep existing values, fill the given ones."""
    current = read_env(target)
    lines = []
    for line in example.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\s*)([A-Z0-9_]+)(\s*=\s*)(.*)$", line)
        if m:
            key = m.group(2)
            value = current.get(key) or values.get(key)
            if value and not value.endswith("REPLACE_ME") and "REPLACE_WITH" not in value:
                quoted = f'"{value}"' if target.name.endswith(".local") else value
                line = f"{m.group(1)}{key}{m.group(3)}{quoted}"
        lines.append(line)
    known = set(read_env(example))
    # Keep keys you added yourself, then any new ones this script sets.
    extra = {k: v for k, v in current.items() if k not in known}
    extra |= {k: v for k, v in values.items() if v and k not in known and k not in current}
    quote = target.name.endswith(".local")
    lines += [f'{k}="{v}"' if quote else f"{k}={v}" for k, v in extra.items()]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ask(prompt: str, given: str | None, current: str | None, required: bool) -> str:
    if given:
        return given
    if current and "REPLACE" not in current:
        return current
    while True:
        value = input(f"   {prompt}: ").strip()
        if value or not required:
            return value
        print("   This one is required.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workos-client-id")
    parser.add_argument("--workos-api-key")
    parser.add_argument("--gemini-key", help="optional: turns on the AI features")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    step("Checking tools")
    missing = [f"   - {hint}" for tool, hint in TOOLS.items() if shutil.which(tool) is None]
    if missing:
        print("Install these first, then run this script again:\n" + "\n".join(missing))
        sys.exit(1)
    print("   All present.")

    step("WorkOS (sign-in)")
    print(
        "   In https://dashboard.workos.com (Staging environment): enable AuthKit, add the\n"
        "   redirect http://localhost:3000/callback, then copy the client ID and API key."
    )
    backend_env, frontend_env = read_env(BACKEND / ".env"), read_env(FRONTEND / ".env.local")
    client_id = ask(
        "WorkOS client ID (client_...)",
        args.workos_client_id,
        backend_env.get("RELAY_WORKOS_CLIENT_ID"),
        required=True,
    )
    api_key = ask(
        "WorkOS API key (sk_test_...)",
        args.workos_api_key,
        backend_env.get("RELAY_WORKOS_API_KEY"),
        required=True,
    )
    gemini = ask(
        "Gemini API key for AI features (optional, press Enter to skip)",
        args.gemini_key,
        backend_env.get("RELAY_GEMINI_KEY_1"),
        required=False,
    )

    step("Writing backend/.env and frontend/.env.local")
    fernet = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    write_env(
        BACKEND / ".env.example",
        BACKEND / ".env",
        {
            "RELAY_WORKOS_CLIENT_ID": client_id,
            "RELAY_WORKOS_API_KEY": api_key,
            "RELAY_GEMINI_KEY_1": gemini,
            "RELAY_LLM_PROVIDERS": "gemini" if gemini else "",
            # One process locally: the API also runs the background jobs.
            "RELAY_EMBEDDED_WORKER": "true",
            "RELAY_INTEGRATION_ENCRYPTION_KEY": backend_env.get(
                "RELAY_INTEGRATION_ENCRYPTION_KEY", fernet
            ),
        },
    )
    write_env(
        FRONTEND / ".env.example",
        FRONTEND / ".env.local",
        {
            "WORKOS_CLIENT_ID": client_id,
            "WORKOS_API_KEY": api_key,
            "WORKOS_COOKIE_PASSWORD": frontend_env.get(
                "WORKOS_COOKIE_PASSWORD", secrets.token_urlsafe(32)
            ),
            "WORKOS_ISSUER": f"https://api.workos.com/user_management/{client_id}",
        },
    )
    print("   Done. Secrets were generated locally and never leave your machine.")

    step("Starting PostgreSQL (Docker)")
    run(["docker", "compose", "up", "-d", "--wait"])

    if not args.skip_install:
        step("Installing backend dependencies")
        run(["uv", "sync"], BACKEND)
        step("Installing frontend dependencies")
        run(["pnpm", "install"], FRONTEND)

    step("Creating the database schema")
    run(["uv", "run", "alembic", "upgrade", "head"], BACKEND)

    print(
        "\nReady. Start Relay with:\n\n    python scripts/dev.py\n\n"
        "then open http://localhost:3000, sign in, and click 'Create sample workspace'."
    )


if __name__ == "__main__":
    os.chdir(ROOT)
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"\nA step failed: {' '.join(error.cmd)}. Fix the error above and run again.")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
