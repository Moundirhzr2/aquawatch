"""Create local Compose credentials without overwriting an existing environment."""

import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / ".env"
with path.open("x", encoding="utf-8") as out:
    out.write("POSTGRES_USER=aquawatch\nPOSTGRES_DB=aquawatch\n")
    out.write("POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")
print("Created .env with a random local password. Keep it out of Git.")
