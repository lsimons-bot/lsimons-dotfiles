#!/usr/bin/env python3
"""Installation script for the OpenSSH server.

Opt-in per machine through `remoteAccess.sshd` in
`machines/<hostname>.json`; every other machine skips this topic. On an
enabled machine it:

* writes `~/.ssh/authorized_keys` from the machine's `ssh.keys` entries
  with `auth: true` — the same 1Password-held keys the other enrolled
  machines authenticate with, so no key material is copied around;
* installs and enables the OpenSSH server;
* drops a hardening snippet into `/etc/ssh/sshd_config.d/` that turns
  off password and root logins — but only once `authorized_keys` has at
  least one key, because doing it earlier would lock the machine out;
* opens port 22 in ufw, restricted to `remoteAccess.allowFrom` when set.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'script'))
from helpers import (
    IS_ARCH,
    IS_DEBIAN,
    SSH_CONFIG_DIR,
    chmod,
    dry,
    ensure_package,
    error,
    get_machine_ssh_config,
    get_remote_access_config,
    info,
    is_dry_run,
    make_dir,
    parse_dry_run,
    run_cmd,
    success,
    sudo_write_file,
    systemctl_enable,
    ufw_allow,
    warn,
)

AUTHORIZED_KEYS = SSH_CONFIG_DIR / "authorized_keys"
HARDENING_PATH = Path("/etc/ssh/sshd_config.d/10-lsimons-dotfiles.conf")
HARDENING = """\
# Managed by lsimons-dotfiles (sshd/install.py). Keys only: the machine's
# authorized_keys is generated from machines/<hostname>.json.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
"""

# Arch calls the unit sshd, Debian and Ubuntu call it ssh.
UNIT = "sshd" if IS_ARCH else "ssh"


def authorized_public_keys():
    """Public keys from the machine config that may log in here."""
    ssh_config = get_machine_ssh_config() or {}
    return [
        key["public_key"].strip()
        for key in ssh_config.get("keys", [])
        if key.get("auth") and key.get("public_key")
    ]


def install_authorized_keys(public_keys):
    """Add the machine's auth keys to authorized_keys, keeping any others.

    Keys added by hand (another device, a one-off ssh-copy-id) stay; only
    missing entries are appended. Returns the number of keys present.
    """
    existing = AUTHORIZED_KEYS.read_text() if AUTHORIZED_KEYS.exists() else ""
    present = [
        line.strip()
        for line in existing.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    missing = [key for key in public_keys if key not in present]
    if not missing:
        success(f"{AUTHORIZED_KEYS} already has every machine-config key")
        return len(present)

    if is_dry_run():
        dry(f"would add {len(missing)} key(s) to {AUTHORIZED_KEYS}")
        return len(present) + len(missing)

    make_dir(SSH_CONFIG_DIR, mode=0o700)
    with AUTHORIZED_KEYS.open("a") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        for key in missing:
            handle.write(key + "\n")
    chmod(AUTHORIZED_KEYS, 0o600)
    success(f"Added {len(missing)} key(s) to {AUTHORIZED_KEYS}")
    return len(present) + len(missing)


def install_server():
    return ensure_package("OpenSSH server", pacman="openssh", apt="openssh-server", command="sshd")


def harden(key_count):
    """Disable password logins, once there is a key to log in with."""
    if key_count == 0:
        warn("No authorized_keys yet; leaving password authentication enabled")
        warn("Mark a key `auth: true` in the machine config, or add one by hand, and re-run")
        return True
    changed = sudo_write_file(HARDENING_PATH, HARDENING)
    if changed and not is_dry_run():
        result = run_cmd(["sudo", "systemctl", "reload", UNIT], check=False, capture_output=True)
        if result.returncode != 0:
            error(f"Failed to reload {UNIT}: {(result.stderr or '').strip()}")
            return False
        success(f"{UNIT} reloaded")
    return True


def main():
    parse_dry_run()

    remote = get_remote_access_config()
    if not remote.get("sshd"):
        info("remoteAccess.sshd is not enabled for this machine; skipping the SSH server")
        return 0

    if not (IS_ARCH or IS_DEBIAN):
        error("The SSH server is only set up for Arch and Debian/Ubuntu here")
        return 1

    info("Installing the OpenSSH server...")
    key_count = install_authorized_keys(authorized_public_keys())

    if not install_server():
        return 1
    if not systemctl_enable(UNIT):
        return 1
    if not harden(key_count):
        return 1
    if not ufw_allow(22, "tcp", "ssh", from_cidr=remote.get("allowFrom")):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
