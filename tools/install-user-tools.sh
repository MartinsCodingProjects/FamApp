#!/usr/bin/env bash
# Installs the toolchain into ~/.local, without root (BUILDPLAN A6, 1.3.1). Idempotent.
#   - GNU make (the container image has none; extracted from the Ubuntu package)
#   - a JDK (Temurin 21, for ktlint and engine-core; SDKMAN needs unzip, which is missing)
#   - fnm + the Node version pinned in .node-version
#   - the Python version pinned in .python-version (via uv)
# `make setup` runs it; it also works before make exists.
set -euo pipefail

prefix="${HOME}/.local"
bin="${prefix}/bin"
mkdir -p "$bin"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if ! command -v make >/dev/null 2>&1 && [ ! -x "$bin/make" ]; then
  echo "installing GNU make into $bin"
  deb="make_4.3-4.1build2_amd64.deb"
  curl -sSfL "http://archive.ubuntu.com/ubuntu/pool/main/m/make-dfsg/$deb" -o "$tmp/$deb"
  dpkg-deb -x "$tmp/$deb" "$tmp/make"
  install -m 755 "$tmp/make/usr/bin/make" "$bin/make"
fi

jdk_dir="${prefix}/jdk-21"
if ! command -v java >/dev/null 2>&1 && [ ! -x "$jdk_dir/bin/java" ]; then
  echo "installing Temurin JDK 21 into $jdk_dir"
  curl -sSfL "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse" -o "$tmp/jdk.tar.gz"
  mkdir -p "$jdk_dir"
  tar -xzf "$tmp/jdk.tar.gz" -C "$jdk_dir" --strip-components=1
  ln -sf "$jdk_dir/bin/java" "$bin/java"
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fnm_dir="${prefix}/share/fnm"
if [ ! -x "$bin/fnm" ]; then
  echo "installing fnm into $bin"
  curl -sSfL "https://github.com/Schniz/fnm/releases/download/v1.39.0/fnm-linux.zip" -o "$tmp/fnm.zip"
  python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$tmp/fnm.zip" "$tmp/fnm"
  install -m 755 "$tmp/fnm/fnm" "$bin/fnm"
fi
node_version="$(cat "$root/.node-version")"
if ! FNM_DIR="$fnm_dir" "$bin/fnm" list | grep -q "v$node_version"; then
  echo "installing Node $node_version via fnm"
  FNM_DIR="$fnm_dir" "$bin/fnm" install "$node_version"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "installing uv into $bin"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$bin" UV_NO_MODIFY_PATH=1 sh
fi
uv python install --quiet "$(cat "$root/.python-version")"

case ":$PATH:" in
  *":$bin:"*) ;;
  *) echo "note: put $bin on PATH (make, java, fnm live there)" ;;
esac
echo "note: activate the pinned Node with: eval \"\$(FNM_DIR=$fnm_dir fnm env)\" && fnm use"
