"""Fail-closed access to the executable-proven VC5 servicing selection."""

from __future__ import annotations

import hashlib
import tomllib

from rom1.core.paths import CONFIG, msvc_dir
from rom1.tool import ToolError
from rom1.tool.compiler_census import find_ci, fixed_file_version
from rom1.tool.library_census import default_archives


def require_selected_toolchain() -> dict:
    """Return selection metadata only when the active payload is exact.

    The PE stamp narrows RoM1 to VC5 SP1/SP2 but cannot distinguish them.  A
    compile or link with the convenient Gruntz SP3 bootstrap would create
    misleading artifacts, so those operations remain unavailable until the
    complete servicing matrix has selected and hashed one payload.
    """
    path = CONFIG / "compiler.toml"
    data = tomllib.loads(path.read_text())
    if data.get("status") != "selected":
        raise ToolError(
            "exact compiler servicing is unresolved (retail linker stamp 5.02: "
            "VC5 SP1 or SP2). Supply both payloads to `rom1 tool "
            "compiler-census --candidate vc5-sp1=... --candidate vc5-sp2=... "
            "--write`; the bundled SP3 toolchain is analysis-only.")

    root = msvc_dir().parent
    linker = find_ci(root / "msvc/bin", "link.exe")
    if linker is None:
        raise ToolError(f"selected toolchain has no msvc/bin/link.exe: {root}")
    actual = fixed_file_version(linker)
    if actual != data.get("linker_file_version"):
        raise ToolError(f"active link.exe is {actual}, selection requires "
                        f"{data.get('linker_file_version')}")
    hashes = sorted(hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in default_archives(root))
    aggregate = hashlib.sha256("".join(hashes).encode()).hexdigest()
    if aggregate != data.get("archive_set_sha256"):
        raise ToolError("active VC5 archive set does not match compiler.toml")
    return data
