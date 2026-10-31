#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
[[ "$HOME" == /* ]] || fail 'HOME must be an absolute path.'
source_file="$ROOT/bin/git-user"
destination="$HOME/.local/bin/git-user"
[[ -x "$source_file" ]] || fail "Missing executable: $source_file"
mkdir -p -- "$(dirname -- "$destination")"

if [[ -L "$destination" && "$(readlink -- "$destination")" == "$source_file" ]]; then
  exit 0
fi
[[ ! -d "$destination" ]] || fail "Expected a file, found directory: $destination"
if [[ -e "$destination" || -L "$destination" ]]; then
  state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
  [[ "$state_home" == /* ]] || fail 'XDG_STATE_HOME must be an absolute path.'
  mkdir -p -- "$state_home/git-user/backups"
  backup_directory=$(mktemp -d "$state_home/git-user/backups/install.XXXXXXXX")
  mv -- "$destination" "$backup_directory/git-user"
  printf 'Preserved the previous command at %s\n' "$backup_directory/git-user"
fi
ln -s -- "$source_file" "$destination"
