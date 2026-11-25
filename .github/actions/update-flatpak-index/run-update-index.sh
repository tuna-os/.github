#!/bin/bash
# The one place that turns the action inputs into an update-index.py call.
# Both update-flatpak-index and publish-flatpak-index run it, so the tag check
# cannot be present in one and missing in the other. update-index.py must stay
# byte-identical to its canonical copy (AGENTS.md), so the check lives here.
#
# Inputs arrive as env, never interpolated into a script (AGENTS.md):
#   OCI_DIR, INDEX_FILE, REPO_NAME, REGISTRY, TAGS, REQUIRE_APPSTREAM
set -euo pipefail

# TAGS is split into words so a multi-tag list reaches argparse's nargs="+".
# Each word must match the OCI tag grammar. Without this check a word such as
# `--repo-name` would override an earlier argument: argparse keeps the last
# value, so the entry would be written under another app's key.
read -ra tag_args <<<"${TAGS:-}"
if [ "${#tag_args[@]}" -eq 0 ]; then
  echo "::error::tags input is empty" >&2
  exit 1
fi
for tag in "${tag_args[@]}"; do
  if ! [[ "$tag" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$ ]]; then
    echo "::error::invalid OCI tag: $tag" >&2
    exit 1
  fi
done

extra=()
if [ "${REQUIRE_APPSTREAM:-false}" = "true" ]; then
  extra+=(--require-appstream)
fi

python3 "$(dirname "${BASH_SOURCE[0]}")/update-index.py" \
  --oci-dir "$OCI_DIR" \
  --index-file "$INDEX_FILE" \
  --repo-name "$REPO_NAME" \
  --registry "$REGISTRY" \
  --tags "${tag_args[@]}" \
  "${extra[@]}"
