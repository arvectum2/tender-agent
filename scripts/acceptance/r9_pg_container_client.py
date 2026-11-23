#!/usr/bin/env python3
"""Isolated R9 acceptance adapter: run PG16 clients inside owned PG16 DB container.

Installed as disposable pg_dump/pg_restore shim in the acceptance scratch PATH.
Only synthetic loopback targets are allowed. Production recovery is unchanged.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def main() -> int:
    name = Path(sys.argv[0]).name
    if name not in {"pg_dump", "pg_restore"}:
        raise SystemExit("R9 PG client accepts only pg_dump and pg_restore")
    container = os.environ.get("R9_PG_TEST_CONTAINER", "")
    host_port = os.environ.get("R9_PG_TEST_PORT", "")
    if not container or not host_port.isdigit() or not os.environ.get("PGPASSWORD"):
        raise SystemExit("R9 disposable DB/container identity not established")
    args = sys.argv[1:]
    if name == "pg_dump":
        index = args.index("--file")
        data_file = Path(args[index + 1])
        del args[index : index + 2]
        url_index = len(args) - 1
    else:
        index = args.index("--dbname")
        url_index = index + 1
        data_file = Path(args[-1])
        del args[-1]
    parsed = urlsplit(args[url_index])
    if (
        parsed.scheme != "postgresql"
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.port != int(host_port)
        or not parsed.username
        or parsed.password
        or not parsed.path.startswith("/")
    ):
        raise SystemExit("refusing non-disposable database URI")
    # The server container is the only PG16 target; use its own loopback.
    args[url_index] = urlunsplit(
        (
            "postgresql",
            f"{parsed.username}@127.0.0.1:5432",
            parsed.path,
            parsed.query,
            "",
        )
    )
    command = [
        "docker",
        "exec",
        "-i",
        "-e",
        f"PGPASSWORD={os.environ['PGPASSWORD']}",
        container,
        name,
        *args,
    ]
    if name == "pg_dump":
        with data_file.open("wb") as output:
            result = subprocess.run(
                command, stdout=output, stderr=subprocess.PIPE, check=False, timeout=90
            )
    else:
        with data_file.open("rb") as archive:
            result = subprocess.run(
                command,
                stdin=archive,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=90,
            )
    # Credential-bearing argv and stderr are deliberately never forwarded.
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
