"""Common helper functions for topic install scripts."""

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import tomllib

DOTFILES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOTFILES_ROOT))
from agents.shared import (  # noqa: F401
    AGENTS_MD,
    SKILLS_DIR,
    build_attribution,
    render_instructions,
)

HOME = Path.home()
HOME_STR = str(HOME)
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
XDG_CONFIG_HOME_STR = str(XDG_CONFIG_HOME)
XDG_DATA_HOME_STR = os.environ.get("XDG_DATA_HOME", str(HOME / ".local/share"))
XDG_CACHE_HOME_STR = os.environ.get("XDG_CACHE_HOME", str(HOME / ".cache"))
XDG_STATE_HOME_STR = os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state"))

OP_DEFAULT_ACCOUNT = "my"

# Local wall-clock time is intentional for human-readable backup suffixes.
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005

_DRY_RUN = False

# ssh paths are also used also by git/ topic
SSH_CONFIG_DIR = HOME / ".ssh"
SSH_CONFIG_AI_PATH = SSH_CONFIG_DIR / "config.ai"
SSH_ASKPASS_AI_PATH = XDG_CONFIG_HOME / "dotfiles" / "ssh-askpass-ai.sh"
AI_KEY_FILE = "ai_ed25519"
AI_KEY_PATH = SSH_CONFIG_DIR / AI_KEY_FILE
AI_KEY_PUB_FILE = AI_KEY_FILE + ".pub"
AI_KEY_PUB_PATH = SSH_CONFIG_DIR / AI_KEY_PUB_FILE


def info(msg):
    """Print an info message."""
    print(f"[INFO] {msg}")


def success(msg):
    """Print a success message."""
    print(f"[SUCCESS] {msg}")


def warn(msg):
    """Print a warning message."""
    print(f"[WARN] {msg}")


