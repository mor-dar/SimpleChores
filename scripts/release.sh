#!/bin/bash

# SimpleChores Release Script
# Usage: ./scripts/release.sh <version> <type> [message]
# Example: ./scripts/release.sh 1.0.1 fix "Resolve PENDING APPROVAL string bug"

set -e

VERSION=$1
TYPE=$2
MESSAGE=${3:-"Release $VERSION"}

if [ -z "$VERSION" ] || [ -z "$TYPE" ]; then
    echo "Usage: $0 <version> <type> [message]"
    echo "Types: feat, fix, docs, style, refactor, test, chore"
    echo "Example: $0 1.0.1 fix 'Bug fix description'"
    exit 1
fi

echo "🚀 Starting release workflow for v$VERSION"
echo "📝 Type: $TYPE"
echo "💬 Message: $MESSAGE"
echo ""

# Check if we're on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "❌ Error: Must be on main branch for release"
    echo "Current branch: $CURRENT_BRANCH"
    exit 1
fi

# Show git status
echo "📊 Current git status:"
git status --short

echo ""
read -p "Continue with release? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Release cancelled"
    exit 1
fi

# Update version in manifest.json
echo "📝 Updating manifest.json version to $VERSION"
sed -i.bak "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" custom_components/SimpleChores/manifest.json
rm custom_components/SimpleChores/manifest.json.bak

# Commit changes
echo "💾 Committing changes..."
git add .
git commit -m "$TYPE: $MESSAGE

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push to remote
echo "⬆️ Pushing to remote..."
git push

# Create and push tag
echo "🏷️ Creating release tag v$VERSION..."
git tag -a "v$VERSION" -m "Release v$VERSION

$MESSAGE

$(git log --oneline --since='1 month ago' --pretty=format:'- %s' | head -10)"

git push origin "v$VERSION"

# Create GitHub release
echo "🎉 Creating GitHub release..."
if command -v gh &> /dev/null; then
    gh release create "v$VERSION" \
        --title "SimpleChores v$VERSION" \
        --notes "## Changes

$MESSAGE

## Installation

Via HACS:
1. Add custom repository: \`https://github.com/mor-dar/SimpleChores\`
2. Download SimpleChores
3. Restart Home Assistant

## Full Changelog
$(git log --oneline --since='1 month ago' --pretty=format:'- %s' | head -10)

---

🤖 Generated with [Claude Code](https://claude.ai/code)"
else
    echo "⚠️ GitHub CLI not available. Please create release manually at:"
    echo "https://github.com/mor-dar/SimpleChores/releases/new?tag=v$VERSION"
fi

echo ""
echo "✅ Release v$VERSION completed successfully!"
echo "📦 Users can now update via HACS"