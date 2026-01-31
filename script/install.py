#!/usr/bin/env python3
"""
Installation script for lsimons-dotfiles
This script is safe to run multiple times (idempotent)

Steps:
1. Install Homebrew (if not present)
2. Install Python via Homebrew (if not present)
3. Create ~/.dotfiles symlink
4. Setup XDG directories
5. Symlink dotfiles to appropriate locations
6. Run topic-specific installation scripts
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from datetime import datetime


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

    if check_homebrew_python():
        success("Python is already installed via Homebrew")
        # Get python3 path
        result = run_command(['which', 'python3'], capture_output=True)
        python_path = result.stdout.strip()
        info(f"Python location: {python_path}")

        # Get Python version
        result = run_command(['python3', '--version'], capture_output=True)
        python_version = result.stdout.strip()
        info(f"Python version: {python_version}")
        return True

    info("Installing Python via Homebrew...")

    try:
        run_command(['brew', 'install', 'python@3'])
        success("Python installed successfully")

        # Verify installation
        result = run_command(['python3', '--version'], capture_output=True)
        python_version = result.stdout.strip()
        success(f"Installed: {python_version}")

        return True
    except subprocess.CalledProcessError:
        error("Failed to install Python")
        return False


def get_homebrew_python():
    """Get the path to Homebrew Python"""
    result = run_command(['which', 'python3'], capture_output=True)
    return result.stdout.strip()


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
            response = input("Remove and recreate symlink? (y/N): ")
            if response.lower() != 'y':
                info("Skipping symlink creation")
                return True
            symlink_path.unlink()

    # Check if a regular directory exists at ~/.dotfiles
    elif symlink_path.exists():
        error(f"~/.dotfiles exists as a directory or file, not a symlink")
        error(f"Please move or remove {symlink_path} manually")
        return False

    # Create the symlink
    try:
        symlink_path.symlink_to(dotfiles_root)
        success(f"Created symlink: ~/.dotfiles -> {dotfiles_root}")
        return True
    except Exception as e:
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

    xdg_config_home.mkdir(parents=True, exist_ok=True)
    xdg_data_home.mkdir(parents=True, exist_ok=True)
    xdg_cache_home.mkdir(parents=True, exist_ok=True)
    xdg_state_home.mkdir(parents=True, exist_ok=True)

    success("XDG directories created")


def backup_file(file_path):
    """Backup a file before replacing it"""
    path = Path(file_path)
    if path.exists() or path.is_symlink():
        backup_dir = Path.home() / '.dotfiles-backup' / datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir.mkdir(parents=True, exist_ok=True)
        dest = backup_dir / path.name
        shutil.move(str(path), str(dest))
        info(f"Backed up {file_path} to {dest}")


def link_file(src, dst):
    """Link a file to its destination"""
    src_path = Path(src)
    dst_path = Path(dst)

    # Check if destination already exists and is correct
    if dst_path.is_symlink():
        current_src = dst_path.resolve()
        if current_src == src_path.resolve():
            success(f"Already linked: {dst}")
            return True
        else:
            warn(f"Symlink exists but points to different location: {dst} -> {current_src}")
            backup_file(dst)
    elif dst_path.exists():
        warn(f"File exists: {dst}")
        backup_file(dst)

    # Create parent directory if it doesn't exist
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Create symlink
    dst_path.symlink_to(src_path)
    success(f"Linked: {dst} -> {src}")
    return True


def load_symlink_mappings(topic_dir):
    """Load symlink destination mappings from topic's symlinks.txt"""
    mappings = {}
    symlinks_file = topic_dir / 'symlinks.txt'
    if not symlinks_file.exists():
        return mappings

    home = Path.home()
    xdg_config_home = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))

    for line in symlinks_file.read_text().strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ' -> ' not in line:
            continue

        src_name, dst_path = line.split(' -> ', 1)
        src_name = src_name.strip()
        dst_path = dst_path.strip()

        # Expand variables
        dst_path = dst_path.replace('$HOME', str(home))
        dst_path = dst_path.replace('$XDG_CONFIG_HOME', str(xdg_config_home))
        dst_path = dst_path.replace('~', str(home))

        mappings[src_name] = Path(dst_path)

    return mappings


def bootstrap_dotfiles(dotfiles_root):
    """Symlink dotfiles to appropriate locations"""
    info("Linking dotfiles...")

    home = Path.home()

    # Load all symlink mappings from topic directories
    all_mappings = {}
    for topic_dir in dotfiles_root.iterdir():
        if topic_dir.is_dir() and not topic_dir.name.startswith('.'):
            mappings = load_symlink_mappings(topic_dir)
            for src_name, dst in mappings.items():
                src_path = topic_dir / src_name
                if src_path.exists():
                    all_mappings[src_path] = dst

    for src in dotfiles_root.rglob('*.symlink'):
        if src.is_file():
            if src in all_mappings:
                dst = all_mappings[src]
            else:
                # Default: link to home directory with a dot prefix
                basename = src.stem
                dst = home / f'.{basename}'

            link_file(src, dst)

    success("Dotfiles linked")


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
    # Build in-degree map and adjacency list
    in_degree = {topic: 0 for topic in topics}
    dependents = {topic: [] for topic in topics}

    for topic, deps in dependencies.items():
        for dep in deps:
            if dep in topics:
                in_degree[topic] += 1
                dependents[dep].append(topic)
            else:
                warn(f"Topic '{topic}' depends on '{dep}' which has no installer")

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
        if topic_dir.is_dir() and not topic_dir.name.startswith('.') and topic_dir.name != 'script':
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

    # Run each installer in order
    for topic in sorted_topics:
        script = topics[topic]
        deps = dependencies[topic]
        if deps:
            info(f"Running installer for: {topic} (depends on: {', '.join(deps)})")
        else:
            info(f"Running installer for: {topic}")

        try:
            run_command([python_path, str(script)])
            success(f"Installed: {topic}")
        except subprocess.CalledProcessError:
            error(f"Failed to install: {topic}")
            return False

    return True


def main():
    """Main installation flow"""
    info("Starting lsimons-dotfiles installation")
    info("=" * 50)

    # Get dotfiles root directory
    script_dir = Path(__file__).parent
    dotfiles_root = script_dir.parent
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

    # Step 7: Bootstrap dotfiles (symlink .symlink files)
    info("=" * 50)
    bootstrap_dotfiles(dotfiles_root)

    # Step 8: Run topic installers
    info("=" * 50)
    if not run_topic_installers(dotfiles_root, python_path):
        error("Some topic installations failed")
        sys.exit(1)

    # Done
    success("=" * 50)
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
    except Exception as e:
        error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
