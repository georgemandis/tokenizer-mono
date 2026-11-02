#!/usr/bin/env bash
# Downloads the IBM Plex families we build on into vendor/plex/ (gitignored).
# The release assets are public, so no GitHub login is needed.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor/plex && cd vendor/plex
dl() { # tag asset
  [ -d "${2%.zip}" ] && { echo "have ${2%.zip}"; return; }
  url="https://github.com/IBM/plex/releases/download/$(printf '%s' "$1" | sed 's|@|%40|g; s|/|%2F|g')/$2"
  echo "fetching $2"
  curl -fsSL --retry 3 -o "$2" "$url"
  mkdir -p "${2%.zip}" && unzip -q "$2" -d "${2%.zip}" && rm "$2"
}
dl '@ibm/plex-mono@2.5.0'  ibm-plex-mono.zip
dl '@ibm/plex-serif@2.0.0' ibm-plex-serif.zip
dl '@ibm/plex-sans@1.1.0'  ibm-plex-sans.zip
