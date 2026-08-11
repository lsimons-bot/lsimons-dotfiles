#!/usr/bin/env python3
"""
Installation script for lsimons-dotfiles
This script is safe to run multiple times (idempotent)

Steps:
1. Install Homebrew (if not present)
2. Install Python via Homebrew (if not present)
3. Create ~/.dotfiles symlink
4. Setup XDG directories
5. Run topic-specific installation scripts (each installs its own symlinks)

Pass --dry-run to preview without touching the system. The flag is
propagated to each topic installer.
"""

import argparse
import os
import platform
import subprocess
import sys
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
    sys.stderr.write(
        "lsimons-dotfiles needs Python {}.{} or newer, but this is {}.\n"
        "  interpreter: {}\n"
        "Install a newer Python first, then re-run this script:\n"
        "  brew install python\n".format(
            MIN_PYTHON[0],
            MIN_PYTHON[1],
            platform.python_version(),
            sys.executable,
        )
    )
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (
    dry,
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


def check_macos():
    """Verify we're running on macOS"""
    if platform.system() != 'Darwin':
        warn("This installation is designed for macOS")
        warn(f"Detected: {platform.system()}")
        if is_dry_run():
            dry("non-macOS platform OK for dry-run")
            return
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            info("Installation cancelled")
            sys.exit(0)
    else:
        success("Running on macOS")


def check_homebrew():
    """Check if Homebrew is installed"""
    result = run_command(['which', 'brew'], check=False, capture_output=True)
    return result.returncode == 0


def install_homebrew():
    """Install Homebrew if not present"""
    info("Checking for Homebrew...")

    if is_dry_run():
        dry("assume Homebrew is installed; skipping bootstrap")
        return True

    if check_homebrew():
        success("Homebrew is already installed")
        # Get brew path
        result = run_command(['which', 'brew'], capture_output=True)
        brew_path = result.stdout.strip()
        info(f"Homebrew location: {brew_path}")
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


def get_topic_dependencies(topic_dir):
    """Read dependencies from a topic's dependencies.txt file"""
    deps_file = topic_dir / 'dependencies.txt'
    if not deps_file.exists():
        return []

    dependencies = []
    for line in deps_file.read_text().strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            dependencies.append(line)
    return dependencies


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
                topics[topic_name] = install_py
                dependencies[topic_name] = get_topic_dependencies(topic_dir)

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

    for topic in FINAL_TOPICS:
        script = dotfiles_root / topic / 'install.py'
        if not script.exists():
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

    # Step 1: Check macOS
    check_macos()

    # Step 2: Install Homebrew
    if not install_homebrew():
        error("Homebrew installation failed. Cannot continue.")
        sys.exit(1)

    # Step 3: Install Python
    if not install_python():
        error("Python installation failed. Cannot continue.")
        sys.exit(1)

    # Step 4: Get Homebrew Python path
    python_path = get_homebrew_python()
    success(f"Using Python: {python_path}")

    # Step 5: Create ~/.dotfiles symlink
    info("=" * 50)
    if not create_dotfiles_symlink(dotfiles_root):
        error("Failed to create ~/.dotfiles symlink")
        sys.exit(1)

    # Step 6: Setup XDG directories
    setup_xdg()

    # Step 7: Add mise shims to PATH so topic installers can find mise-managed
    # tools (e.g. npm) even before the shell config topics have been sourced.
    xdg_data_home = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    mise_shims = str(xdg_data_home / 'mise' / 'shims')
    if mise_shims not in os.environ.get('PATH', '').split(':'):
        os.environ['PATH'] = f"{mise_shims}:{os.environ['PATH']}"
        info(f"Added mise shims to PATH: {mise_shims}")

    # Step 8: Run topic installers (each installs its own .symlink files)
    info("=" * 50)
    if not run_topic_installers(dotfiles_root, python_path):
        error("Some topic installations failed")
        sys.exit(1)

    # Step 9: Run final topics (e.g. dock) after everything else
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
        info("  1. Run 'source ~/.zshrc' to load the configuration")
        info("  2. Configure 1Password CLI for secret management")


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
