"""Common helper functions for topic install scripts."""

import argparse
import json
import os
import platform as platform_module
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


# --- Platform detection -------------------------------------------------
#
# These dotfiles target macOS and Arch-based Linux (specifically Omarchy).
# Topics declare which platforms they support in a `platforms.txt` file
# next to their `install.py`; see script/install.py. Within an installer,
# use `ensure_package()` rather than branching on these flags directly —
# only genuinely platform-shaped work (LaunchAgents, systemd units, Dock)
# should test them.

SYSTEM = platform_module.system()
IS_MACOS = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"

# The canonical platform name used by platforms.txt.
PLATFORM = "macos" if IS_MACOS else "linux" if IS_LINUX else SYSTEM.lower()


def _linux_distro_ids(os_release=Path("/etc/os-release")):
    """Return the set of distro identifiers from /etc/os-release.

    Includes both ``ID`` and every entry of ``ID_LIKE``, so Arch
    derivatives (Omarchy, EndeavourOS, Manjaro, Arch Linux ARM) all
    report "arch". Returns an empty set off Linux or when the file is
    missing (some containers).
    """
    ids = set()
    try:
        text = os_release.read_text()
    except OSError:
        return ids
    for raw in text.splitlines():
        key, _, value = raw.partition("=")
        if key not in ("ID", "ID_LIKE"):
            continue
        ids.update(value.strip().strip('"\'').split())
    return ids


LINUX_DISTRO_IDS = _linux_distro_ids() if IS_LINUX else set()

# True on Arch and its derivatives, i.e. wherever pacman/yay are the
# right package managers. Note this is False on the Ubuntu CI runner,
# which is why every installer must stay dry-run-safe there.
IS_ARCH = IS_LINUX and "arch" in LINUX_DISTRO_IDS

# True on Debian and its derivatives (Ubuntu), i.e. wherever apt is the
# package manager. The CI runner is Ubuntu, so dry-run there exercises the
# apt branch of every installer.
IS_DEBIAN = IS_LINUX and bool({"debian", "ubuntu"} & LINUX_DISTRO_IDS)


def _running_in_wsl(proc_version=Path("/proc/version")):
    """True inside Windows Subsystem for Linux.

    WSL exports ``WSL_DISTRO_NAME`` into every session it starts, and its
    kernel identifies itself as Microsoft's in /proc/version, which also
    covers sessions started some other way (cron, a systemd unit).
    """
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in proc_version.read_text().lower()
    except OSError:
        return False


# A WSL distro has no desktop of its own: the Windows host owns the
# browser, editor, fonts and the 1Password app. Topics that install those
# consult this rather than the distro flags.
IS_WSL = IS_LINUX and _running_in_wsl()

# Every platforms.txt value this host satisfies. `linux-desktop` is a
# Linux with a graphical session of its own; WSL has none, so a desktop
# topic lists `linux-desktop` rather than `linux` and is skipped there.
HOST_PLATFORMS = {PLATFORM}
if IS_LINUX and not IS_WSL:
    HOST_PLATFORMS.add("linux-desktop")

# Where the Linux 1Password app serves its SSH agent. Under WSL no app runs
# here; 1password/install.py bridges the Windows app's agent into this same
# path, so ssh's IdentityAgent needs no WSL special case.
OP_LINUX_AGENT_SOCKET = HOME / ".1password" / "agent.sock"

# git's gpg.ssh.program under WSL. op-ssh-sign ships only with the desktop
# app, so ssh/install.py generates this helper, which signs with ssh-keygen
# through the bridged agent instead.
SSH_SIGN_BRIDGE_PATH = XDG_CONFIG_HOME / "dotfiles" / "ssh-sign-1password-bridge.sh"