def error(msg):
    """Print an error message to stderr."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def dry(msg):
    """Print a dry-run message."""
    print(f"[DRY-RUN] {msg}")


def is_dry_run():
    """Return True when dry-run mode is active for this process."""
    return _DRY_RUN


def set_dry_run(value=True):
    """Explicitly set the dry-run flag."""
    global _DRY_RUN
    _DRY_RUN = bool(value)


def parse_dry_run(argv=None):
    """Read --dry-run from argv and update the dry-run flag.

    Safe to call from any install.py at the top of main(). Unknown args
    are ignored so topic scripts can still add their own argparse later.
    Returns True if dry-run mode is now active.
    """
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dry-run", action="store_true")
    args, _ = parser.parse_known_args(argv)
    if args.dry_run:
        set_dry_run(True)
    return is_dry_run()


def run_cmd(cmd, check=True, capture_output=False, env=None, shell=False, cwd=None):
    """Run a subprocess command, honouring dry-run mode.

    In dry-run mode, logs the command and returns a fake successful
    CompletedProcess without executing anything.
    """
    if _DRY_RUN:
        if isinstance(cmd, str):
            cmd_str = cmd
        else:
            cmd_str = " ".join(str(c) for c in cmd)
        dry(f"would run: {cmd_str}")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True,
        env=env,
        shell=shell,
        cwd=cwd,
    )


def command_exists(cmd):
    """Check if a command exists in PATH.

    In dry-run mode, reports commands as absent so installers exercise
    their installation paths without running anything.
    """
    if _DRY_RUN:
        dry(f"probe '{cmd}' as absent")
        return False
    result = subprocess.run(["which", cmd], capture_output=True, check=False)
    return result.returncode == 0


def app_exists(app_name):
    """Check if a macOS app exists in /Applications.

    Args:
        app_name: Name without .app suffix (e.g., 'Brave Browser')
    """
    if _DRY_RUN:
        dry(f"probe '{app_name}.app' as absent")
        return False
    return Path(f"/Applications/{app_name}.app").exists()


def brew_install(package, cask=False):
    """Install a package via Homebrew.

    Args:
        package: The brew formula or cask name
        cask: If True, install as cask (--cask flag)

    Returns:
        True on success, False on failure
    """
    if _DRY_RUN:
        suffix = " (cask)" if cask else ""
        dry(f"would brew install {package}{suffix}")
        return True

    cmd = ["brew", "install"]
    if cask:
        cmd.append("--cask")
    cmd.append(package)

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def brew_is_installed(package):
    """Check if a package is installed via Homebrew.

    In dry-run mode, reports packages as absent so the install path is
    exercised without changing the system.
    """
    if _DRY_RUN:
        dry(f"probe brew package '{package}' as absent")
        return False
    result = subprocess.run(["brew", "list", package], capture_output=True, check=False)
    return result.returncode == 0


def brew_uninstall(package):
    """Uninstall a Homebrew package if installed. Respects dry-run.

    Returns True if the package is absent (or successfully removed),
    False if uninstall failed.
    """
    if _DRY_RUN:
        dry(f"would brew uninstall {package} if installed")
        return True
    result = subprocess.run(["brew", "list", package], capture_output=True, check=False)
    if result.returncode != 0:
        return True
    try:
        subprocess.run(["brew", "uninstall", package], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def npm_install_global(package):
    """Install an npm package globally (into the active mise node).

    Returns True on success, False on failure.
    """
    if _DRY_RUN:
        dry(f"would run: npm install -g {package}")
        return True
    if not command_exists("npm"):
        error("npm not found; install the 'node' topic first")
        return False
    try:
        subprocess.run(["npm", "install", "-g", package], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def mise_use(tool_spec):
    """Run `mise use -g <tool_spec>`. Respects dry-run.

    Returns True on success, False on failure.
    """
    if _DRY_RUN:
        dry(f"would run: mise use -g {tool_spec}")
        return True
    try:
        subprocess.run(["mise", "use", "-g", tool_spec], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def chmod(path, mode):
    """Chmod a directory or file, honouring dry-run."""
    if mode is None:
        return
    if _DRY_RUN:
        dry("would ensure {path} permissions {mode}")
        return

    st_mode = path.stat().st_mode
    current_mode = st_mode & 0o777

    if current_mode != mode:
        path.chmod(mode)
        info(f"Set {path} permissions: {oct(current_mode)} -> {oct(mode)}")


def make_dir(path, mode=None, parents=True):
    """Create a directory, honouring dry-run."""
    path = Path(path)
    if _DRY_RUN:
        dry(f"would mkdir {path}")
        return

    if path.is_file():
        error(f"{path} exists and is a file")
        return

    if path.is_dir():
        chmod(path, mode)
        return

    if mode is None:
        path.mkdir(parents=parents, exist_ok=True)
    else:
        path.mkdir(mode=mode, parents=parents, exist_ok=True)


def write_file(path, content, mode=None):
    """Write text content to path, honouring dry-run.

    Creates parent directories. Applies `mode` (e.g. 0o600) if given.
    """
    path = Path(path)
    if _DRY_RUN:
        dry(f"would write {path} ({len(content)} bytes)")
        return
    make_dir(path.parent)
    path.write_text(content)
    chmod(path, mode)


def touch_file(path, mode=None):
    """Ensure file exists, honouring dry-run.

    Creates parent directories. Applies `mode` (e.g. 0o600) if given.
    """
    path = Path(path)
    if _DRY_RUN:
        dry(f"would touch {path}")
        return
    if path.exists():
        return

    make_dir(path.parent)
    if mode is None:
        path.touch()
    else:
        path.touch(mode)


def _toml_literal(value):
    """Serialise a Python scalar to its TOML literal form."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def set_toml_value(path, table, key, value):
    """Idempotently set a single ``key = value`` under ``[table]`` in a TOML file.

    Only the one key is managed: all other content, comments, and formatting
    are preserved, so the file is *not* brought fully under version control.
    Creates the file (or the ``[table]`` section, or the key) as needed, and
    replaces an out-of-date value in place. The edit is scoped to the target
    table's block, so a same-named key in another table is left alone.

    Honours dry-run mode. Returns True on success.
    """
    path = Path(path)
    setting_line = f"{key} = {_toml_literal(value)}"

    if not path.exists():
        if _DRY_RUN:
            dry(f"would create {path} with [{table}] {setting_line}")
            return True
        write_file(path, f"[{table}]\n{setting_line}\n")
        success(f"Created {path} with {setting_line}")
        return True

    text = path.read_text()
    if tomllib.loads(text).get(table, {}).get(key) == value:
        success(f"{path}: {table}.{key} already set")
        return True

    if _DRY_RUN:
        dry(f"would set {setting_line} under [{table}] in {path}")
        return True

    lines = text.splitlines(keepends=True)
    header_re = re.compile(rf"^\s*\[{re.escape(table)}\]\s*(?:#.*)?$")
    boundary_re = re.compile(r"^\s*\[")
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")

    table_start = next(
        (i for i, line in enumerate(lines) if header_re.match(line)), None
    )

    if table_start is None:
        sep = "\n" if text.endswith("\n") else "\n\n"
        new_text = f"{text}{sep}[{table}]\n{setting_line}\n"
    else:
        table_end = next(
            (
                j
                for j in range(table_start + 1, len(lines))
                if boundary_re.match(lines[j])
            ),
            len(lines),
        )
        for j in range(table_start + 1, table_end):
            if key_re.match(lines[j]):
                nl = "\n" if lines[j].endswith("\n") else ""
                lines[j] = setting_line + nl
                break
        else:
            lines.insert(table_start + 1, setting_line + "\n")
        new_text = "".join(lines)

    write_file(path, new_text)
    success(f"Set {setting_line} in {path}")
    return True


