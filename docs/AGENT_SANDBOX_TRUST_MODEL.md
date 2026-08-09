# Agent sandbox trust model

What the coding-agent sandboxes (Claude Code, Codex) are allowed to touch
on the host, and why. Both `claude/settings.json.base` and
`codex/config.toml.base` grant two broad permissions beyond a typical
sandbox default. This document records the reasoning so the trade-off
isn't re-litigated (or silently narrowed) by accident.

This is about the *sandbox's* reach into the host — not about the VM
setup in [`AGENT_SETUP.md`](./AGENT_SETUP.md), which is a separate,
stronger isolation boundary for a dedicated bot account.

## 1. Read access to the private SSH signing key

`claude/settings.json.base` (`sandbox.filesystem.allowRead`) lists:

- `~/.ssh/ai_ed25519` — the **private** half of the dedicated agent
  signing key
- `~/.ssh/ai_ed25519.pub` and `~/.config/git/allowed-signers`

**Why:** git commit signing (`git config commit.gpgsign` with
`gpg.format = ssh`) needs to read the private key at commit time. If the
sandboxed process can't read it, every sandboxed `git commit` either
fails or has to shell out unsandboxed just to sign, which defeats the
point of sandboxing commits in the first place.

**Accepted risk:** any sandboxed agent process — including a
compromised or misbehaving one — can read this key. It can sign
arbitrary commits as the agent identity, or exfiltrate the key itself
(e.g. over an allowed network domain, or by writing it somewhere it can
later retrieve it). The key is scoped to the dedicated `ai_ed25519`
signing identity, not a human's primary key, which bounds the blast
radius to "commits attributed to the bot" rather than to Leo.

**Why not a narrower alternative:** the safer shape is a small signing
helper/agent outside the sandbox that receives a digest and returns a
signature, so the sandbox never sees key material. This was not built
because it adds a process boundary and IPC just to protect a key whose
compromise only lets an attacker sign bot-attributed commits — mitigated
today by the dedicated identity, branch protection, and code review
before merge. Revisit if the bot identity ever gets broader push/merge
rights, or if the key is reused for anything beyond commit signing.

## 2. Unrestricted Unix-domain socket access

`claude/settings.json.base` sets `sandbox.network.allowAllUnixSockets:
true`; `codex/config.toml.base` sets
`features.network_proxy.dangerously_allow_all_unix_sockets = true` (the
name is Codex's own naming, not this repo's judgment on the setting).

**Why:** the tools agents need to run day-to-day talk to local services
exclusively over Unix-domain sockets — the SSH agent (`SSH_AUTH_SOCK`,
including 1Password's SSH agent socket), the 1Password CLI/desktop app
integration, Docker's daemon socket, and similar. There is no small,
stable list of "the sockets an agent needs" — it depends on which CLI
the agent invokes, and 1Password/Docker/etc. don't publish a fixed
socket path guaranteed across versions. Blocking all sockets by default
and allowlisting per-tool would break normal workflows (`git push` over
SSH, `op` calls, `docker build`) until each one is individually
diagnosed and added.

**Accepted risk:** a sandboxed agent can reach any local Unix socket,
not just the ones it legitimately needs. In practice that means it can
talk to the SSH agent (sign/use loaded keys), the 1Password CLI socket
(read secrets the desktop app has unlocked), the Docker daemon (run
containers, mount host paths), and any other local service that happens
to be listening. This is a wide grant of local blast radius if an agent
process is compromised or goes rogue.

**Why not a narrower alternative:** an explicit per-socket allowlist
(SSH agent + 1Password + Docker, deny the rest) is the obvious
least-privilege fix, but no current incident or threat model justifies
the added complexity and maintenance burden — new sockets show up
whenever a tool is upgraded or a new local service is installed,
turning the allowlist into an ongoing chore. Revisit if agent tooling
ever runs against untrusted/third-party input at scale, or if a
sandbox-escape-via-socket incident (here or elsewhere) makes the
generic grant look too risky to keep.