# Omarchy ships its own config tree; its presence is what distinguishes
# "an Arch box" from "the Omarchy desktop" for topics that theme it.
OMARCHY_ROOT = XDG_CONFIG_HOME / "omarchy"
# Omarchy 4 is a package and lives in /usr/share; before that it was a
# git checkout in the user's XDG data dir.
OMARCHY_SHARE_DIRS = (Path("/usr/share/omarchy"), Path(XDG_DATA_HOME_STR) / "omarchy")


def is_omarchy():
    """True when this machine runs Omarchy (its install tree is present)."""
    return IS_LINUX and any(path.is_dir() for path in OMARCHY_SHARE_DIRS)


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

    Uses shutil.which rather than shelling out to which(1): Arch does not
    ship a `which` binary at all (it is a separate `which` package that
    Omarchy does not install), so the subprocess form raised
    FileNotFoundError for every probe on Linux.

    In dry-run mode, reports commands as absent so installers exercise
    their installation paths without running anything.
    """
    if _DRY_RUN:
        dry(f"probe '{cmd}' as absent")
        return False
    return shutil.which(cmd) is not None


def app_exists(app_name):
    """Check if a macOS app exists in /Applications.

    macOS-only by construction: /Applications does not exist elsewhere,
    so this is always False on Linux. Cross-platform installers should
    probe with `ensure_package(..., command=...)` instead.

    Args:
        app_name: Name without .app suffix (e.g., 'Brave Browser')
    """
    if _DRY_RUN:
        dry(f"probe '{app_name}.app' as absent")
        return False
    return Path(f"/Applications/{app_name}.app").exists()


def _brew_available():
    """True when Homebrew is on PATH.

    Every brew_* helper checks this rather than assuming macOS. The
    Homebrew-only topics never run on Linux (they declare `macos` in
    their platforms.txt), but a few portable topics still ask "is the
    legacy Homebrew copy of X installed?" as a migration step, and
    shelling out to a `brew` that does not exist would raise
    FileNotFoundError instead of answering "no".
    """
    return shutil.which("brew") is not None


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

    if not _brew_available():
        error(f"Homebrew not found; cannot install {package}")
        return False

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
    if not _brew_available():
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
    if not _brew_available():
        return True
    result = subprocess.run(["brew", "list", package], capture_output=True, check=False)
    if result.returncode != 0:
        return True
    try:
        subprocess.run(["brew", "uninstall", package], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def pacman_is_installed(package):
    """Check whether an Arch package is installed locally.

    In dry-run mode, reports packages as absent so the install path is
    exercised without changing the system.
    """
    if _DRY_RUN:
        dry(f"probe pacman package '{package}' as absent")
        return False
    result = subprocess.run(["pacman", "-Qi", package], capture_output=True, check=False)
    return result.returncode == 0


def pacman_repo_of(package):
    """Return the repository holding `package`, or None if no repo has it.

    Omarchy configures an `[aur]` binary repo alongside core/extra, plus
    its own `[omarchy]` repo, so a good many nominally-AUR packages
    resolve here and never need a yay build.
    """
    if _DRY_RUN:
        dry(f"probe pacman repos for '{package}' as absent")
        return None
    result = subprocess.run(
        ["pacman", "-Si", package], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    # `pacman -Si` prints one block per repo carrying the name, in
    # pacman.conf order, each starting with "Repository : <name>". The
    # first is the one pacman itself would install from.
    for line in (result.stdout or "").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "Repository":
            return value.strip()
    return None


def pacman_install(target):
    """Install a fully qualified ``<repo>/<package>`` pacman target.

    The repo prefix is not cosmetic. A repository may set `Usage` in
    pacman.conf to something that excludes `Install`, and Omarchy's own
    repo does exactly that (`Usage = Sync`): `pacman -S 1password` fails
    with "target not found" even though `pacman -Si 1password` describes
    the package, while `pacman -S omarchy/1password` installs it. Passing
    a bare name would make every Omarchy-repo package look absent and
    fall through to an AUR source build.

    `--needed` makes this idempotent and `--noconfirm` keeps pacman from
    prompting; `sudo` may still ask for a password once per session, the
    same way a Homebrew cask does on macOS.

    Returns True on success, False on failure.
    """
    if _DRY_RUN:
        dry(f"would pacman -S {target}")
        return True
    try:
        subprocess.run(
            ["sudo", "pacman", "-S", "--needed", "--noconfirm", target], check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def aur_has(package):
    """Check whether yay can resolve `package` at all (repos or AUR)."""
    result = subprocess.run(["yay", "-Si", package], capture_output=True, check=False)
    return result.returncode == 0


def aur_install(package):
    """Install a package with yay, which covers both the AUR and the repos.

    Returns True on success, False on failure.
    """
    if _DRY_RUN:
        dry(f"would yay -S {package}")
        return True
    if not command_exists("yay"):
        error(f"yay not found; cannot install AUR package {package}")
        return False
    # Resolve the name first. Without this, a package that simply does not
    # exist under this name reaches yay as a build request and reports it
    # as a build failure, which reads as "it broke" rather than "there is
    # no such package".
    if not aur_has(package):
        error(f"No AUR or repository package named {package}")
        return False
    try:
        subprocess.run(
            ["yay", "-S", "--needed", "--noconfirm", package], check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def apt_is_installed(package):
    """Check whether a Debian package is installed locally.

    In dry-run mode, reports packages as absent so the install path is
    exercised without changing the system.
    """
    if _DRY_RUN:
        dry(f"probe apt package '{package}' as absent")
        return False
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and "install ok installed" in (result.stdout or "")


def apt_install(package):
    """Install a Debian package with apt-get, non-interactively.

    `--no-install-recommends` keeps a CLI install from dragging in a
    desktop's worth of Recommends; the topics name what they need.
    `sudo` may still ask for a password once per session.

    Returns True on success, False on failure.
    """
    if _DRY_RUN:
        dry(f"would apt-get install {package}")
        return True
    try:
        subprocess.run(
            [
                "sudo",
                "env",
                "DEBIAN_FRONTEND=noninteractive",
                "apt-get",
                "install",
                "-y",
                "--no-install-recommends",
                package,
            ],
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _mise_install(tool):
    """Install a tool globally with mise, the fallback where no native
    package exists (most CLI tools on Debian/Ubuntu, whose apt is stale).

    `mise use -g` is idempotent, so no separate presence probe is needed
    beyond the `command=` check the caller already made.
    """
    if not _DRY_RUN and not command_exists("mise"):
        error(f"mise not found; install the 'mise' topic before {tool}")
        return False
    return mise_use(tool)


def _linux_install(pacman=None, aur=None):
    """Install an Arch package, preferring a repo copy over an AUR build.

    Both candidate names are checked against the repos first: Omarchy
    ships prebuilt copies of plenty of nominally-AUR packages, and taking
    one of those beats spending minutes on a source build.
    """
    for name in (pacman, aur):
        if not name:
            continue
        repo = pacman_repo_of(name)
        if repo:
            return pacman_install(f"{repo}/{name}")
    if aur:
        return aur_install(aur)
    if pacman:
        # In no configured repo, and no separate AUR name was given. yay
        # can still find it in the AUR under the same name.
        return aur_install(pacman)
    return False


def ensure_package(
    label,
    *,
    brew=None,
    cask=False,
    pacman=None,
    aur=None,
    apt=None,
    mise=None,
    command=None,
    macos_app=None,
    optional=False,
):
    """Install `label` with this platform's package manager, if it is missing.

    Presence is probed in this order, using whichever probes apply:
    `command` (a binary on PATH), `macos_app` (an /Applications bundle,
    macOS only), then the platform's own package database.

    Package names are per-platform: `brew`/`cask` for macOS, `pacman`/`aur`
    for Arch, `apt` for Debian and Ubuntu. `mise` names a tool in the mise
    registry (or a `github:owner/repo` spec) and is the fallback for any
    platform without a native name: in practice Debian/Ubuntu, whose apt
    carries few developer CLIs and old versions of those. A platform with
    neither has no package for `label`; that is an error unless `optional`
    is set, which downgrades it to a warning so a mostly-portable topic can
    still install its config.

    Returns True when the package is present afterwards.
    """
    if command and command_exists(command):
        success(f"{label} already installed")
        return True
    if macos_app and IS_MACOS and app_exists(macos_app):
        success(f"{label} already installed")
        return True

    if IS_MACOS and brew:
        if brew_is_installed(brew):
            success(f"{label} already installed")
            return True
        info(f"Installing {label} via Homebrew...")
        installed = brew_install(brew, cask=cask)
    elif IS_ARCH and (pacman or aur):
        if pacman and pacman_is_installed(pacman):
            success(f"{label} already installed")
            return True
        if aur and pacman_is_installed(aur):
            success(f"{label} already installed")
            return True
        info(f"Installing {label} via pacman/yay...")
        installed = _linux_install(pacman=pacman, aur=aur)
    elif IS_DEBIAN and apt:
        if apt_is_installed(apt):
            success(f"{label} already installed")
            return True
        info(f"Installing {label} via apt...")
        installed = apt_install(apt)
    elif mise:
        info(f"Installing {label} via mise...")
        installed = _mise_install(mise)
    else:
        return _no_package_for_platform(label, optional)

    if installed:
        success(f"{label} installed")
        return True

    if optional:
        warn(f"Failed to install {label}; continuing")
        return True
    error(f"Failed to install {label}")
    return False


def _package_manager_name():
    """The package manager `ensure_package` would use here, for messages."""
    if IS_MACOS:
        return "Homebrew"
    if IS_ARCH:
        return "pacman/yay"
    if IS_DEBIAN:
        return "apt"
    return PLATFORM


def _no_package_for_platform(label, optional):
    manager = _package_manager_name()
    if optional:
        warn(f"No {manager} package configured for {label}; skipping")
        return True
    error(f"No {manager} package configured for {label}")
    return False


def sudo_write_file(path, content, mode="0644"):
    """Write `content` to a root-owned `path` through sudo, honouring dry-run.

    Only writes when the content differs, so a re-run neither prompts for
    a password nor touches the file's mtime. Returns True when the file
    was (re)written, False when it was already up to date or the write
    failed; failures are reported.
    """
    path = Path(path)
    try:
        if path.read_text() == content:
            success(f"{path} already up to date")
            return False
    except (FileNotFoundError, PermissionError):
        pass
    if _DRY_RUN:
        dry(f"would write {path} ({len(content)} bytes) via sudo")
        return True
    try:
        subprocess.run(["sudo", "install", "-d", "-m", "0755", str(path.parent)], check=True)
        subprocess.run(
            ["sudo", "tee", str(path)], input=content, text=True,
            stdout=subprocess.DEVNULL, check=True,
        )
        subprocess.run(["sudo", "chmod", mode, str(path)], check=True)
    except subprocess.CalledProcessError as exc:
        error(f"Failed to write {path}: {exc}")
        return False
    success(f"Wrote {path}")
    return True


def systemctl_enable(unit, user=False):
    """`systemctl enable --now <unit>`, as the user or via sudo. Respects dry-run.

    Idempotent: enabling an enabled, running unit is a no-op for systemd.
    Returns True on success.
    """
    cmd = ["systemctl", "--user"] if user else ["sudo", "systemctl"]
    cmd += ["enable", "--now", unit]
    result = run_cmd(cmd, check=False, capture_output=True)
    if result.returncode != 0:
        error(f"{' '.join(cmd)} failed: {(result.stderr or '').strip()}")
        return False
    success(f"{unit} enabled")
    return True


def ufw_allow(port, proto, comment, from_cidr=None):
    """Open `port`/`proto` in ufw, optionally only from `from_cidr`.

    ufw itself is idempotent ("Skipping adding existing rule"), so this
    needs no read-back, which would require sudo just to look. Machines
    without ufw (macOS, servers using nftables directly) are skipped with
    a warning rather than failed: the firewall is not this topic's to
    install. Returns True unless ufw is present and the rule failed.
    """
    if not command_exists("ufw"):
        warn(f"ufw is not installed; not opening {port}/{proto} for {comment}")
        return True
    cmd = ["sudo", "ufw", "allow"]
    if from_cidr:
        cmd += ["from", from_cidr, "to", "any"]
    cmd += ["port", str(port), "proto", proto, "comment", comment]
    result = run_cmd(cmd, check=False, capture_output=True)
    if result.returncode != 0:
        error(f"{' '.join(cmd)} failed: {(result.stderr or '').strip()}")
        return False
    success(f"ufw allows {port}/{proto} ({comment})" + (f" from {from_cidr}" if from_cidr else ""))
    return True


def get_remote_access_config():
    """This machine's `remoteAccess` block, or {} when it has none.

    Hosting SSH or a Sunshine stream is opt-in per machine; see
    'Machine-Specific Configuration' in README.md for the keys.
    """
    config, _ = get_machine_config()
    return config.get("remoteAccess", {})


def get_omarchy_config():
    """This machine's `omarchy` block, or {} when it has none.

    Per-machine desktop tweaks (terminal font size); see
    'Machine-Specific Configuration' in README.md for the keys.
    """
    config, _ = get_machine_config()
    return config.get("omarchy", {})


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


def load_symlink_mappings(topic_dir, platform=None):
    """Load symlink destination overrides from <topic>/symlinks.txt.

    Each non-comment line has the form ``source.symlink -> destination``.
    ``$HOME``, the XDG base directory variables, and a leading ``~`` are
    expanded in destinations.

    A line may be prefixed with ``<platform>:`` to restrict it to one
    platform, e.g.::

        macos: config.symlink -> $HOME/Library/Application Support/x/config
        linux: config.symlink -> $XDG_CONFIG_HOME/x/config

    Unprefixed lines apply everywhere. Lines for another platform are
    dropped, so the same source file can land in different places on
    macOS and Linux.
    """
    topic_dir = Path(topic_dir)
    platform = PLATFORM if platform is None else platform
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

        prefix, sep, remainder = line.partition(":")
        # Only treat this as a platform prefix when it precedes the
        # mapping arrow; a Windows-style destination path would also
        # contain a colon, and must not be mistaken for one.
        if sep and " -> " not in prefix:
            if prefix.strip() != platform:
                continue
            line = remainder.strip()

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


def get_provider_credential(provider):
    """Return the (op_account, op_ref) 1Password reference for a provider.

    Reads ``providers.<provider>`` from the CURRENT machine's config
    (``get_machine_config()``), mirroring how ``find_ssh_key`` reads
    per-machine SSH key config. There is no fallback to another
    machine's account/reference: a machine with no ``providers.<provider>``
    entry must fail closed rather than silently borrow credentials
    configured for a different machine.

    Raises ValueError with an actionable message if the current machine
    has no (complete) configuration for ``provider``.
    """
    machine_config, hostname = get_machine_config()
    entry = machine_config.get("providers", {}).get(provider)
    if not entry:
        raise ValueError(
            f"no {provider!r} provider credential configured for machine "
            f"{hostname!r}. Add providers.{provider}.op_account/op_ref to "
            f"machines/{hostname}.json (see machines/ documentation)."
        )
    op_account = entry.get("op_account")
    op_ref = entry.get("op_ref")
    if not op_account or not op_ref:
        raise ValueError(
            f"providers.{provider} for machine {hostname!r} is missing "
            "op_account or op_ref."
        )
    return op_account, op_ref


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
