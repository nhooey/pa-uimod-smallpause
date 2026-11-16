#!/usr/bin/env bash
# Checks that modinfo.json is a manifest Planetary Annihilation can load:
# valid JSON with the fields the game and PAMM read, and every coui:// scene
# script and the icon resolving to a file in the repository.
# Usage: tests/check-modinfo.sh [repository root]   (default: current directory)
set -euo pipefail

root=${1:-.}
manifest="$root/modinfo.json"
failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

if ! jq -e 'type == "object"' "$manifest" >/dev/null; then
  echo "FAIL: $manifest is not a JSON object" >&2
  exit 1
fi

for field in context identifier display_name version id scenes; do
  jq -e --arg f "$field" 'has($f) and .[$f] != "" and .[$f] != null' "$manifest" >/dev/null ||
    fail "modinfo.json has no \"$field\""
done

jq -e '.context == "client"' "$manifest" >/dev/null ||
  fail "modinfo.json context is not \"client\""

jq -e '.version | test("^[0-9]+\\.[0-9]+\\.[0-9]+$")' "$manifest" >/dev/null ||
  fail "modinfo.json version is not MAJOR.MINOR.PATCH"

scripts=$(jq -r '.scenes | to_entries[] | .value[]' "$manifest")
[ -n "$scripts" ] || fail "modinfo.json scenes lists no scripts"

while IFS= read -r url; do
  [ -n "$url" ] || continue
  case $url in
    coui://*) path=${url#coui://} ;;
    *) fail "scene script $url is not a coui:// URL"; continue ;;
  esac
  [ -f "$root/$path" ] || fail "scene script $url has no file at $path"
done <<<"$scripts"

# The icon is served from GitHub's raw host; its path after the branch must
# exist here, or the PAMM listing shows a broken image.
icon=$(jq -r '.icon // empty' "$manifest")
if [ -n "$icon" ]; then
  icon_path=$(sed -E 's#^https://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/##' <<<"$icon")
  [ "$icon_path" != "$icon" ] || fail "icon $icon is not a raw.githubusercontent.com URL"
  [ -f "$root/$icon_path" ] || fail "icon $icon has no file at $icon_path"
fi

if [ "$failures" -gt 0 ]; then
  echo "$failures modinfo.json check(s) failed" >&2
  exit 1
fi
echo "modinfo.json OK"
