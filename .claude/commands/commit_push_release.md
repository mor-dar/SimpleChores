# Commit, Push, and Release Workflow

Execute the complete workflow for committing changes, creating PRs, and releasing with proper branch protection.

## Protected Branch Workflow:

### Step 1: Create Feature Branch
- Check current branch and create feature branch from main
- Use descriptive branch name (e.g., `fix/approval-string`, `feat/hacs-ready`)

### Step 2: Commit Changes
- Commit all staged/unstaged changes with conventional commit format:
  ```
  {type}: {description}
  
  {detailed explanation}
  {breaking changes if any}
  
  🤖 Generated with [Claude Code](https://claude.ai/code)
  
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```
- Types: feat, fix, docs, style, refactor, test, chore, build, ci

### Step 3: Push Feature Branch
- Push feature branch to remote origin

### Step 4: Create Pull Request
- Use `gh pr create` with proper title and description
- Include changelog, testing notes, and any special instructions

### Step 5: Merge PR (if ready for release)
- Review and merge PR through GitHub interface
- This updates main branch with changes

### Step 6: Create Release (optional)
- If changes warrant a release, update manifest.json version
- Create annotated git tag with release notes
- Push tag and create GitHub release via `gh release create`
- Use semantic versioning (patch/minor/major)

## Usage:

When ready to commit current work, type `/commit_push_release` and Claude will:
1. Analyze current changes
2. Determine appropriate commit type and branch name  
3. Execute the full workflow including PR creation
4. Ask if you want to create a release (and what version)
