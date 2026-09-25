#!/usr/bin/env python3
"""Installation script for a container runtime.

macOS gets Rancher Desktop, which bundles the VM, the docker CLI and a
Kubernetes distribution in one app. Linux runs containers natively, so
there is no VM to install: it gets the docker engine plus the compose and
buildx plugins, the socket enabled, and the invoking user added to the
`docker` group.

On macOS a machine can also set Rancher Desktop's VM memory and turn
Kubernetes off through `docker` in machines/<hostname>.json. Those go
through `rdctl set`, which only reaches a running Rancher Desktop, so on
a fresh machine: start the app once, then re-run the installer.
"""

import getpass
import grp
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    HOME,
    IS_LINUX,
    dry,
    ensure_package,
    error,
    get_machine_config,
    info,
    is_dry_run,
    parse_dry_run,
    run_cmd,
    success,
    warn,
)

# (label, pacman package, apt package). Ubuntu packages the engine as
# docker.io and the compose plugin under its v2 name.
LINUX_PACKAGES = [
    ("docker", "docker", "docker.io"),
    ("docker-compose", "docker-compose", "docker-compose-v2"),
    ("docker-buildx", "docker-buildx", "docker-buildx"),
]


# Rancher Desktop links its CLIs here; docker/path.sh puts it on PATH for
# shells, but this installer may run before that has been sourced.
RDCTL = HOME / ".rd" / "bin" / "rdctl"


def rancher_wanted_settings(docker_config):
    """Map the machine's `docker` config to (settings path, rdctl flag, value).

    The container engine is not a machine choice: this topic exists to
    provide the docker CLI, which only works with the moby engine, so it is
    pinned whenever a machine configures Rancher at all.
    """
    wanted = [(("containerEngine", "name"), "container-engine.name", "moby")]
    if "vmMemoryGB" in docker_config:
        wanted.append(
            (("virtualMachine", "memoryInGB"), "virtual-machine.memory-in-gb",
             docker_config["vmMemoryGB"])
        )
    if "kubernetes" in docker_config:
        wanted.append(
            (("kubernetes", "enabled"), "kubernetes.enabled", docker_config["kubernetes"])
        )
    return wanted


def rdctl_flag(flag, value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    return f"--{flag}={value}"


def configure_rancher():
    """Apply the machine's Rancher Desktop settings through rdctl."""
    config, hostname = get_machine_config()
    docker_config = config.get("docker")
    if not docker_config:
        return True

    wanted = rancher_wanted_settings(docker_config)
    set_all = [str(RDCTL), "set", *(rdctl_flag(flag, value) for _, flag, value in wanted)]

    if is_dry_run():
        dry(f"would run (for settings that differ): {' '.join(set_all)}")
        return True
    if not RDCTL.exists():
        warn(f"{RDCTL} not found; start Rancher Desktop once, then re-run the installer")
        return True

    current = run_cmd([str(RDCTL), "list-settings"], check=False, capture_output=True)
    if current.returncode != 0:
        warn(
            "Rancher Desktop is not running; start it, then re-run the installer "
            f"or run: {' '.join(set_all)}"
        )
        return True
    settings = json.loads(current.stdout)

    flags = []
    for (section, key), flag, value in wanted:
        if settings.get(section, {}).get(key) != value:
            flags.append(rdctl_flag(flag, value))
    if not flags:
        success(f"Rancher Desktop settings already match {hostname}")
        return True

    info(f"Updating Rancher Desktop settings: {' '.join(flags)}")
    result = run_cmd([str(RDCTL), "set", *flags], check=False, capture_output=True)
    if result.returncode != 0:
        error(f"rdctl set failed: {(result.stderr or '').strip()}")
        return False
    success("Rancher Desktop settings updated (it restarts its VM to apply them)")
    return True


def install_linux_docker():
    for label, pacman, apt in LINUX_PACKAGES:
        if not ensure_package(label, pacman=pacman, apt=apt):
            return False
    return enable_docker_service() and join_docker_group()


def enable_docker_service():
    """Enable and start docker.socket so the daemon starts on demand."""
    if is_dry_run():
        dry("would run: sudo systemctl enable --now docker.socket")
        return True

    result = run_cmd(
        ['sudo', 'systemctl', 'enable', '--now', 'docker.socket'],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        error(f"Failed to enable docker.socket: {(result.stderr or '').strip()}")
        return False
    success("docker.socket enabled")
    return True


def join_docker_group():
    """Add the current user to the `docker` group.

    Membership of this group is root-equivalent — it grants the ability to
    start a container that bind-mounts the host filesystem. That is the
    standard single-user desktop trade-off (and what Omarchy's own
    installer does), taken deliberately here so `docker` works without
    sudo. Drop this call and use rootless docker instead if that trade is
    not wanted on a given machine.
    """
    user = getpass.getuser()

    if is_dry_run():
        dry(f"would add {user} to the docker group")
        return True

    try:
        if user in grp.getgrnam('docker').gr_mem:
            success(f"{user} is already in the docker group")
            return True
    except KeyError:
        warn("No docker group exists; skipping group membership")
        return True

    result = run_cmd(
        ['sudo', 'usermod', '-aG', 'docker', user], check=False, capture_output=True
    )
    if result.returncode != 0:
        error(f"Failed to add {user} to the docker group: {(result.stderr or '').strip()}")
        return False
    success(f"Added {user} to the docker group (log out and back in to pick it up)")
    return True


def main():
    parse_dry_run()

    if IS_LINUX:
        info("Installing the docker engine...")
        return 0 if install_linux_docker() else 1

    info("Checking Rancher Desktop installation...")
    if not ensure_package(
        'Rancher Desktop', brew='rancher', cask=True, macos_app='Rancher Desktop'
    ):
        return 1
    return 0 if configure_rancher() else 1


if __name__ == '__main__':
    sys.exit(main())
