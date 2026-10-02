# fnox (1Password secret injection) shell integration.
# fnox reads fnox.toml files in your project to resolve op:// references
# into environment variables. See https://fnox.jdx.dev/
#
# Usage in projects:
#   fnox run -- <command>   # run command with resolved secrets
#   fnox export             # print export lines for sourcing
#
# For shell-wide secrets that apply regardless of cwd, see the 1password
# topic — that one resolves a machine-specific env file on shell startup.
#
# No automatic activation here: fnox is cwd-scoped by design.