def get_short_hostname():
    """Get short hostname (without domain suffix)."""
    return socket.gethostname().split(".")[0]


def _deep_merge(base, override):
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def backup_file(file_path):
    """Back up an existing file or symlink before it's replaced."""
    path = Path(file_path)
    if not (path.exists() or path.is_symlink()):
        return
    if _DRY_RUN:
        dry(f"would back up {file_path}")
        return
    backup_dir = HOME / ".dotfiles-backup" / NOW
    try:
        relative_path = path.absolute().relative_to(HOME.absolute())
    except ValueError:
        relative_path = Path("__absolute__", *path.absolute().parts[1:])
    dest = backup_dir / relative_path
    make_dir(dest.parent)
    if dest.exists() or dest.is_symlink():
        counter = 1
        while True:
            candidate = dest.with_name(f"{dest.name}.{counter}")
            if not (candidate.exists() or candidate.is_symlink()):
                dest = candidate
                break
            counter += 1
    shutil.move(str(path), str(dest))
    info(f"Backed up {file_path} to {dest}")


def link_file(src, dst):
    """Symlink src to dst, backing up anything already at dst."""
    src_path = Path(src).resolve()
    dst_path = Path(dst)

    if dst_path.is_symlink():
        current_src = dst_path.resolve()
        if current_src == src_path.resolve():
            success(f"Already linked: {dst}")
            return True
        warn(f"Symlink exists but points elsewhere: {dst} -> {current_src}")
        backup_file(dst)
    elif dst_path.exists():
        warn(f"File exists: {dst}")
        backup_file(dst)

    if _DRY_RUN:
        dry(f"would link {dst} -> {src}")
        return True

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.symlink_to(src_path)
    success(f"Linked: {dst} -> {src}")
    return True


