#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin" "$TMP/skills" "$TMP/workspace"
cat > "$TMP/bin/openclaw" <<'MOCK'
#!/usr/bin/env bash
set -e
printf '%s\n' "$*" >> "${OPENCLAW_MOCK_LOG:?}"
case "${1:-}" in
  --version) echo "OpenClaw 2026.7.1" ;;
  config)
    if [ "${2:-}" = "get" ] && [ "${3:-}" = "cron.enabled" ]; then
      echo "true"
    elif [ "${2:-}" = "get" ] && [ "${3:-}" = "agents.defaults.heartbeat.agentId" ]; then
      echo "main"
    fi
    ;;
  skills)
    find "${OPENCLAW_MOCK_SKILLS:?}" -mindepth 1 -maxdepth 1 -type d ! -name _lib \
      -printf '✓ ready %f\n'
    ;;
esac
MOCK
chmod +x "$TMP/bin/openclaw"

export PATH="$TMP/bin:$PATH"
export OPENCLAW_MOCK_LOG="$TMP/openclaw.log"
export OPENCLAW_MOCK_SKILLS="$TMP/skills"

bash "$REPO/install.sh" \
  --skills-dir "$TMP/skills" \
  --ws-agents "$TMP/workspace/AGENTS.md"

test -d "$TMP/skills/_lib"
test -d "$TMP/skills/proactive"
test -d "$TMP/skills/agent-os-vault"
test -f "$TMP/workspace/AGENTS.md"
test -f "$TMP/workspace/HEARTBEAT.md"
grep -Fq 'config set agents.defaults.heartbeat.every 30m' "$TMP/openclaw.log"
grep -Fq 'config set agents.defaults.heartbeat.agentId main' "$TMP/openclaw.log"
test -d "$TMP/workspace/.agent-os/agents/main"
test -d "$TMP/workspace/.agent-os/projects"
test -d "$TMP/workspace/.agent-os/shared"
if grep -Eq '(automations|cron) (add|create)' "$TMP/openclaw.log"; then
  echo "install smoke failed: installer created a business automation" >&2
  exit 1
fi

# Upgrade is retryable and preserves customer runtime files.
printf '%s\n' '# customer-owned' > "$TMP/workspace/AGENTS.md"
bash "$REPO/install.sh" --skills-dir "$TMP/skills" \
  --ws-agents "$TMP/workspace/AGENTS.md" --no-reload
grep -Fq '# customer-owned' "$TMP/workspace/AGENTS.md"
find "$TMP/skills" -maxdepth 1 -type d -name '*.prepatch*' | grep -q .

echo "Install smoke passed."
