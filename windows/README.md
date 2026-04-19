# windows/

Windows 11 ARM64 bootstrap for the AI-agent sandbox VM.

For the rationale (why native-only, why these tools, constraints), see
[../docs/AGENT_WINDOWS_SETUP.md](../docs/AGENT_WINDOWS_SETUP.md).

## Files

| File | Purpose |
|---|---|
| `bootstrap-phase1.ps1` | Unattended setup: winget + Scoop + registry + profiles + Claude Code |
| `bootstrap-phase2.ps1` | Credential-coupled setup: SSH key + git signing + optional repo clones |
| `bootstrap-phase3.ps1` | mise-managed runtimes and CLI tools (node, python, go, rust, …) |
| `packages.winget.yaml` | Declarative winget manifest (GUI / MSI apps) |
| `scoopfile.json` | Declarative Scoop manifest (CLI toolchain) |
| `Microsoft.PowerShell_profile.ps1` | PowerShell profile (copied into `$PROFILE` paths) |
| `WindowsTerminal-settings.json` | Windows Terminal settings (copied into LocalState) |

## Prereqs

- Fresh Windows 11 ARM64 in UTM, local account, updates applied
- `winget --version` works
- You have a browser (Vivaldi) to complete OAuth flows

## Run

### Phase 0 — unblock the scripts (once)

Fresh Windows 11 blocks unsigned scripts by default, and any file extracted
from a downloaded ZIP carries a Mark-of-the-Web that makes `RemoteSigned`
refuse it too. Fix both in one shot from the `windows\` directory:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
Get-ChildItem -Recurse | Unblock-File
```

Or bypass per-invocation (no permanent policy change):

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap-phase1.ps1
```

If you `git clone` the repo instead of downloading a ZIP, the Mark-of-the-Web
doesn't apply and `Set-ExecutionPolicy RemoteSigned` alone is enough.

### Phase 1 — unattended

From a **non-admin** PowerShell (5.1 is fine; pwsh 7 installs during this phase):

```powershell
cd ~\git\lsimons-dotfiles\windows
.\bootstrap-phase1.ps1
```

Preview first with `-DryRun`. Useful flags when iterating:

```powershell
.\bootstrap-phase1.ps1 -DryRun
.\bootstrap-phase1.ps1 -SkipWinget
.\bootstrap-phase1.ps1 -SkipScoop
.\bootstrap-phase1.ps1 -SkipClaude
```

winget will prompt for UAC once when it needs to install a machine-wide
package (Git for Windows, Simplewall, PowerShell 7). That's expected.

### Manual steps (between phases)

These cannot be scripted:

1. Launch **Windows Terminal** once so its LocalState directory is created,
   then re-run `bootstrap-phase1.ps1` to drop the settings file in place.
2. Sign in to **1Password** (Secret Key + passkey). Enable the SSH agent:
   *Settings → Developer → Use the SSH agent*.
3. Sign in to **Vivaldi** with the bot account.
4. `gh auth login` — OAuth flow in the browser.
5. `claude` → `/login` — OAuth flow in the browser.
6. Run **Pareto Security**, remediate until green.
7. Configure **Simplewall** rules, then switch to alert mode.

### Phase 2 — credentials

From **pwsh 7** (`pwsh`), with 1Password signed in and CLI integration on:

```powershell
cd ~\git\lsimons-dotfiles\windows
.\bootstrap-phase2.ps1
```

Optional flags:

```powershell
.\bootstrap-phase2.ps1 -DryRun
.\bootstrap-phase2.ps1 -Repos @('lsimons/lsimons-dotfiles','lsimons/lsimons-arch')
.\bootstrap-phase2.ps1 -SshKeyItem 'op://Private/my ssh key/public key'
```

### Phase 3 — mise runtimes

```powershell
cd ~\git\lsimons-dotfiles\windows
.\bootstrap-phase3.ps1
```

Tools that are not yet available for Windows/ARM64 via mise will warn and be skipped.

### Keep tools up to date

`topgrade` (installed via Scoop) updates everything in one shot — Scoop packages,
winget packages, and mise-managed runtimes:

```powershell
topgrade
```

### Verify

```powershell
# Tools on PATH
git --version ; gh --version ; op --version ; claude --version ; scoop --version

# PowerShell profile loaded
$PROFILE.CurrentUserAllHosts

# Commit signing works
cd ~\git\lsimons-dotfiles
git commit --allow-empty -m 'test: signing'
git log --show-signature -1
```

## Idempotency

Re-running either phase is safe. Each step checks before acting. File writes
are hash-compared so unchanged files don't get rewritten.

## Caveats

- **No WSL2, no Docker, no Podman.** Apple Silicon M2 doesn't expose nested
  virtualization, and even M3+ only exposes it for Linux guests. This VM
  cannot run WSL2 regardless of effort spent trying. Run a separate Linux
  UTM VM if you need containers.
- **winget package IDs** may drift over time. If `winget configure` fails
  with "no package found", update the `id:` in `packages.winget.yaml`.
- **Scoop refuses to run as admin.** Phase 1 enforces this — it throws if
  started elevated.
- Windows Terminal settings file is **copied, not symlinked**. Windows
  symlinks need Developer Mode (admin to enable) so a copy is the simpler
  trade-off. Re-run phase 1 to resync after editing.