def get_git_email():
    """Return the global git user.email, or None if unset."""
    result = subprocess.run(
        ["git", "config", "--get", "user.email"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def render_agents_md(dst, mode=None):
    """Compile the master agent instructions to dst for a non-Claude agent.

    Replaces the settings.json attribution note with an explicit, machine-
    specific Co-Authored-By line, since these agents can't inject it themselves.
    """
    dst_path = Path(dst)
    content = render_instructions(get_git_email())

    # A previous install may have left a symlink here; writing through it would
    # clobber the master. Replace it with a real file.
    if dst_path.is_symlink():
        if _DRY_RUN:
            dry(f"would unlink {dst_path}")
        else:
            dst_path.unlink()

    write_file(dst_path, content, mode=mode)
    success(f"Compiled agent instructions: {dst_path}")


def link_directory(src, dst):
    """Symlink a directory to dst, backing up anything already at dst."""
    src_path = Path(src).resolve()
    dst_path = Path(dst)

    if dst_path.is_symlink():
        if dst_path.resolve() == src_path.resolve():
            success(f"Already linked: {dst}")
            return True
        backup_file(dst_path)
    elif dst_path.exists():
        backup_file(dst_path)

    if _DRY_RUN:
        dry(f"would link {dst} -> {src}")
        return True

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.symlink_to(src_path)
    success(f"Linked: {dst} -> {src}")
    return True


def load_symlink_mappings(topic_dir):
    """Load symlink destination overrides from <topic>/symlinks.txt.

    Each non-comment line has the form ``source.symlink -> destination``.
    ``$HOME``, the XDG base directory variables, and a leading ``~`` are
    expanded in destinations.
    """
    topic_dir = Path(topic_dir)
    mappings = {}
    symlinks_file = topic_dir / "symlinks.txt"
    if not symlinks_file.exists():
        return mappings

    for line in symlinks_file.read_text().strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " -> " not in line:
            continue

        src_name, dst_path = line.split(" -> ", 1)
        src_name = src_name.strip()
        dst_path = dst_path.strip()

        if dst_path == "~" or dst_path.startswith("~/"):
            dst_path = HOME_STR + dst_path[1:]
        dst_path = dst_path.replace("$HOME", HOME_STR)
        dst_path = dst_path.replace("$XDG_CONFIG_HOME", XDG_CONFIG_HOME_STR)
        dst_path = dst_path.replace("$XDG_DATA_HOME", XDG_DATA_HOME_STR)
        dst_path = dst_path.replace("$XDG_CACHE_HOME", XDG_CACHE_HOME_STR)
        dst_path = dst_path.replace("$XDG_STATE_HOME", XDG_STATE_HOME_STR)

        mappings[src_name] = Path(dst_path)

    return mappings


def install_symlinks(topic_dir):
    """Install every ``*.symlink`` file in ``topic_dir``.

    Destinations come from ``symlinks.txt`` when present; otherwise each
    file is linked to ``~/.<basename>`` (the filename without ``.symlink``).
    """
    topic_dir = Path(topic_dir)
    symlink_files = sorted(topic_dir.glob("*.symlink"))
    if not symlink_files:
        return True

    mappings = load_symlink_mappings(topic_dir)

    all_ok = True
    for src in symlink_files:
        if not src.is_file():
            continue
        dst = mappings.get(src.name, HOME / f".{src.stem}")
        if not link_file(src, dst):
            all_ok = False

    return all_ok


__machine_config = None

# Overrides which machine profile get_machine_config() loads, instead of the
# real short hostname. Mainly useful for tests and for the CI/`script/check.py`
# dry-run smoke test, which must behave the same on every runner regardless
# of its (never-enrolled) hostname. Not meant as a way to dodge enrollment on
# a real machine.
MACHINE_HOSTNAME_ENV = "DOTFILES_MACHINE_HOSTNAME"


def get_machine_config():
    """Load machine-specific configuration.

    Always loads machines/default.json, then requires and merges in
    machines/<hostname>.json, where <hostname> is the current machine's
    short hostname (or the DOTFILES_MACHINE_HOSTNAME environment variable,
    if set).

    A hostname with no dedicated machines/<hostname>.json is an unenrolled
    machine. We refuse to silently fall back to machines/default.json for
    it, because default.json intentionally has no SSH keys and no git
    signing key: falling back would make git/install.py generate a config
    with commit signing enabled but no signing key (every commit fails to
    sign) and would make 1password/install.py regenerate the SSH agent
    config with zero key entries (suppressing the agent's normal "expose
    all signed-in keys" fallback). Both are security-relevant and must
    fail loudly instead.

    Returns:
        tuple: (config_dict, hostname)

    Raises:
        SystemExit: if this hostname has no dedicated machine config file.
    """
    global __machine_config

    if __machine_config is not None:
        return __machine_config

    hostname = os.environ.get(MACHINE_HOSTNAME_ENV) or get_short_hostname()
    machines_dir = DOTFILES_ROOT / "machines"

    host_config_file = machines_dir / f"{hostname}.json"
    if not host_config_file.exists():
        error(
            f"No machine config for hostname '{hostname}': "
            f"{host_config_file} does not exist."
        )
        error(
            "This machine has not been enrolled. Falling back to "
            "machines/default.json is not safe here: it has no SSH keys "
            "and no git signing key, which would silently disable commit "
            "signing and the 1Password SSH agent's key exposure."
        )
        error(
            f"Enroll this machine by creating {host_config_file} (see "
            "'Machine-Specific Configuration' in README.md)."
        )
        sys.exit(1)

    # Always load default first
    with open(machines_dir / "default.json") as f:
        config = json.load(f)

    # Merge the required hostname-specific config on top
    with open(host_config_file) as f:
        config = _deep_merge(config, json.load(f))

    __machine_config = config, hostname
    return __machine_config


def get_machine_ssh_config():
    machine_config, _ = get_machine_config()
    return machine_config.get("ssh", {})


def find_ssh_key(name):
    ssh_keys = get_machine_ssh_config().get("keys", [])
    for ssh_key in ssh_keys:
        key_name = ssh_key["name"]
        if key_name != name:
            continue
        return ssh_key
    return None


def op_secret(value):
    """Normalise a 1Password secret reference.

    Accepts either:
    - a string ``"op://vault/item/field"`` — uses OP_DEFAULT_ACCOUNT
    - a dict ``{"ref": "op://...", "account": "schubergphilis"}``;
      ``account`` is optional and defaults to OP_DEFAULT_ACCOUNT.

    Returns ``(ref, account)``. Raises if the input is malformed.
    """
    if isinstance(value, str):
        return value, OP_DEFAULT_ACCOUNT
    if isinstance(value, dict):
        ref = value.get("ref")
        if not ref:
            raise ValueError(f"1Password secret object missing 'ref': {value!r}")
        return ref, value.get("account", OP_DEFAULT_ACCOUNT)
    raise TypeError(f"Unsupported 1Password secret reference: {value!r}")


def op_read_command(value):
    """Return a shell-safe ``op read --account X 'ref'`` command string."""
    ref, account = op_secret(value)
    return f"op read --account {shlex.quote(account)} {shlex.quote(ref)}"
