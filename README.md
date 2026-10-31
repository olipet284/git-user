# git-user

An interactive `git user` subcommand for switching between GitHub accounts and
their global Git email addresses.

## Requirements

- Bash
- Git
- GitHub CLI (`gh`)
- Gum (`gum`)
- GNU/Linux with standard GNU Coreutils

The command uses `gh` for authentication; it never stores credentials in this
repository.

## Install

```bash
./setup.sh
```

The installer links `bin/git-user` to `~/.local/bin/git-user`. Ensure that
`~/.local/bin` is on `PATH`. If that command path already contains another file
or symlink, the installer preserves it under
`${XDG_STATE_HOME:-$HOME/.local/state}/git-user/backups`.

## Add profiles

Run `git user --add` and enter a GitHub username and Git email. The command
authenticates that account with `gh`, verifies the authenticated username, then
saves the profile in the local `.env` file beside this repository. The file is
created with owner-only permissions and is ignored by Git. Profiles are not
imported from dotfiles or committed to the public repository.

Run `git user` to choose a saved username. The active account is preselected
when it has a saved profile. If a profile is no longer authenticated, the
command runs `gh auth login` and verifies the account before switching. Canceling
the chooser leaves GitHub and Git settings unchanged. If changing the global
Git email fails, the command attempts to restore the previously active GitHub
account.

The profile file is a local key/value file managed by `git user --add`; do not
edit it while the command is running. If the profile file is missing or invalid,
add profiles again with `git user --add`.

## Check

```bash
python3 tests/check.py
```
