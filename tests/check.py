#!/usr/bin/env python3
"""Offline checks for git-user using isolated command doubles."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]


def run(args, env, *, input_text=None, success=True):
    result = subprocess.run(args, env=env, input=input_text, text=True, capture_output=True)
    assert (result.returncode == 0) == success, (args, result.stdout, result.stderr)
    return result


def executable(path, content):
    path.write_text("#!/usr/bin/env bash\n" + content)
    path.chmod(0o755)


with tempfile.TemporaryDirectory(prefix="git-user-check.") as temporary:
    base = Path(temporary)
    repo = base / "repo"
    shutil.copytree(SOURCE / "bin", repo / "bin")
    (repo / ".gitignore").write_text(".env\n")
    home = base / "home"
    home.mkdir()
    commands = base / "commands"
    commands.mkdir()
    env = os.environ | {
        "HOME": str(home), "PATH": f"{commands}:/usr/bin:/bin",
        "XDG_STATE_HOME": str(home / "state"),
        "XDG_CONFIG_HOME": str(base / "config"),
        "CONFIG_READ_MARKER": str(base / "config-was-read"),
        "GH_ACCOUNTS": str(base / "gh-accounts"), "GH_ACTIVE": str(base / "gh-active"),
        "GH_LOG": str(base / "gh.log"), "GIT_LOG": str(base / "git.log"),
        "GUM_LOG": str(base / "gum.log"),
    }
    Path(env["GH_ACCOUNTS"]).write_text("personal\nwork\n")
    Path(env["GH_ACTIVE"]).write_text("personal\n")
    legacy_config = Path(env["XDG_CONFIG_HOME"]) / "shell/git-switch.conf"
    legacy_config.parent.mkdir(parents=True)
    legacy_config.write_text('touch "$CONFIG_READ_MARKER"\n')
    executable(
        commands / "gh",
        '''if [[ "$1 $2" == "auth status" ]]; then
  if [[ "${3:-}" == "--active" ]]; then
    account=$(cat "$GH_ACTIVE")
    [[ -n "$account" ]] && printf "Logged in to github.com account %s (keyring)\\n" "$account"
  else
    while IFS= read -r account; do
      [[ -n "$account" ]] && printf "Logged in to github.com account %s (keyring)\\n" "$account"
    done < "$GH_ACCOUNTS"
  fi
elif [[ "$1 $2" == "auth login" ]]; then
  printf "%s\\0" "$@" >> "$GH_LOG"
  account=${LOGIN_ACCOUNT:-}
  [[ -n "$account" ]] || exit 1
  grep -Fxq "$account" "$GH_ACCOUNTS" || printf "%s\\n" "$account" >> "$GH_ACCOUNTS"
  printf "%s\\n" "$account" > "$GH_ACTIVE"
elif [[ "$1 $2" == "auth switch" ]]; then
  printf "%s\\0" "$@" >> "$GH_LOG"
  printf "%s\\n" "$4" > "$GH_ACTIVE"
else
  exit 91
fi
''',
    )
    executable(
        commands / "git",
        'printf "%s\\0" "$@" >> "$GIT_LOG"; exit "${GIT_FAIL:-0}"\n',
    )
    executable(
        commands / "gum",
        '''[[ "$1" == choose ]] || exit 90
printf "%s\\0" "$@" >> "$GUM_LOG"
selected=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == --selected ]]; then selected="$2"; shift 2; else shift; fi
done
[[ "${GUM_CANCEL:-0}" == 0 ]] || exit 1
printf "%s\\n" "${GUM_SELECTION:-$selected}"
''',
    )
    command = ["bash", str(repo / "bin/git-user")]

    # Adding a new account authenticates and verifies it, then restores the previous account.
    result = run(
        command + ["--add"], env | {"LOGIN_ACCOUNT": "contractor"},
        input_text="contractor\ncontractor@example.invalid\n",
    )
    assert "Added contractor" in result.stdout
    assert Path(env["GH_ACTIVE"]).read_text().strip() == "personal"
    assert "GIT_USER_PROFILE_1_USERNAME=contractor" in (repo / ".env").read_text()
    assert (repo / ".env").stat().st_mode & 0o777 == 0o600
    assert b"auth\0login\0--web\0--clipboard\0auth\0switch\0--user\0personal\0" == Path(env["GH_LOG"]).read_bytes()
    assert not Path(env["GIT_LOG"]).exists()
    assert not Path(env["CONFIG_READ_MARKER"]).exists()

    # A mismatched browser login does not write the profile and restores the prior account.
    (repo / ".env").unlink()
    Path(env["GH_ACCOUNTS"]).write_text("personal\nwork\n")
    Path(env["GH_ACTIVE"]).write_text("personal\n")
    Path(env["GH_LOG"]).unlink()
    result = run(
        command + ["--add"], env | {"LOGIN_ACCOUNT": "different"},
        input_text="contractor\ncontractor@example.invalid\n", success=False,
    )
    assert "did not authenticate contractor" in result.stderr
    assert not (repo / ".env").exists()
    assert Path(env["GH_ACTIVE"]).read_text().strip() == "personal"

    # Switching preserves cancel behavior and applies the matching email.
    (repo / ".env").write_text(
        "GIT_USER_PROFILE_COUNT=2\n"
        "GIT_USER_PROFILE_1_USERNAME=personal\n"
        "GIT_USER_PROFILE_1_EMAIL=personal@example.invalid\n"
        "GIT_USER_PROFILE_2_USERNAME=work\n"
        "GIT_USER_PROFILE_2_EMAIL=work@example.invalid\n"
    )
    result = run(command, env | {"GUM_SELECTION": "work"})
    assert "Switched to work (work@example.invalid)." in result.stdout
    assert Path(env["GH_ACTIVE"]).read_text().strip() == "work"
    assert Path(env["GIT_LOG"]).read_bytes() == b"config\0--global\0user.email\0work@example.invalid\0"

    git_command_env = env | {"PATH": f"{repo / 'bin'}:{env['PATH']}", "GUM_SELECTION": "personal"}
    result = run(["/usr/bin/git", "user"], git_command_env)
    assert "Switched to personal (personal@example.invalid)." in result.stdout

    Path(env["GH_LOG"]).unlink(missing_ok=True)
    Path(env["GIT_LOG"]).unlink(missing_ok=True)
    result = run(command, env | {"GUM_CANCEL": "1"})
    assert "Switched to " not in result.stdout
    assert not Path(env["GH_LOG"]).exists()
    assert not Path(env["GIT_LOG"]).exists()

    # An unauthed selected profile is logged in and verified before switching.
    Path(env["GH_ACCOUNTS"]).write_text("personal\n")
    Path(env["GH_ACTIVE"]).write_text("personal\n")
    result = run(command, env | {"GUM_SELECTION": "work", "LOGIN_ACCOUNT": "work"})
    assert "Switched to work" in result.stdout
    assert Path(env["GH_ACTIVE"]).read_text().strip() == "work"
    assert b"auth\0login\0--web\0--clipboard\0" in Path(env["GH_LOG"]).read_bytes()

    # A failed Git email update restores the previous GitHub account.
    Path(env["GH_ACTIVE"]).write_text("personal\n")
    result = run(command, env | {"GUM_SELECTION": "work", "GIT_FAIL": "1"}, success=False)
    assert Path(env["GH_ACTIVE"]).read_text().strip() == "personal"
    assert "Failed to update" in result.stderr

    install_bin = home / ".local/bin"
    install_bin.mkdir(parents=True)
    old_command = install_bin / "git-user"
    old_command.write_text("previous command\n")
    run(["bash", str(SOURCE / "setup.sh")], env)
    assert old_command.is_symlink()
    install_backups = list((home / "state/git-user/backups").iterdir())
    assert len(install_backups) == 1
    assert (install_backups[0] / "git-user").read_text() == "previous command\n"
    run(["bash", str(SOURCE / "setup.sh")], env)
    assert list((home / "state/git-user/backups").iterdir()) == install_backups
    assert ".env" in (SOURCE / ".gitignore").read_text().splitlines()

print("PASS: profile add, authentication, selection, cancel, and rollback")
