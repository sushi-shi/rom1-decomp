#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
: "${MSVC_DIR:?run inside 'nix develop'}"
: "${WINEPREFIX:?run inside 'nix develop'}"

name="${1:?usage: build.sh <name> [unit ...]}"
shift || true
src="$here/$name.c"
[ -f "$src" ] || src="$here/$name.cpp"
[ -f "$src" ] || { echo "build.sh: no source for $name" >&2; exit 1; }

objects=()
for unit in "$@"; do
    object="$repo/build/objdiff/base/$unit.obj"
    [ -f "$object" ] || {
        echo "build.sh: $object missing; run 'rom1 build' first" >&2
        exit 1
    }
    objects+=("$(winepath -w "$object")")
done

export WINEDEBUG="${WINEDEBUG:-fixme-all,err-all}"
out="$here/$name.exe"
rm -f "$out" "$here/$name.obj"

set +e
wine "$MSVC_DIR/bin/cl.exe" /nologo /O2 /MT /W3 \
    "/I$(winepath -w "$repo/include")" \
    "/Fe$(winepath -w "$out")" "$(winepath -w "$src")" \
    /link /BASE:0x10000000 /INCREMENTAL:NO /SUBSYSTEM:CONSOLE \
    /FORCE:UNRESOLVED kernel32.lib "${objects[@]}"
set -e

rm -f "$here/$name.obj"
test -f "$out" || { echo "build.sh: cl/link produced no $out" >&2; exit 1; }
echo "recomp: built $out${*:+ (linked: $*)}"
