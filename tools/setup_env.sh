#!/usr/bin/env bash
# Rebuild the toolchain after a sandbox reset.
#
# A reset wipes everything outside /home/user/workspace, including Blender.
# This reinstalls it into /home/user/.local (no root needed) and pulls the
# handful of X11 libraries the official build links against.
#
# Usage:  bash tools/setup_env.sh && source tools/env.sh
set -euo pipefail

VER="4.2.1"
SERIES="4.2"
PREFIX="/home/user/.local"
BL="$PREFIX/blender/blender"

mkdir -p "$PREFIX/bin" "$PREFIX/libs"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$REPO/vendor/blender"

if [ ! -x "$BL" ]; then
  TARBALL=/tmp/blender.tar.xz
  # Prefer the copy vendored in the repo: no network, no re-download.
  # GitHub caps single files at 100 MB, so it is stored as 90 MB parts.
  if ls "$VENDOR"/blender-*.tar.xz.part* >/dev/null 2>&1; then
    echo "==> reassembling Blender from vendor/blender (offline)"
    cat "$VENDOR"/blender-*.tar.xz.part* > "$TARBALL"
    if [ -f "$VENDOR/SHA256SUMS" ]; then
      (cd "$VENDOR" && sha256sum -c SHA256SUMS --quiet) \
        && echo "    checksums ok" || echo "    !! checksum mismatch"
    fi
  else
    echo "==> downloading Blender ${VER}"
    curl -sL -o "$TARBALL" \
      "https://download.blender.org/release/Blender${SERIES}/blender-${VER}-linux-x64.tar.xz"
  fi
  mkdir -p "$PREFIX/blender"
  tar -xf "$TARBALL" -C "$PREFIX/blender" --strip-components=1
  ln -sf "$BL" "$PREFIX/bin/blender"
  echo "==> installed to $BL"
else
  echo "==> Blender already present"
fi

# X11 runtime deps. apt needs root here, so fetch the .debs and unpack locally.
NEED="libsm6 libice6 libxrender1 libxi6 libxxf86vm1 libxfixes3 libxkbcommon0"
if [ ! -f "$PREFIX/libs/usr/lib/x86_64-linux-gnu/libSM.so.6" ]; then
  echo "==> fetching X11 runtime libraries"
  tmp="$(mktemp -d)"
  cd "$tmp"
  for p in $NEED; do
    url="$(curl -s "https://packages.debian.org/bookworm/amd64/$p/download" \
           | grep -oE 'http://ftp[^"]*\.deb' | head -1)"
    [ -n "$url" ] && curl -sL -O "$url" || echo "   (skipped $p)"
  done
  for d in *.deb; do dpkg-deb -x "$d" "$PREFIX/libs"; done
  cd - >/dev/null
fi

cat > "$(dirname "$0")/env.sh" <<'ENV'
# source this before running blender
export LD_LIBRARY_PATH="/home/user/.local/libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PATH="/home/user/.local/bin:$PATH"
ENV

export LD_LIBRARY_PATH="$PREFIX/libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
"$PREFIX/bin/blender" --version | head -2
echo "==> ready.  run:  source tools/env.sh"
