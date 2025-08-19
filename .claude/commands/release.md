# Release Workflow

Execute a complete release workflow: commit, push, tag, and create GitHub release.

## Parameters:
- `version`: Version number (e.g., 1.0.1, 1.1.0, 2.0.0)
- `type`: Release type (patch|minor|major)  
- `message`: Commit message summary

## Workflow:

1. **Check git status** and show pending changes
2. **Commit changes** with conventional commit format:
   ```
   {type}: {message}
   
   {detailed description}
   
   🤖 Generated with [Claude Code](https://claude.ai/code)
   
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```

3. **Push to remote**

4. **Create annotated tag** with release notes

5. **Push tag to remote**

6. **Create GitHub release** using `gh` CLI

## Example Usage:

User says: "Release version 1.0.1 with bug fixes"
Claude executes complete workflow with proper versioning.