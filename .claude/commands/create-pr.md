---
allowed-tools: Bash(git:*), Bash(gh pr create:*), Bash(gh pr view:*), Bash(gh repo view:*), Write, Read, Glob, Grep, AskUserQuestion
argument-hint: '<optional: PR title>'
description: Create a feature branch (if on main), commit changes, and open a PR
---

## Context

- Current branch: !`git branch --show-current`
- Git status: !`git status --short`
- Recent commits: !`git log --oneline -3`

## Task

Create a Pull Request for the current changes.

### Arguments: $ARGUMENTS

- Optional: PR title (if not provided, generate from changes)

### Steps to Follow

1. **Check for changes** - If no staged or unstaged changes exist, inform user and stop.

2. **Handle branch based on current state**:

   **If on `main` branch:**
   - Analyze changed files and generate 2-3 branch name suggestions
   - Use appropriate prefixes: `docs/`, `feature/`, `fix/`, `refactor/`
   - Present options to user using AskUserQuestion tool, e.g.:
     - `docs/update-claude-md`
     - `docs/add-pr-command`
     - `feature/claude-commands`
   - Wait for user selection before creating branch:
     ```bash
     git checkout -b <selected-branch-name>
     ```

   **If already on a feature/docs/fix branch:**
   - Stay on current branch

3. **Stage all changes** if not already staged:

   ```bash
   git add -A
   ```

4. **Commit changes** with a descriptive message:
   - Analyze the diff to understand what changed
   - Write a concise commit message
   - Include the Claude Code co-author footer

5. **Push branch** to origin:

   ```bash
   git push -u origin <branch-name>
   ```

6. **Create Pull Request**:
   - Use the **Write tool** to write the PR body markdown to `.pr-body.md` in the repo root
   - Then create the PR using `--body-file` to avoid long inline strings that trigger permission prompts:
     ```bash
     gh pr create --title "<title>" --body-file .pr-body.md
     ```
   - **NEVER pass the body inline** via `--body` or heredocs — always use `--body-file`
   - Body should include:
     - Summary (1-3 bullet points)
     - Test plan
     - Claude Code footer
   - No need to clean up `.pr-body.md` — it will be overwritten next time

7. **Report the PR URL** to the user