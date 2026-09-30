#!/usr/bin/env python3
"""Serve Moondream 2 from the (deprecated) Moondream Station under launchd.

Why this exists instead of a plain `station interactive` pipe:

- A fresh REPL boot always makes *Moondream 3 MLX Quantized* the active model
  (the manifest default), rewriting config's ``current_model`` — and md3 is too
  heavy for a 16GB Mac, so its service never answers. We must explicitly
  ``models switch moondream-2`` on every boot.
- That switch shows an interactive "Does your system meet these requirements?"
  confirm that reads from a real TTY, so a piped stdin can't answer it. We drive
  the REPL through a pseudo-terminal and type ``y``.
- moondream-2 also needs ``transformers==4.46.3`` in the station venv (5.x makes
  it emit gibberish). That pin is a one-time setup, documented in docs/SETUP.md.

The script keeps the pty open forever; if the REPL dies the read loop hits EOF
and we exit, so launchd's KeepAlive restarts the whole thing.
"""

import os
import pty
import select
import sys
import time

STATION = os.path.expanduser("~/.local/bin/moondream-station")
MODEL = "moondream-2"
PORT = os.environ.get("MOONDREAM_PORT", "2020")


def _pump(fd: int, seconds: float, until: bytes | None = None) -> bool:
    """Copy child output to our stdout for `seconds`; stop early if `until` seen.

    Returns True if `until` was found. Raises OSError when the child exits.
    """
    end = time.time() + seconds
    seen = b""
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.3)
        if not r:
            continue
        data = os.read(fd, 4096)  # OSError on child exit -> propagates
        if not data:
            raise OSError("moondream station REPL closed")
        os.write(sys.stdout.fileno(), data)
        if until:
            seen = (seen + data)[-4096:]
            if until in seen:
                return True
    return False


def main() -> int:
    pid, fd = pty.fork()
    if pid == 0:  # child: become the station REPL
        os.execv(STATION, [STATION, "interactive"])
        return 1  # unreachable

    try:
        _pump(fd, 10, until=b">")  # let the REPL come up
        os.write(fd, f"models switch {MODEL}\r".encode())
        # The requirements confirm reads from the TTY; answer it when it shows.
        _pump(fd, 8, until=b"requirements")
        os.write(fd, b"y\r")
        _pump(fd, 40, until=b"witched to model")  # "Switched to model: ..."
        os.write(fd, f"start {PORT}\r".encode())
        _pump(fd, 3600 * 24 * 365)  # hold open; EOF -> OSError -> restart
    except OSError:
        return 1  # child died; let launchd KeepAlive restart us
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
