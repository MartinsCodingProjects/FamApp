#!/usr/bin/env bash
# Installs the tools the home server lacks into ~/.local, without root (BUILDPLAN A6):
#   - GNU make (the container image has none; extracted from the Ubuntu package)
#   - a JDK (Temurin 21, needed by ktlint and later engine-core)
# Idempotent. Package 1.3.1 folds this into `make setup`; it has to run once before
# make exists, so it stays a plain script.
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

case ":$PATH:" in
  *":$bin:"*) ;;
  *) echo "add $bin to PATH, e.g.: echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc" ;;
esac
