#!/usr/bin/env bash
# Render PWA app icons — prefers Python/Pillow (works everywhere).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if python3 -c "import PIL" 2>/dev/null; then
  python3 "${ROOT}/scripts/generate_app_icons.py"
  exit 0
fi

ASSETS="${ROOT}/frontend/assets"

render() {
  local svg="$1"
  local png="$2"
  local size="$3"
  if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w "${size}" -h "${size}" "${svg}" -o "${png}"
  elif command -v convert >/dev/null 2>&1; then
    convert -background none -density 384 "${svg}" -resize "${size}x${size}" "${png}"
  else
    echo "Install Pillow (pip install pillow) or librsvg to generate PNG icons."
    exit 1
  fi
  echo "Wrote ${png} (${size}px)"
}

for base in app-icon-hr app-icon-hr-maskable app-icon-clock; do
  svg="${ASSETS}/${base}.svg"
  for size in 180 192 512; do
    render "${svg}" "${ASSETS}/${base}-${size}.png" "${size}"
  done
done

echo "App icon PNGs generated from SVG."
