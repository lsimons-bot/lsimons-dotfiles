---
name: 1password
description: Manage credentials, secrets, vaults, tokens and secure storage using 1password using the op CLI. Use when (1) Retrieving or setting passwords, API keys, and secrets from vaults, (2) Injecting secrets into environment variables and config files, (3) Automating credential rotation and management, (4) Accessing SSH keys and certificates, (5) Doing CRUD operations on vaults and secure items.
---

# 1Password CLI Skill

Use 1Password for secure secret management.

## Authentication

1Password authentication settings come from your environment. Assume it is available, do not attempt signin or debugging signin. You MUST NOT try to sign in, sign out, connect, or use a different account. If you think you need a different account, instead ask the user for help and stop.

## Vaults

Which vaults you can reach depends on the environment. Discover them, don't assume:

```bash
op vault list
```

A common failure is not seeing the vault you expect. If that occurs, specify the
`OP_ACCOUNT` environment variable, for example:

```bash
OP_ACCOUNT=my.1password.eu op vault list
```

Other reasons a vault or item may be missing:

- Service account tokens only see vaults explicitly granted at token creation
  time, and never the built-in Private/Personal vault.
- Archived items are skipped by `op read`, `op run` and `op inject`.

Pass the vault name or ID to commands that need it. Do so whenever more than one
vault is reachable — some commands require it:

```bash
op item list --vault AI
```

## Items

Items are stored inside vaults and can be passwords, login credentials, API tokens, SSH keys, and more.

### Retrieving items

```bash
# List all items
op item list

# Get complete item details
op item get <item-name-or-id>
op item get "GitHub Token"
op item get "AWS Credentials"

# Get item in JSON format
op item get "GitHub Token" --format json
```

### Retrieving specific fields

```bash
# Get a specific field value
op item get <item-name> --fields <field-name>

# Examples
op item get "GitHub Token" --fields token
op item get "AWS Credentials" --fields "access key"

# Get multiple fields as JSON
op item get "AWS Credentials" --fields "access key,secret key" --format json

# Using field notation (for scripting)
op read "op://<vault>/<item>/<field>"
op read "op://AI/GitHub Token/token"
op read "op://AI/AWS Credentials/access key"

# Capture into a variable without a trailing newline
TOKEN="$(op read --no-newline 'op://AI/GitHub Token/token')"
```

Since CLI 2.30, concealed fields are masked in human-readable output and print
`[use 'op item get <id> --reveal' to reveal]` instead of the value — while still
exiting 0, so scripts fail silently. Prefer `op read` or `--format json`, which
are not masked. Use `--reveal` only when you deliberately want the plaintext in
human-readable output.

### Creating and updating items

```bash
# Create a new login item, letting 1Password generate the password
op item create --category Login \
  --title "New Service" \
  --vault "AI" \
  --url "https://example.com" \
  --generate-password='letters,digits,symbols,32' \
  username=user@example.com

# Create item with custom fields
op item create --category Password \
  --title "API Key" \
  --vault "Work" \
  api_key=sk-xxx \
  environment=production

# Create secure note
op item create --category "Secure Note" \
  --title "Deployment Notes" \
  --vault "Work" \
  notesPlain="Important deployment information"

# Update an existing item
op item edit <item-name> <field>=<value>
op item edit "GitHub Token" token=ghp_newtoken123

# Add tags to item
op item edit "AWS Credentials" --tags production,terraform

# Rotate a password, letting 1Password generate it
op item edit "Database Login" --generate-password='letters,digits,symbols,32'
```

Never paste a secret you were given as a literal command argument if you can
avoid it — arguments are visible in process listings and shell history. Prefer
`--generate-password`, `op run`, or `op inject`.

## Deleting items

Do not delete items from 1Password. If you think you must delete items, ask the user for help and stop.

## Secret references

Use secret references to inject 1Password secrets into applications without exposing them:

```
# Secret reference syntax; the section is optional
op://<vault>/<item>/[section]/<field>

# Examples
op://Private/GitHub Token/token
op://Work/AWS Credentials/access key
op://DevOps/Database/password

# Query parameters select an attribute rather than the value
op://Work/Okta/one-time password?attribute=otp
op://AI/Deploy Key/private key?ssh-format=openssh
```

```
# Using op run to inject secrets into commands
op run -- env
op run -- npm run build
op run -- terraform apply

# Using op inject with templates
echo 'DB_PASSWORD=op://Work/Database/password' | op inject
cat .env.template | op inject > .env
```

`op run` masks secrets it injected from the child process's output. Do not
disable that masking (`--no-masking` / `OP_RUN_NO_MASKING`) — it is what keeps
secrets out of this transcript.

## Getting help

For more information on these commands, run `op --help`. Pass `--help` to a subcommand for more instructions. For example:

```bash
op vault --help
op vault list --help
op item --help
op item list --help
op item get --help
op run --help
```
