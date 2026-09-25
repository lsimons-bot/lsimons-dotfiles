#!/usr/bin/env python3
"""
Installation script for lsimons-dotfiles
This script is safe to run multiple times (idempotent)

Supports macOS, Arch-based Linux (Omarchy) and Debian-based Linux
(Ubuntu, including under WSL2).

Steps:
1. Bootstrap the platform package manager and a modern Python
   (Homebrew + python@3 on macOS; pacman prerequisites + yay on Arch;
   apt prerequisites + the vendor apt repositories on Debian/Ubuntu)
2. Create ~/.dotfiles symlink
3. Setup XDG directories
4. Run topic-specific installation scripts (each installs its own symlinks)

Topics that only make sense on one platform declare that in a
``platforms.txt`` file next to their ``install.py`` (values: ``macos``,
``linux``, ``linux-desktop`` for a Linux with its own graphical session,
which excludes WSL); topics without one run everywhere. Unsupported
topics are skipped, and any dependency on a skipped topic is dropped
rather than treated as an error.

A machine whose ``machines/<hostname>.json`` has a ``topics`` list installs
only those topics. Dependencies on topics outside the list are dropped the
same way, so the list is the complete set: a lean machine names what it
wants instead of inheriting whatever the dependency graph pulls in.

Pass --dry-run to preview without touching the system. The flag is
propagated to each topic installer.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# Checked before importing helpers, which imports tomllib (new in 3.11).
# macOS ships Python 3.9.6 in the Command Line Tools, so on a genuinely
# fresh machine this script would otherwise die on an opaque
# `ModuleNotFoundError: No module named 'tomllib'` before reaching step 2
# above — the step that installs a newer Python. Fail with an instruction
# instead.
#
# Only the standard library sets this floor: the syntax here is still
# 3.9-compatible, so this guard itself parses on the stock interpreter
# and can report the problem.
MIN_PYTHON = (3, 11)
if sys.version_info < MIN_PYTHON:
    if platform.system() == 'Darwin':
        _hint = (
            "Install a newer Python first, then re-run this script:\n"
            "  brew install python\n"
            "If Homebrew is not installed yet either, install it first -- see\n"
            "https://brew.sh. This script installs Homebrew itself, but cannot\n"
            "get far enough to do so on this interpreter.\n"
        )
    else:
        _hint = (
            "Install a newer Python first, then re-run this script:\n"
            "  sudo pacman -S python              # Arch\n"
            "  sudo apt-get install -y python3    # Debian/Ubuntu\n"
        )
    sys.stderr.write(
        f"lsimons-dotfiles needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, "
        f"but this is {platform.python_version()}.\n"
        f"  interpreter: {sys.executable}\n"
        + _hint
    )
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (
    HOST_PLATFORMS,
    IS_ARCH,
    IS_DEBIAN,
    IS_LINUX,
    IS_MACOS,
    IS_WSL,
    PLATFORM,
    apt_is_installed,
    dry,
    get_machine_config,
    is_dry_run,
    set_dry_run,
)


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def info(message):
    """Print info message"""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")


def success(message):
    """Print success message"""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def warn(message):
    """Print warning message"""
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {message}")


def error(message):
    """Print error message"""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


def run_command(cmd, check=True, capture_output=False, shell=False):
    """Run a shell command and return result"""
    try:
        if shell:
            result = subprocess.run(
                cmd,
                shell=True,
                check=check,
                capture_output=capture_output,
                text=True
            )
        else:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=capture_output,
                text=True
            )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            error(f"Command failed: {cmd}")
            error(f"Exit code: {e.returncode}")
            if e.stderr:
                error(f"Error: {e.stderr}")
            raise
        return e


def check_platform():
    """Verify we're on a supported platform: macOS, Arch- or Debian-based Linux.

    Anything else still installs — the config-only topics are portable —
    but the package-installing ones have no package manager to reach for,
    so confirm first. In dry-run mode nothing is confirmed.
    """
    if IS_MACOS:
        success("Running on macOS")
        return
    if IS_LINUX:
        if IS_ARCH:
            success("Running on Arch-based Linux")
            return
        if IS_DEBIAN:
            success("Running on Debian-based Linux" + (" under WSL" if IS_WSL else ""))
            return
        warn("This is Linux, but neither an Arch nor a Debian derivative")
        warn("Topics that install packages expect pacman/yay or apt and will fail")
    else:
        warn("These dotfiles target macOS and Arch- or Debian-based Linux")
        warn(f"Detected: {platform.system()}")

    if is_dry_run():
        dry(f"unsupported platform '{PLATFORM}' OK for dry-run")
        return
    response = input("Continue anyway? (y/N): ")
    if response.lower() != 'y':
        info("Installation cancelled")
        sys.exit(0)


def check_homebrew():
    """Check if Homebrew is installed"""
    return shutil.which('brew') is not None


def install_homebrew():
    """Install Homebrew if not present"""
    info("Checking for Homebrew...")

    if is_dry_run():
        dry("assume Homebrew is installed; skipping bootstrap")
        return True

    if check_homebrew():
        success("Homebrew is already installed")
        info(f"Homebrew location: {shutil.which('brew')}")
        return True

    info("Installing Homebrew...")
    info("This may take several minutes and will require your password")

    # Homebrew installation command
    install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'

    try:
        run_command(install_cmd, shell=True)
        success("Homebrew installed successfully")

        # Add Homebrew to PATH for this session
        if platform.machine() == 'arm64':
            # Apple Silicon
            brew_path = '/opt/homebrew/bin'
        else:
            # Intel
            brew_path = '/usr/local/bin'

        if brew_path not in os.environ.get('PATH', ''):
            os.environ['PATH'] = f"{brew_path}:{os.environ['PATH']}"
            info(f"Added {brew_path} to PATH for this session")

        return True
    except subprocess.CalledProcessError:
        error("Failed to install Homebrew")
        return False


def check_homebrew_python():
    """Check if Python is installed via Homebrew"""
    if not check_homebrew():
        return False

    result = run_command(
        ['brew', 'list', 'python@3'],
        check=False,
        capture_output=True
    )
    return result.returncode == 0


def install_python():
    """Install Python via Homebrew"""
    info("Checking for Homebrew Python...")

    if is_dry_run():
        dry("assume Homebrew python@3 is installed; skipping bootstrap")
        return True

    if check_homebrew_python():
        success("Python is already installed via Homebrew")
        python_path = get_homebrew_python()
        info(f"Python location: {python_path}")

        # Get Python version
        result = run_command([python_path, '--version'], capture_output=True)
        python_version = result.stdout.strip()
        info(f"Python version: {python_version}")
        return True

    info("Installing Python via Homebrew...")

    try:
        run_command(['brew', 'install', 'python@3'])
        success("Python installed successfully")

        # Verify installation
        python_path = get_homebrew_python()
        result = run_command([python_path, '--version'], capture_output=True)
        python_version = result.stdout.strip()
        success(f"Installed: {python_version}")

        return True
    except subprocess.CalledProcessError:
        error("Failed to install Python")
        return False


def get_homebrew_python():
    """Get the path to Homebrew Python"""
    if is_dry_run():
        return sys.executable
    result = run_command(['brew', '--prefix', 'python@3'], capture_output=True)
    return str(Path(result.stdout.strip()) / 'bin' / 'python3')


# Packages every Arch install needs before the first topic installer runs:
# base-devel and git are what yay needs to build anything from the AUR, and
# python is the interpreter the topic installers run under.
ARCH_BOOTSTRAP_PACKAGES = ['base-devel', 'git', 'python']

# The Debian/Ubuntu equivalent. build-essential and git are what mise's
# cargo/pipx-style backends need to build anything; curl, ca-certificates
# and gnupg fetch and verify the vendor repository keys below; unzip is
# what tfenv (and other release-tarball tools) unpack with, and Ubuntu's
# WSL image does not ship it.
DEBIAN_BOOTSTRAP_PACKAGES = [
    'build-essential', 'git', 'curl', 'ca-certificates', 'gnupg', 'python3', 'unzip',
]

# Third-party apt repositories the topics rely on. Ubuntu's own archive
# carries no mise and no 1Password CLI, and its gh is a year stale, so
# these come from the vendors' repositories, each pinned to the vendor's
# signing key. Adding them is the Debian analogue of installing yay: it is
# what puts the rest of the packages within reach of `ensure_package`.
#
# `source` is formatted with the dpkg architecture and the keyring path.
# `extra_files` are (path, url, dearmor) triples written once when absent.
# `managed_by` lists files whose presence means the repository is already
# configured another way (extrepo, the vendor's other documented route),
# in which case nothing is added so apt does not see the same repo twice.
APT_KEYRINGS_DIR = Path('/etc/apt/keyrings')
APT_SOURCES_DIR = Path('/etc/apt/sources.list.d')
APT_REPOS = [
    {
        'name': 'mise',
        'key_url': 'https://mise.jdx.dev/gpg-key.pub',
        'keyring': APT_KEYRINGS_DIR / 'mise-archive-keyring.gpg',
        'source': (
            'deb [arch={arch} signed-by={keyring}] '
            'https://mise.jdx.dev/deb stable main'
        ),
        'list': APT_SOURCES_DIR / 'mise.list',
        'managed_by': [APT_SOURCES_DIR / 'extrepo_mise.sources'],
    },
    {
        'name': 'GitHub CLI',
        'key_url': 'https://cli.github.com/packages/githubcli-archive-keyring.gpg',
        'keyring': APT_KEYRINGS_DIR / 'githubcli-archive-keyring.gpg',
        'source': (
            'deb [arch={arch} signed-by={keyring}] '
            'https://cli.github.com/packages stable main'
        ),
        'list': APT_SOURCES_DIR / 'github-cli.list',
    },
    {
        'name': '1Password',
        'key_url': 'https://downloads.1password.com/linux/keys/1password.asc',
        'keyring': APT_KEYRINGS_DIR / '1password-archive-keyring.gpg',
        'source': (
            'deb [arch={arch} signed-by={keyring}] '
            'https://downloads.1password.com/linux/debian/{arch} stable main'
        ),
        'list': APT_SOURCES_DIR / '1password.list',
        # 1Password's .debs are also debsig-signed; this is the policy and
        # key debsig-verify checks them against, per the vendor's docs.
        'extra_files': [
            (
                Path('/etc/debsig/policies/AC2D62742012EA22/1password.pol'),
                'https://downloads.1password.com/linux/debian/debsig/1password.pol',
                False,
            ),
            (
                Path('/usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg'),
                'https://downloads.1password.com/linux/keys/1password.asc',
                True,
            ),
        ],
    },
]


def pacman_has(package):
    """True if `package` is installed locally (pacman -Qi)."""
    result = run_command(
        ['pacman', '-Qi', package], check=False, capture_output=True
    )
    return result.returncode == 0


def bootstrap_linux():
    """Install the distro's package prerequisites and its catch-all installer.

    Unlike the macOS bootstrap this cannot install its own package
    manager: pacman or apt comes with the distro. Arch gets its build
    prerequisites plus yay for the AUR; Debian/Ubuntu gets its build
    prerequisites plus the vendor apt repositories for mise, GitHub CLI
    and 1Password, mise being what installs most CLI tools there. Any
    other Linux is a warning rather than a failure — config-only topics
    still work there.
    """
    if is_dry_run():
        dry("assume package prerequisites and repositories are in place; skipping bootstrap")
        return True
    if IS_ARCH:
        return bootstrap_arch()
    if IS_DEBIAN:
        return bootstrap_debian()
    warn("Neither pacman nor apt found; skipping the Linux package bootstrap")
    warn("Topics that install packages will fail on this system")
    return True


def bootstrap_arch():
    """Install the pacman prerequisites and yay, the AUR helper."""
    info("Checking Arch package prerequisites...")

    missing = [pkg for pkg in ARCH_BOOTSTRAP_PACKAGES if not pacman_has(pkg)]
    if missing:
        info(f"Installing prerequisites: {', '.join(missing)}")
        try:
            run_command(
                ['sudo', 'pacman', '-S', '--needed', '--noconfirm', *missing]
            )
        except subprocess.CalledProcessError:
            error("Failed to install Arch prerequisites")
            return False
        success("Arch prerequisites installed")
    else:
        success("Arch prerequisites already installed")

    if shutil.which('yay') is not None:
        success("yay already installed")
        return True

    info("Installing yay (AUR helper)...")
    try:
        run_command(['sudo', 'pacman', '-S', '--needed', '--noconfirm', 'yay'])
        success("yay installed")
    except subprocess.CalledProcessError:
        warn("Could not install yay from a configured repository")
        warn("AUR-only packages will fail; see https://github.com/Jguer/yay")

    return True


def dpkg_architecture():
    """The dpkg architecture name (amd64, arm64) the apt sources need."""
    result = run_command(['dpkg', '--print-architecture'], capture_output=True)
    return result.stdout.strip()


# mise.jdx.dev answers 403 to Python's default "Python-urllib/x.y" agent
# (a bot filter); a descriptive one is accepted everywhere.
FETCH_USER_AGENT = 'lsimons-dotfiles (+https://github.com/lsimons/lsimons-dotfiles)'


def fetch_url(url):
    """Download `url` and return its bytes; raises on any HTTP or network error."""
    request = urllib.request.Request(url, headers={'User-Agent': FETCH_USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def dearmor(key):
    """Turn an ASCII-armored OpenPGP key into the binary form apt wants.

    Keys that are already binary (GitHub's) pass through unchanged.
    """
    if not key.lstrip().startswith(b'-----BEGIN'):
        return key
    result = subprocess.run(
        ['gpg', '--dearmor'], input=key, capture_output=True, check=True
    )
    return result.stdout


def sudo_write(path, data, mode='0644'):
    """Write `data` to a root-owned `path`, creating parent directories."""
    run_command(['sudo', 'install', '-d', '-m', '0755', str(path.parent)])
    subprocess.run(
        ['sudo', 'tee', str(path)], input=data, stdout=subprocess.DEVNULL, check=True
    )
    run_command(['sudo', 'chmod', mode, str(path)])


def ensure_apt_repo(repo, arch):
    """Add one vendor apt repository if it is not already configured.

    The keyring and any extra files are written once and then left
    alone; the sources entry is rewritten whenever it differs from the
    expected line. Returns True when anything changed, so the caller
    knows to refresh apt's package lists.
    """
    for managed in repo.get('managed_by', ()):
        if managed.exists():
            success(f"{repo['name']} apt repository already configured ({managed.name})")
            return False

    changed = False
    keyring = repo['keyring']
    if not keyring.exists():
        info(f"Adding the {repo['name']} apt signing key...")
        sudo_write(keyring, dearmor(fetch_url(repo['key_url'])))
        changed = True

    source = repo['source'].format(arch=arch, keyring=keyring) + '\n'
    sources_list = repo['list']
    if not sources_list.exists() or sources_list.read_text() != source:
        info(f"Adding the {repo['name']} apt repository...")
        sudo_write(sources_list, source.encode())
        changed = True

    for path, url, needs_dearmor in repo.get('extra_files', ()):
        if path.exists():
            continue
        data = fetch_url(url)
        sudo_write(path, dearmor(data) if needs_dearmor else data)
        changed = True

    if changed:
        success(f"{repo['name']} apt repository configured")
    else:
        success(f"{repo['name']} apt repository already configured")
    return changed


def apt_update():
    run_command(['sudo', 'apt-get', 'update'])


def bootstrap_debian():
    """Install the apt prerequisites and the vendor repositories."""
    info("Checking Debian package prerequisites...")

    missing = [pkg for pkg in DEBIAN_BOOTSTRAP_PACKAGES if not apt_is_installed(pkg)]
    if missing:
        info(f"Installing prerequisites: {', '.join(missing)}")
        try:
            apt_update()
            run_command(
                [
                    'sudo', 'env', 'DEBIAN_FRONTEND=noninteractive',
                    'apt-get', 'install', '-y', '--no-install-recommends', *missing,
                ]
            )
        except subprocess.CalledProcessError:
            error("Failed to install Debian prerequisites")
            return False
        success("Debian prerequisites installed")
    else:
        success("Debian prerequisites already installed")

    arch = dpkg_architecture()
    changed = False
    for repo in APT_REPOS:
        try:
            changed = ensure_apt_repo(repo, arch) or changed
        except (OSError, subprocess.CalledProcessError) as exc:
            error(f"Failed to configure the {repo['name']} apt repository: {exc}")
            return False

    if changed:
        try:
            apt_update()
        except subprocess.CalledProcessError:
            error("apt-get update failed after adding repositories")
            return False
    return True


def bootstrap_platform():
    """Install the platform package manager and a modern Python.

    Returns the interpreter path the topic installers should run under,
    or None if the bootstrap failed.
    """
    if IS_MACOS:
        if not install_homebrew():
            error("Homebrew installation failed. Cannot continue.")
            return None
        if not install_python():
            error("Python installation failed. Cannot continue.")
            return None
        return get_homebrew_python()

    if IS_LINUX:
        if not bootstrap_linux():
            return None
        # pacman's `python` is current (Arch is a rolling release), Ubuntu
        # 24.04's 3.12 clears the guard at the top of this file, and that
        # guard has already vetted this interpreter, so there is nothing to
        # install a newer one *for*.
        return sys.executable

    warn(f"No package-manager bootstrap for platform '{PLATFORM}'")
    return sys.executable


def create_dotfiles_symlink(dotfiles_root):
    """Create ~/.dotfiles symlink if it doesn't already exist"""
    home = Path.home()
    symlink_path = home / '.dotfiles'

    info("Setting up ~/.dotfiles symlink...")

    # Check if symlink already exists and points to the correct location
    if symlink_path.is_symlink():
        current_target = symlink_path.resolve()
        if current_target == dotfiles_root:
            success("~/.dotfiles symlink already points to correct location")
            return True
        else:
            warn(f"~/.dotfiles exists but points to: {current_target}")
            warn(f"Expected: {dotfiles_root}")
            if is_dry_run():
                dry("would prompt to recreate ~/.dotfiles symlink")
                return True
            response = input("Remove and recreate symlink? (y/N): ")
            if response.lower() != 'y':
                info("Skipping symlink creation")
                return False
            symlink_path.unlink()

    # Check if a regular directory exists at ~/.dotfiles
    elif symlink_path.exists():
        error("~/.dotfiles exists as a directory or file, not a symlink")
        error(f"Please move or remove {symlink_path} manually")
        return False

    if is_dry_run():
        dry(f"would create symlink ~/.dotfiles -> {dotfiles_root}")
        return True

    # Create the symlink
    try:
        symlink_path.symlink_to(dotfiles_root)
        success(f"Created symlink: ~/.dotfiles -> {dotfiles_root}")
        return True
    except Exception as e:  # noqa: BLE001 - report any symlink failure, keep going
        error(f"Failed to create symlink: {e}")
        return False


def setup_xdg():
    """Setup XDG Base Directory structure"""
    info("Setting up XDG Base Directory structure...")

    home = Path.home()
    xdg_config_home = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    xdg_data_home = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    xdg_cache_home = Path(os.environ.get('XDG_CACHE_HOME', home / '.cache'))
    xdg_state_home = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state'))

    if is_dry_run():
        for p in (xdg_config_home, xdg_data_home, xdg_cache_home, xdg_state_home):
            dry(f"would mkdir {p}")
        return

    xdg_config_home.mkdir(parents=True, exist_ok=True)
    xdg_data_home.mkdir(parents=True, exist_ok=True)
    xdg_cache_home.mkdir(parents=True, exist_ok=True)
    xdg_state_home.mkdir(parents=True, exist_ok=True)

    success("XDG directories created")


# Topics that must run after all others, in this exact order. They are
# excluded from the normal dependency-sorted pass and run last so the apps
# and tools they reference are guaranteed to be installed first.
FINAL_TOPICS = ['dock']


def _read_list_file(path):
    """Read a one-entry-per-line config file, ignoring blanks and comments."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            entries.append(line)
    return entries


def get_topic_dependencies(topic_dir):
    """Read dependencies from a topic's dependencies.txt file"""
    return _read_list_file(topic_dir / 'dependencies.txt')


def get_topic_platforms(topic_dir):
    """Read the platforms a topic supports from its platforms.txt file.

    Returns None when the file is absent, which means "every platform" —
    that is the case for the large majority of topics, so only the ones
    that are genuinely platform-bound need to say anything.
    """
    platforms_file = topic_dir / 'platforms.txt'
    if not platforms_file.exists():
        return None
    return set(_read_list_file(platforms_file))


def topic_supported(topic_dir):
    """True if this topic should be installed on the current platform."""
    platforms = get_topic_platforms(topic_dir)
    return platforms is None or bool(platforms & HOST_PLATFORMS)


def get_topic_allowlist():
    """Return the machine's ``topics`` list as a set, or None for every topic."""
    config, _ = get_machine_config()
    topics = config.get('topics')
    return None if topics is None else set(topics)


def unknown_allowlisted_topics(dotfiles_root, allowlist):
    """Return allowlisted names that are not a topic with an install.py."""
    return sorted(
        name for name in allowlist
        if not (dotfiles_root / name / 'install.py').exists()
    )


def topological_sort(topics, dependencies):
    """
    Sort topics so dependencies come before dependents.
    topics: dict of topic_name -> install_script_path
    dependencies: dict of topic_name -> list of dependency topic names
    Returns: list of topic names in installation order
    """
    unknown = sorted(
        (topic, dep)
        for topic, deps in dependencies.items()
        for dep in deps
        if dep not in topics
    )
    if unknown:
        for topic, dep in unknown:
            error(f"Topic '{topic}' depends on unknown topic '{dep}'")
        return None

    # Build in-degree map and adjacency list
    in_degree = {topic: 0 for topic in topics}
    dependents = {topic: [] for topic in topics}

    for topic, deps in dependencies.items():
        for dep in deps:
            in_degree[topic] += 1
            dependents[dep].append(topic)

    # Kahn's algorithm for topological sort
    queue = [topic for topic, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        # Sort queue for deterministic ordering
        queue.sort()
        topic = queue.pop(0)
        result.append(topic)

        for dependent in dependents[topic]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(topics):
        # Cycle detected
        remaining = set(topics.keys()) - set(result)
        error(f"Circular dependency detected involving: {remaining}")
        return None

    return result


def run_topic_installers(dotfiles_root, python_path):
    """Run topic-specific installation scripts in dependency order"""
    info("Looking for topic installation scripts...")

    topics = {}  # topic_name -> install_script_path
    dependencies = {}  # topic_name -> list of dependencies
    skipped = []  # topic names excluded on this platform
    excluded = []  # topic names left out of this machine's `topics` list

    allowlist = get_topic_allowlist()
    if allowlist is not None:
        unknown = unknown_allowlisted_topics(dotfiles_root, allowlist)
        if unknown:
            error(
                f"Machine config lists unknown topic(s): {', '.join(unknown)}"
            )
            return False
        info(f"Machine config limits topics to: {', '.join(sorted(allowlist))}")

    # Find all install.py scripts and their dependencies
    for topic_dir in dotfiles_root.iterdir():
        # Skip script directory to avoid recursive invocation
        if (topic_dir.is_dir()
                and not topic_dir.name.startswith('.')
                and topic_dir.name != 'script'
                and topic_dir.name not in FINAL_TOPICS):
            install_py = topic_dir / 'install.py'
            if install_py.exists():
                topic_name = topic_dir.name
                if allowlist is not None and topic_name not in allowlist:
                    excluded.append(topic_name)
                    continue
                if not topic_supported(topic_dir):
                    skipped.append(topic_name)
                    continue
                topics[topic_name] = install_py
                dependencies[topic_name] = get_topic_dependencies(topic_dir)

    if excluded:
        info(
            f"Skipping {len(excluded)} topic(s) not in this machine's topics: "
            f"{', '.join(sorted(excluded))}"
        )
    if skipped:
        info(
            f"Skipping {len(skipped)} topic(s) not supported on {PLATFORM}: "
            f"{', '.join(sorted(skipped))}"
        )

    # A dependency on a topic that is skipped on this platform, or left out
    # of the machine's topics, is not an error: the dependent topic just
    # loses an ordering constraint it no longer needs. Dropping it here
    # keeps topological_sort's genuine "depends on a topic that does not
    # exist" check meaningful.
    reasons = {name: f"skipped on {PLATFORM}" for name in skipped}
    reasons.update({name: "not in this machine's topics" for name in excluded})
    for topic_name, deps in dependencies.items():
        dropped = [dep for dep in deps if dep in reasons]
        if dropped:
            info(
                f"{topic_name}: dropping dependency on "
                + ", ".join(f"{dep} ({reasons[dep]})" for dep in sorted(dropped))
            )
            dependencies[topic_name] = [d for d in deps if d not in reasons]

    if not topics:
        info("No topic install.py scripts found")
        return True

    info(f"Found {len(topics)} topic installer(s)")

    # Sort topics by dependencies
    sorted_topics = topological_sort(topics, dependencies)
    if sorted_topics is None:
        return False

    child_args = ['--dry-run'] if is_dry_run() else []

    # Run each installer in order
    for topic in sorted_topics:
        script = topics[topic]
        deps = dependencies[topic]
        if deps:
            info(f"Running installer for: {topic} (depends on: {', '.join(deps)})")
        else:
            info(f"Running installer for: {topic}")

        try:
            run_command([python_path, str(script), *child_args])
            success(f"Installed: {topic}")
        except subprocess.CalledProcessError:
            error(f"Failed to install: {topic}")
            return False

    return True


def run_final_topics(dotfiles_root, python_path):
    """Run the FINAL_TOPICS installers last, in declared order."""
    child_args = ['--dry-run'] if is_dry_run() else []
    allowlist = get_topic_allowlist()

    for topic in FINAL_TOPICS:
        topic_dir = dotfiles_root / topic
        script = topic_dir / 'install.py'
        if not script.exists():
            continue
        if allowlist is not None and topic not in allowlist:
            info(f"Skipping final topic {topic}: not in this machine's topics")
            continue
        if not topic_supported(topic_dir):
            info(f"Skipping final topic {topic}: not supported on {PLATFORM}")
            continue
        info(f"Running final installer for: {topic}")
        try:
            run_command([python_path, str(script), *child_args])
            success(f"Installed: {topic}")
        except subprocess.CalledProcessError:
            error(f"Failed to install: {topic}")
            return False

    return True


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would happen without making any changes.',
    )
    return parser.parse_args(argv)


def main():
    """Main installation flow"""
    args = parse_args()
    set_dry_run(args.dry_run)

    info("Starting lsimons-dotfiles installation")
    if is_dry_run():
        dry("dry-run mode: no changes will be made")
    info("=" * 50)

    # Get dotfiles root directory
    script_dir = Path(__file__).resolve().parent
    dotfiles_root = script_dir.parent.resolve()
    info(f"Dotfiles root: {dotfiles_root}")

    # Step 1: Check the platform
    check_platform()

    # Step 2: Bootstrap the package manager and a modern Python
    python_path = bootstrap_platform()
    if python_path is None:
        sys.exit(1)
    success(f"Using Python: {python_path}")

    # Step 3: Create ~/.dotfiles symlink
    info("=" * 50)
    if not create_dotfiles_symlink(dotfiles_root):
        error("Failed to create ~/.dotfiles symlink")
        sys.exit(1)

    # Step 4: Setup XDG directories
    setup_xdg()

    # Step 5: Add mise shims to PATH so topic installers can find mise-managed
    # tools (e.g. npm) even before the shell config topics have been sourced.
    xdg_data_home = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    mise_shims = str(xdg_data_home / 'mise' / 'shims')
    if mise_shims not in os.environ.get('PATH', '').split(':'):
        os.environ['PATH'] = f"{mise_shims}:{os.environ['PATH']}"
        info(f"Added mise shims to PATH: {mise_shims}")

    # Step 6: Run topic installers (each installs its own .symlink files)
    info("=" * 50)
    if not run_topic_installers(dotfiles_root, python_path):
        error("Some topic installations failed")
        sys.exit(1)

    # Step 7: Run final topics (e.g. dock) after everything else
    if not run_final_topics(dotfiles_root, python_path):
        error("Some topic installations failed")
        sys.exit(1)

    # Done
    success("=" * 50)
    if is_dry_run():
        success("Dry-run complete. No changes made.")
    else:
        success("Installation complete!")
        info("")
        info("Next steps:")
        info("  1. Restart your shell (or 'source ~/.zshrc') to load the config")
        info("  2. Configure 1Password CLI for secret management")
        if IS_LINUX:
            info("  3. Enable the 1Password SSH agent in the desktop app's")
            info("     Developer settings, so git commit signing works")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Installation cancelled by user")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001 - top-level catch-all for clean exit
        error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
