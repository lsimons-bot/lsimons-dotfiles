# Rust: XDG-compliant cargo home for user-installed crates.
# mise manages the toolchain; CARGO_HOME keeps `cargo install` outputs
# in a predictable, XDG-compliant location.
export CARGO_HOME="${CARGO_HOME:-$XDG_DATA_HOME/cargo}"
if [ -d "$CARGO_HOME/bin" ]; then
  export PATH="$CARGO_HOME/bin:$PATH"
fi
