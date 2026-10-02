# Personal claude-docker image: the upstream claude-code:local plus mise, a C
# toolchain and the libraries Playwright's Chromium needs. Projects that pin
# their tools in mise.toml get those versions inside the container instead of
# the image's own node/go/uv.
#
# Built by claude-docker/install.py after the base image. Rebuild it whenever
# the base is rebuilt, since run.sh and the image it runs are versioned together:
#   docker build -t claude-code-lsimons:local ~/git/lsimons/lsimons-dotfiles/claude-docker/image
#
# Nothing is installed under /root here: at runtime /root is the
# claude-code-root volume, which hides whatever the image has at that path.
# mise's binary lives in /usr/local/bin; the tools it installs land in
# /root/.local/share/mise on the volume, owned by the session user.
FROM claude-code:local

# build-essential: mise's source-built runtimes (ruby, erlang) and native
# npm/pip packages need a compiler. Claude runs unprivileged, so it cannot
# apt-get install one itself.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

# Shared libraries for Playwright's own Chromium build, which a project
# downloads with `playwright install chromium` into ~/.cache/ms-playwright on
# the claude-code-root volume. Ubuntu's `chromium` apt package is only a
# wrapper around the snap, and snaps cannot run in a container. These names
# are the ones `ldd headless_shell` reports missing, so Claude, as a
# non-root user, never needs `playwright install-deps`. fonts-liberation:
# the image has no fonts at all, and text in screenshots would render as
# empty boxes without one.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libglib2.0-0t64 libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
      libdbus-1-3 libcups2t64 libxcb1 libxkbcommon0 libasound2t64 libgbm1 \
      libx11-6 libxext6 libcairo2 libpango-1.0-0 libxcomposite1 libxdamage1 \
      libxfixes3 libxrandr2 libatspi2.0-0t64 fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

# mise: version + per-arch sha256 from the release's SHASUMS256.txt.
ARG MISE_VERSION=2026.9.14
ARG MISE_SHA256_ARM64=b405a2ea062c4d9560eee0a3c45b79e53c8834cf38e956bb47ca70e0d2e7479a
ARG MISE_SHA256_X64=2b289d1b3074e0b1d3f95bad0bd78bbc517c1a5bcb020cbc1643d260f5d1a351
RUN case "$(dpkg --print-architecture)" in \
      arm64) arch=arm64; sha="$MISE_SHA256_ARM64" ;; \
      amd64) arch=x64;   sha="$MISE_SHA256_X64" ;; \
      *) echo "unsupported architecture: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac \
 && curl -fsSLo /usr/local/bin/mise \
      "https://github.com/jdx/mise/releases/download/v${MISE_VERSION}/mise-v${MISE_VERSION}-linux-${arch}" \
 && echo "${sha}  /usr/local/bin/mise" | sha256sum -c - \
 && chmod 0755 /usr/local/bin/mise \
 && mise --version

COPY claude_env.sh session_start.sh /usr/local/share/claude-docker-lsimons/

# MISE_TRUSTED_CONFIG_PATHS: workspaces mount at /workspaces/<name>, and the
#   host's trust records don't carry over; Claude can't answer the prompt.
# MISE_YES: no other interactive confirmations either.
# MISE_MINIMUM_RELEASE_AGE: same 7-day soak as the host's mise config.
# PATH: shims first, so a project's pinned node/go/python wins over the
#   image's. Claude's Bash tool is a non-interactive shell, where
#   `mise activate` never runs; shims work regardless.
# CLAUDE_ENV_FILE: loads mise.toml [env] into that same shell (see
#   claude_env.sh).
ENV CLAUDE_ENV_FILE=/usr/local/share/claude-docker-lsimons/claude_env.sh \
    MISE_TRUSTED_CONFIG_PATHS=/workspaces \
    MISE_YES=1 \
    MISE_MINIMUM_RELEASE_AGE=7d \
    PATH="/root/.local/share/mise/shims:${PATH}"
