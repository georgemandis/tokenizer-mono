#!/usr/bin/env bash
# Downloads the IBM Plex families we build on into vendor/plex/ (gitignored).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor/plex && cd vendor/plex
dl() { # tag asset
  [ -d "${2%.zip}" ] && { echo "have ${2%.zip}"; return; }
  gh release download "$1" -R IBM/plex -p "$2"
  mkdir -p "${2%.zip}" && unzip -q "$2" -d "${2%.zip}" && rm "$2"
}
dl '@ibm/plex-mono@2.5.0'  ibm-plex-mono.zip
dl '@ibm/plex-serif@2.0.0' ibm-plex-serif.zip
dl '@ibm/plex-sans@1.1.0'  ibm-plex-sans.zip
