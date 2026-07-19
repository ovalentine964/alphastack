#!/usr/bin/env bash
###############################################################################
# AlphaStack Release Script
#
# Usage:
#   ./scripts/release.sh           # interactive — prompts for version
#   ./scripts/release.sh 0.2.0     # explicit version
#   ./scripts/release.sh patch     # bump patch: 0.1.0 → 0.1.1
#   ./scripts/release.sh minor     # bump minor: 0.1.0 → 0.2.0
#   ./scripts/release.sh major     # bump major: 0.1.0 → 1.0.0
#
# What it does:
#   1. Validates working tree is clean
#   2. Bumps version in package.json (desktop & web) and pubspec.yaml (mobile)
#   3. Bumps tauri.conf.json package.version
#   4. Commits the version bump
#   5. Creates an annotated git tag  (v0.2.0)
#   6. Pushes commit + tag to origin  → triggers release-all.yml
###############################################################################
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ── colours ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}ℹ ${NC}$*"; }
ok()    { echo -e "${GREEN}✅ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $*${NC}"; }
die()   { echo -e "${RED}❌ $*${NC}" >&2; exit 1; }

# ── tools ──
require_cmd() { command -v "$1" &>/dev/null || die "Missing required command: $1"; }
require_cmd git
require_cmd jq

# ── detect current version (from desktop package.json) ──
CURRENT=$(jq -r '.version' apps/desktop/package.json 2>/dev/null || echo "0.0.0")
info "Current version: ${CURRENT}"

# ── resolve next version ──
bump_semver() {
  local cur="$1" part="$2"
  IFS='.' read -r major minor patch <<< "$cur"
  case "$part" in
    major) echo "$((major+1)).0.0" ;;
    minor) echo "${major}.$((minor+1)).0" ;;
    patch) echo "${major}.${minor}.$((patch+1))" ;;
    *)     die "Unknown bump type: $part" ;;
  esac
}

INPUT="${1:-}"
case "$INPUT" in
  major|minor|patch)
    NEXT=$(bump_semver "$CURRENT" "$INPUT")
    ;;
  "")
    echo ""
    echo -e "${CYAN}┌─────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│       AlphaStack Release Manager        │${NC}"
    echo -e "${CYAN}└─────────────────────────────────────────┘${NC}"
    echo ""
    echo "  Current version: ${GREEN}${CURRENT}${NC}"
    echo ""
    echo "  Bump options:"
    echo "    [1] Patch  → $(bump_semver "$CURRENT" patch)"
    echo "    [2] Minor  → $(bump_semver "$CURRENT" minor)"
    echo "    [3] Major  → $(bump_semver "$CURRENT" major)"
    echo "    [4] Custom"
    echo ""
    read -rp "  Select [1-4]: " choice
    case "$choice" in
      1) NEXT=$(bump_semver "$CURRENT" patch) ;;
      2) NEXT=$(bump_semver "$CURRENT" minor) ;;
      3) NEXT=$(bump_semver "$CURRENT" major) ;;
      4) read -rp "  Enter version (e.g. 0.3.0): " NEXT ;;
      *) die "Invalid choice" ;;
    esac
    ;;
  *)
    # Validate it looks like a semver
    if [[ "$INPUT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      NEXT="$INPUT"
    else
      die "Invalid version format: $INPUT (expected X.Y.Z or patch|minor|major)"
    fi
    ;;
esac

TAG="v${NEXT}"
info "Next version: ${NEXT}  (tag: ${TAG})"
echo ""

# ── pre-flight checks ──
if ! git diff --quiet HEAD 2>/dev/null; then
  die "Working tree is not clean. Commit or stash changes first."
fi

if git tag -l | grep -qx "$TAG"; then
  die "Tag $TAG already exists!"
fi

# ── bump versions ──
info "Bumping versions..."

# Desktop — package.json
jq --arg v "$NEXT" '.version = $v' apps/desktop/package.json > /tmp/_pkg.json \
  && mv /tmp/_pkg.json apps/desktop/package.json
ok "apps/desktop/package.json → $NEXT"

# Desktop — tauri.conf.json
jq --arg v "$NEXT" '.package.version = $v' apps/desktop/src-tauri/tauri.conf.json > /tmp/_tauri.json \
  && mv /tmp/_tauri.json apps/desktop/src-tauri/tauri.conf.json
ok "apps/desktop/src-tauri/tauri.conf.json → $NEXT"

# Web — package.json
jq --arg v "$NEXT" '.version = $v' apps/web/package.json > /tmp/_web.json \
  && mv /tmp/_web.json apps/web/package.json
ok "apps/web/package.json → $NEXT"

# Mobile — pubspec.yaml  (version: X.Y.Z+1)
BUILD_NUM=$(grep -oP '(?<=\+)\d+' apps/mobile/pubspec.yaml || echo "1")
if [[ "$INPUT" == "patch" || "$INPUT" == "minor" || "$INPUT" == "major" || "$INPUT" == "" ]]; then
  BUILD_NUM=$((BUILD_NUM + 1))
fi
sed -i "s/^version: .*/version: ${NEXT}+${BUILD_NUM}/" apps/mobile/pubspec.yaml
ok "apps/mobile/pubspec.yaml → ${NEXT}+${BUILD_NUM}"

echo ""

# ── commit & tag ──
info "Committing version bump..."
git add \
  apps/desktop/package.json \
  apps/desktop/src-tauri/tauri.conf.json \
  apps/web/package.json \
  apps/mobile/pubspec.yaml

git commit -m "release: ${TAG}

Bumped versions:
- desktop/package.json → ${NEXT}
- desktop/src-tauri/tauri.conf.json → ${NEXT}
- web/package.json → ${NEXT}
- mobile/pubspec.yaml → ${NEXT}+${BUILD_NUM}"

ok "Committed"

info "Creating tag ${TAG}..."
git tag -a "$TAG" -m "Release ${TAG}"
ok "Tag ${TAG} created"

# ── push ──
echo ""
info "Pushing to origin..."
git push origin HEAD
git push origin "$TAG"
ok "Pushed commit and tag ${TAG} to origin"

echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│  🚀  Release ${TAG} triggered!                  │${NC}"
echo -e "${GREEN}│                                                 │${NC}"
echo -e "${GREEN}│  CI will build:                                 │${NC}"
echo -e "${GREEN}│    • Android APK                                │${NC}"
echo -e "${GREEN}│    • Desktop (Windows, macOS, Linux)            │${NC}"
echo -e "${GREEN}│    • Web bundle                                 │${NC}"
echo -e "${GREEN}│                                                 │${NC}"
echo -e "${GREEN}│  Watch progress:                                │${NC}"
echo -e "${GREEN}│  https://github.com/<owner>/alphastack/actions  │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────┘${NC}"
