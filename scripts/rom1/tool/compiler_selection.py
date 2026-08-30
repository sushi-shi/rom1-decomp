"""Fail-closed access to the executable-proven VC5 servicing selection."""

from __future__ import annotations

import hashlib
import tomllib

from rom1.core.paths import CONFIG, msvc_dir
from rom1.tool import ToolError
from rom1.tool.compiler_census import ROLES, find_ci, fixed_file_version
from rom1.tool.library_census import default_archives


def require_selected_toolchain() -> dict:
    """Return selection metadata only when the active payload is exact.

    A compile or link with the convenient Gruntz SP3 bootstrap would create
    misleading artifacts. The selected SP2-first payload is therefore pinned
    by both its complete tool-role hash and its archive-set hash.
    """
    path = CONFIG / "compiler.toml"
    data = tomllib.loads(path.read_text())
    if data.get("status") != "selected":
        raise ToolError(
            "exact compiler servicing is unresolved. Run `rom1 tool "
            "compiler-census --candidate vc5-sp2=... --write`; acquire SP1 "
            "only if the tracked SP2-first panel fails. The bundled SP3 "
            "toolchain is analysis-only.")

    root = msvc_dir().parent
    linker = find_ci(root / "msvc/bin", "link.exe")
    if linker is None:
        raise ToolError(f"selected toolchain has no msvc/bin/link.exe: {root}")
    actual = fixed_file_version(linker)
    if actual != data.get("linker_file_version"):
        raise ToolError(f"active link.exe is {actual}, selection requires "
                        f"{data.get('linker_file_version')}")
    tool_hashes = []
    for role in ROLES:
        tool = find_ci(root / "msvc/bin", role)
        if tool is None:
            raise ToolError(f"selected toolchain has no msvc/bin/{role}: {root}")
        tool_hashes.append(hashlib.sha256(tool.read_bytes()).hexdigest())
    tool_aggregate = hashlib.sha256("".join(sorted(tool_hashes)).encode()).hexdigest()
    if tool_aggregate != data.get("tool_set_sha256"):
        raise ToolError("active VC5 compiler/linker tool set does not match compiler.toml")
    hashes = sorted(hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in default_archives(root))
    aggregate = hashlib.sha256("".join(hashes).encode()).hexdigest()
    if aggregate != data.get("archive_set_sha256"):
        raise ToolError("active VC5 archive set does not match compiler.toml")
    return data
