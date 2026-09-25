#!/usr/bin/env bash
# Apply repository hardening for ha-atmos (rulesets + settings).
# Requires: gh auth with repo admin scopes.
set -euo pipefail

OWNER="${OWNER:-marpi82}"
REPO="${REPO:-ha-atmos}"
API="repos/${OWNER}/${REPO}"

# Repository Admin role (actor_id 5) may always bypass rulesets (solo-maintainer).

need_auth() {
  if ! gh api user --jq .login >/dev/null 2>&1; then
    echo "gh is not authenticated. Run: gh auth login -h github.com" >&2
    exit 1
  fi
}

patch_repo() {
  echo "Updating repository settings..."
  gh api -X PATCH "${API}" --input - <<'EOF'
{
  "has_wiki": false,
  "has_projects": true,
  "has_issues": true,
  "allow_squash_merge": true,
  "allow_merge_commit": true,
  "allow_rebase_merge": true,
  "allow_auto_merge": true,
  "delete_branch_on_merge": true,
  "allow_update_branch": true,
  "squash_merge_commit_title": "PR_TITLE",
  "squash_merge_commit_message": "COMMIT_MESSAGES"
}
EOF
}

enable_security() {
  echo "Enabling vulnerability alerts and automated security fixes..."
  gh api -X PUT "${API}/vulnerability-alerts" --silent
  gh api -X PUT "${API}/automated-security-fixes" --silent
  echo "Enabling secret scanning and push protection..."
  gh api -X PATCH "${API}" --input - <<'EOF'
{
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" },
    "dependabot_security_updates": { "status": "enabled" }
  }
}
EOF
}

enable_pages() {
  echo "Ensuring GitHub Pages is enabled (Actions source)..."
  local payload='{"build_type":"workflow","source":{"branch":"main","path":"/"}}'
  if gh api "${API}/pages" >/dev/null 2>&1; then
    gh api -X PUT "${API}/pages" --input - <<<"${payload}"
  else
    gh api -X POST "${API}/pages" --input - <<<"${payload}"
  fi
}

merge_admin_bypass() {
  # stdin: ruleset JSON body; $1: existing bypass_actors JSON array
  python3 -c '
import json, sys

admin = {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
body = json.loads(sys.stdin.read())
existing = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []

merged = []
seen = set()
for actor in list(existing) + list(body.get("bypass_actors") or []) + [admin]:
    key = (actor.get("actor_id"), actor.get("actor_type"), actor.get("bypass_mode"))
    if key in seen:
        continue
    seen.add(key)
    merged.append(actor)
body["bypass_actors"] = merged
print(json.dumps(body))
' "${1:-[]}"
}

create_or_replace_ruleset() {
  local name="$1"
  local body="$2"
  local existing_id existing_bypass
  existing_id="$(gh api "${API}/rulesets" --jq ".[] | select(.name==\"${name}\") | .id" | head -n1 || true)"
  existing_bypass='[]'
  if [[ -n "${existing_id}" ]]; then
    existing_bypass="$(gh api "${API}/rulesets/${existing_id}" --jq '.bypass_actors // []')"
  fi
  body="$(printf '%s' "${body}" | merge_admin_bypass "${existing_bypass}")"
  if [[ -n "${existing_id}" ]]; then
    echo "Updating ruleset ${name} (${existing_id})..."
    gh api -X PUT "${API}/rulesets/${existing_id}" --input - <<<"${body}"
  else
    echo "Creating ruleset ${name}..."
    gh api -X POST "${API}/rulesets" --input - <<<"${body}"
  fi
}

ruleset_main() {
  cat <<'EOF'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {"context": "secrets (gitleaks)"},
          {"context": "security (pip-audit)"},
          {"context": "quality (lint + typecheck)"},
          {"context": "tests (3.13)"},
          {"context": "hassfest"},
          {"context": "build"}
        ]
      }
    },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
EOF
}

ruleset_release() {
  cat <<'EOF'
{
  "name": "protect-release/**",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/release/**"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
EOF
}

ruleset_tags() {
  # GitHub ruleset ref patterns are fnmatch (not regex). Cover CalVer tags
  # starting with 20xx, with or without a leading ``v`` (workflows accept both).
  cat <<'EOF'
{
  "name": "protect-tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": [
        "refs/tags/20*",
        "refs/tags/v20*"
      ],
      "exclude": []
    }
  },
  "rules": [
    { "type": "creation" },
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ]
}
EOF
}

main() {
  need_auth
  patch_repo
  enable_security
  create_or_replace_ruleset "protect-main" "$(ruleset_main)"
  create_or_replace_ruleset "protect-release/**" "$(ruleset_release)"
  create_or_replace_ruleset "protect-tags" "$(ruleset_tags)"
  echo
  echo "Done. Current rulesets:"
  gh api "${API}/rulesets" --jq '.[] | {id,name,target,enforcement}'
}

main "$@"
