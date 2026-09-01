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
  --version) echo "OpenClaw 2026.8.1" ;;
  config)
    if [ "${2:-}" = "get" ] && [ "${3:-}" = "cron.enabled" ]; then
      echo "true"
    elif [ "${2:-}" = "get" ] && [ "${3:-}" = "agents.entries" ]; then
      echo '{"main":{"id":"main","default":true}}'
    elif [ "${2:-}" = "get" ] && [ "${3:-}" = "agents.entries.main.heartbeat.every" ]; then
      echo "30m"
    elif [ "${2:-}" = "get" ] && [ "${3:-}" = "agents.entries.main.heartbeat.prompt" ]; then
      echo "Run python3 skills/proactive/scripts/proactive.py heartbeat"
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
test ! -e "$TMP/workspace/HEARTBEAT.md"
grep -Fq 'config set agents.entries.main.heartbeat.every 30m' "$TMP/openclaw.log"
grep -Fq 'config set agents.entries.main.heartbeat.prompt' "$TMP/openclaw.log"
grep -Fq 'config get agents.entries --json' "$TMP/openclaw.log"
grep -Fq 'config get agents.entries.main.heartbeat.every' "$TMP/openclaw.log"
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
  --ws-agents "$TMP/workspace/AGENTS.md" --vault-dir "$TMP/vault" --no-reload
grep -Fq '# customer-owned' "$TMP/workspace/AGENTS.md"
find "$TMP/skills" -maxdepth 1 -type d -name '*.prepatch*' | grep -q .
grep -Fq "config set env.vars.AGENT_OS_VAULT_DIR $TMP/vault" "$TMP/openclaw.log"
test -d "$TMP/vault"

echo "Install smoke passed."
