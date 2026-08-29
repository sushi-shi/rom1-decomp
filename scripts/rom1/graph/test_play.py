"""Integration controls for the generated Rom1 game launcher."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

from rom1.graph.play import write_play_sh


class PlayRunnerControls(unittest.TestCase):
    def test_wine_prefix_is_stopped_and_game_status_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            target = tmp / "game env"
            game = target / "game"
            fake_bin = tmp / "bin"
            game.mkdir(parents=True)
            fake_bin.mkdir()
            (game / "ALLODS.EXE").write_bytes(b"candidate")
            log = tmp / "calls.log"
            server_pid = tmp / "server.pid"

            self._write_executable(
                fake_bin / "gamescope",
                """#!/usr/bin/env bash
while [[ $# -gt 0 && $1 != -- ]]; do shift; done
[[ $# -gt 0 ]] && shift
"$@"
""",
            )
            self._write_executable(
                fake_bin / "wine",
                """#!/usr/bin/env bash
printf 'wine:%s\\n' "$1" >> "$PLAY_TEST_LOG"
sleep 300 &
printf '%s\\n' "$!" > "$PLAY_TEST_SERVER_PID"
exit 7
""",
            )
            self._write_executable(
                fake_bin / "wineserver",
                """#!/usr/bin/env bash
printf 'wineserver:%s:%s\\n' "$1" "$WINEPREFIX" >> "$PLAY_TEST_LOG"
kill "$(cat "$PLAY_TEST_SERVER_PID")"
""",
            )

            play_sh = write_play_sh(target, tmp / "repo")
            env = dict(
                os.environ,
                PATH=f"{fake_bin}:{os.environ['PATH']}",
                PLAY_TEST_LOG=str(log),
                PLAY_TEST_SERVER_PID=str(server_pid),
            )
            try:
                result = subprocess.run(
                    [str(play_sh)],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=5,
                )
            finally:
                if server_pid.exists():
                    try:
                        os.kill(int(server_pid.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                [
                    "wine:ALLODS.EXE",
                    f"wineserver:-k:{target / 'prefix3'}",
                ],
            )

    @staticmethod
    def _write_executable(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
