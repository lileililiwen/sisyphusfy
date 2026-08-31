#!/bin/sh
set -eu

REPOSITORY="lileililiwen/sisyphusfy"
VERSION="${SISYPHUSFY_VERSION:-0.1.0}"
INSTALL_DIR="${SISYPHUSFY_INSTALL_DIR:-$HOME/.sisyphusfy/bin}"
DRY_RUN=false

usage() {
  cat <<EOF
Usage: install.sh [OPTIONS]

Install Sisyphusfy ${VERSION}

Options:
  --version VERSION    Override version (default: ${VERSION})
  --dir DIR            Install directory (default: ${INSTALL_DIR})
  --dry-run            Show what would be done without executing
  -h, --help           Show this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="$2"
      shift 2
      ;;
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

detect_platform() {
  platform=$(uname -s | tr '[:upper:]' '[:lower:]')
  arch=$(uname -m)

  case "$platform" in
    linux)
      platform="linux"
      ;;
    darwin)
      platform="darwin"
      ;;
    *)
      echo "Error: Unsupported platform: $platform" >&2
      echo "Supported platforms: linux, darwin" >&2
      exit 1
      ;;
  esac

  case "$arch" in
    x86_64|amd64)
      arch="x86_64"
      ;;
    aarch64|arm64)
      arch="aarch64"
      ;;
    *)
      echo "Error: Unsupported architecture: $arch" >&2
      echo "Supported architectures: x86_64, aarch64" >&2
      exit 1
      ;;
  esac

  # Only targets with a published artifact may be advertised. Anything else
  # (for example linux-aarch64) is deferred and would download a mislabeled
  # binary or fail with a missing checksum.
  case "${platform}-${arch}" in
    linux-x86_64|darwin-x86_64|darwin-aarch64)
      ;;
    *)
      echo "Error: no prebuilt release for ${platform}-${arch}" >&2
      echo "Supported targets: linux-x86_64, darwin-x86_64, darwin-aarch64" >&2
      echo "Install with 'pip install sisyphusfy' on this platform." >&2
      exit 1
      ;;
  esac

  echo "${platform}-${arch}"
}

fetch_checksums() {
  url="https://github.com/${REPOSITORY}/releases/download/v${VERSION}/SHA256SUMS.txt"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$url"
  else
    echo "Error: curl or wget required" >&2
    exit 1
  fi
}

verify_checksum() {
  file="$1"
  expected="$2"

  if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$file" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$file" | awk '{print $1}')
  else
    echo "Error: sha256sum or shasum required" >&2
    exit 1
  fi

  if [ "$actual" != "$expected" ]; then
    echo "Error: Checksum mismatch" >&2
    echo "  Expected: $expected" >&2
    echo "  Got:      $actual" >&2
    exit 1
  fi
}

main() {
  platform_arch=$(detect_platform)
  platform=$(echo "$platform_arch" | cut -d'-' -f1)
  arch=$(echo "$platform_arch" | cut -d'-' -f2)

  filename="sisyphusfy-${VERSION}-${platform}-${arch}.tar.gz"
  url="https://github.com/${REPOSITORY}/releases/download/v${VERSION}/${filename}"

  echo "Sisyphusfy ${VERSION} installer"
  echo "Platform: ${platform} (${arch})"
  echo "Install directory: ${INSTALL_DIR}"
  echo ""

  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] Would download: ${url}"
    echo "[dry-run] Would verify checksum"
    echo "[dry-run] Would extract to: ${INSTALL_DIR}"
    echo "[dry-run] Would print PATH instructions"
    exit 0
  fi

  echo "Fetching checksums..."
  checksums=$(fetch_checksums)
  expected=$(echo "$checksums" | grep "$filename" | awk '{print $1}')

  if [ -z "$expected" ]; then
    echo "Error: No checksum found for ${filename}" >&2
    echo "Available artifacts:" >&2
    echo "$checksums" | awk '{print "  " $2}' >&2
    exit 1
  fi

  echo "Downloading ${filename}..."
  tmpdir=$(mktemp -d)
  trap 'rm -rf "$tmpdir"' EXIT

  archive="${tmpdir}/${filename}"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$archive" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$archive" "$url"
  fi

  echo "Verifying checksum..."
  verify_checksum "$archive" "$expected"

  echo "Extracting..."
  mkdir -p "$INSTALL_DIR"
  tar xzf "$archive" -C "$INSTALL_DIR"

  echo ""
  echo "Installed to ${INSTALL_DIR}"
  echo ""
  echo "Add to your PATH:"
  case "$(uname -s)" in
    Darwin)
      echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
      echo ""
      echo "Add to ~/.zshrc or ~/.bashrc for persistence."
      ;;
    *)
      echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
      echo ""
      echo "Add to ~/.bashrc for persistence."
      ;;
  esac
}

main
