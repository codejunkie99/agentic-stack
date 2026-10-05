#!/bin/sh
# Install only Agentic Stack's named profile. No daemon or global policy changes.
set -eu
if [ "$(uname -s)" != Linux ]; then
  echo "Run this on the Linux Docker host (tested with Ubuntu 24.04)." >&2
  exit 1
fi
if [ "$(id -u)" != 0 ]; then
  echo "Run sudo sh install-sandbox.sh on the Docker host to load the named AppArmor profile." >&2
  exit 1
fi
command -v apparmor_parser >/dev/null || {
  echo "Install the host's AppArmor utilities before continuing." >&2; exit 1;
}
[ -d /sys/kernel/security/apparmor ] || {
  echo "AppArmor is not active on this host. No security settings were changed." >&2; exit 1;
}
profile_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_profile="$profile_dir/agentic-stack-bwrap.apparmor"
target_profile=/etc/apparmor.d/agentic-stack-bwrap
# Parse first; unsupported user-namespace policy syntax must not replace a profile.
apparmor_parser --skip-kernel-load "$source_profile"
if [ -L "$target_profile" ]; then
  echo "The profile target is a symbolic link; inspect it before continuing." >&2
  exit 1
fi
if [ -f "$target_profile" ] && ! cmp -s "$source_profile" "$target_profile"; then
  cp -p "$target_profile" "$target_profile.backup-$(date +%s)"
fi
install -m 0644 "$source_profile" "$target_profile"
apparmor_parser -r "$target_profile"
echo "Loaded agentic-stack-bwrap. Only containers selecting this profile use it."
