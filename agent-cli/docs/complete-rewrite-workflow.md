# Complete Git History Rewrite Workflow

## Overview
This document provides a step-by-step walkthrough of using the git-history-rewriter tool to clean up git history using the two-phase plan-based approach.

## Scenario: Cleaning Up a Feature Branch

You've been working on a feature branch with messy commit history:
- Multiple "WIP" commits
- Fixes for typos
- Debug commits that should be removed
- Poor commit messages

Goal: Clean up the history before merging to main.

## Step-by-Step Workflow

### Step 1: Examine Current History

First, check what commits need to be rewritten:

```bash
# Navigate to your repository
cd /home/paul/my-project

# View the commit history
git log --oneline -15

# Output:
# f5d3a2b (HEAD -> feature-user-auth) fix typo
# e8c9d11 remove debug logs
# d7b6a34 WIP: more auth work
# c6a5b23 add debug logging
# b5a4c12 WIP: auth stuff
# a4b3c11 fix broken test
# 93a2b01 WIP: starting auth
# 82a1b90 add user model
# 71a0b89 (main) Previous feature merged
```

### Step 2: Generate a Rewrite Plan

Create a plan to clean up these commits:

```bash
git-history-rewriter rewrite \
  --repo /home/paul/my-project \
  --prompt "Clean up the feature branch: 
    1. Squash all WIP commits into meaningful commits
    2. Remove debug-related commits
    3. Improve commit messages to follow conventional commits format
    4. Group related changes together" \
  --initial-commit main \
  --final-commit HEAD \
  --dry-run \
  --save-plan /tmp/auth-cleanup-plan.json \
  --verbose
```

**Expected Output:**
```
Analyzing repository history...
Found 8 commits to process

Generating rewrite plan with Claude...
✓ Plan generated and saved to: /tmp/auth-cleanup-plan.json

Git History Rewrite Plan
========================
Created: 2025-01-07T14:30:00
Repository: /home/paul/my-project
Commits: 71a0b89..f5d3a2b
Original commits: 8
Planned commits: 3

Operations:
-----------
  squash: 3
  reword: 2
  drop: 2

Next steps:
  1. Review the plan: cat /tmp/auth-cleanup-plan.json
  2. Apply the plan: git-history-rewriter apply-plan --plan /tmp/auth-cleanup-plan.json --repo /home/paul/my-project
```

### Step 3: Review the Generated Plan

Examine what changes will be made:

```bash
# View the plan summary
cat /tmp/auth-cleanup-plan.json | jq '.metadata'
```

**Output:**
```json
{
  "version": "1.0",
  "created_at": "2025-01-07T14:30:00Z",
  "repository": "/home/paul/my-project",
  "branch": "feature-user-auth",
  "initial_commit": "71a0b89",
  "final_commit": "f5d3a2b",
  "original_commit_count": 8,
  "planned_commit_count": 3,
  "prompt": "Clean up the feature branch..."
}
```

```bash
# View the planned operations
cat /tmp/auth-cleanup-plan.json | jq '.operations[] | {type, description, new_message}'
```

**Output:**
```json
{
  "type": "squash",
  "description": "Combine initial auth implementation",
  "new_message": "feat(auth): implement user authentication system"
}
{
  "type": "drop",
  "description": "Remove debug logging commits"
}
{
  "type": "squash",
  "description": "Combine auth improvements and fixes",
  "new_message": "fix(auth): resolve test failures and improve validation"
}
{
  "type": "reword",
  "new_message": "docs(auth): fix typos in authentication documentation"
}
```

### Step 4: Review Detailed Operations

For more detail on what will happen:

```bash
# Pretty-print the full plan
cat /tmp/auth-cleanup-plan.json | jq '.'
```

This shows:
- Commits `93a2b01`, `b5a4c12`, `d7b6a34` will be squashed into "feat(auth): implement user authentication system"
- Commits `c6a5b23`, `e8c9d11` (debug-related) will be dropped
- Commit `a4b3c11` will be reworded to "fix(auth): resolve test failures and improve validation"
- Commit `f5d3a2b` will be reworded to "docs(auth): fix typos in authentication documentation"

### Step 5: Apply the Plan

If the plan looks good, apply it:

```bash
git-history-rewriter apply-plan \
  --plan /tmp/auth-cleanup-plan.json \
  --repo /home/paul/my-project
```

**Expected Output:**
```
Loading plan from: /tmp/auth-cleanup-plan.json

Git History Rewrite Plan
========================
Created: 2025-01-07T14:30:00
Repository: /home/paul/my-project
Commits: 71a0b89..f5d3a2b
Original commits: 8
Planned commits: 3

Operations:
-----------
  squash: 3
  reword: 2
  drop: 2

⚠ This will rewrite git history!
  Repository: /home/paul/my-project
  Commits: 71a0b89..f5d3a2b
  Operations: 7

Do you want to proceed? [y/N]: y

Creating backup branch: backup-20250107-143100

Executing plan...
[##########] 100% Complete

✓ Plan applied successfully!
  Backup branch: backup-20250107-143100

Next steps:
  1. Review changes: git log --oneline
  2. If satisfied: git push --force-with-lease
  3. To restore: git reset --hard backup-20250107-143100
```

### Step 6: Verify the Results

Check the new, clean history:

```bash
git log --oneline -5
```

**Output:**
```
a9f8e7d (HEAD -> feature-user-auth) docs(auth): fix typos in authentication documentation
b8e7d6c fix(auth): resolve test failures and improve validation
c7d6e5b feat(auth): implement user authentication system
82a1b90 add user model
71a0b89 (main) Previous feature merged
```

Much cleaner! The history now tells a clear story.

### Step 7: Push Changes (If Satisfied)

If everything looks good:

```bash
# Force push with lease for safety
git push --force-with-lease origin feature-user-auth
```

### Step 8: Restore If Needed

If something went wrong or you're not satisfied:

```bash
# Restore from the automatic backup
git reset --hard backup-20250107-143100

# Delete the backup branch when no longer needed
git branch -d backup-20250107-143100
```

## Alternative Workflows

### Workflow with Manual Plan Review

You can edit the plan before applying:

```bash
# Generate plan
git-history-rewriter rewrite --dry-run --save-plan plan.json ...

# Edit the plan manually
vim plan.json
# For example, change a commit message or remove an operation

# Apply the edited plan
git-history-rewriter apply-plan --plan plan.json --repo .
```

### Workflow with Team Review

For shared branches, get team approval first:

```bash
# Developer A generates plan
git-history-rewriter rewrite \
  --repo . \
  --prompt "Clean up release branch" \
  --initial-commit develop \
  --final-commit HEAD \
  --dry-run \
  --save-plan release-cleanup.json

# Share plan with team
cp release-cleanup.json /shared/plans/
# Or commit it:
git add release-cleanup.json
git commit -m "chore: propose git history cleanup for release"
git push

# Team reviews plan in PR/code review

# Developer B applies approved plan
git pull
git-history-rewriter apply-plan \
  --plan release-cleanup.json \
  --repo . \
  --force  # Skip confirmation since it was reviewed
```

### Workflow for Multiple Branches

Clean up several feature branches:

```bash
# Create plans for each branch
for branch in feature-1 feature-2 feature-3; do
  git checkout $branch
  git-history-rewriter rewrite \
    --repo . \
    --prompt "Clean up feature branch" \
    --initial-commit main \
    --final-commit HEAD \
    --dry-run \
    --save-plan plans/${branch}.json
done

# Review all plans
for plan in plans/*.json; do
  echo "=== Plan: $plan ==="
  cat $plan | jq '.operations[] | {type, new_message}'
done

# Apply all plans if they look good
for branch in feature-1 feature-2 feature-3; do
  git checkout $branch
  git-history-rewriter apply-plan \
    --plan plans/${branch}.json \
    --repo . \
    --backup-branch backup-${branch}
done
```

## Tips and Best Practices

### 1. Always Review Plans Carefully
- Check that important commits aren't being dropped
- Verify commit messages make sense
- Ensure the planned commit count is reasonable

### 2. Use Descriptive Prompts
Good prompt:
```bash
--prompt "Group authentication commits together, remove debug code, follow conventional commits"
```

Bad prompt:
```bash
--prompt "clean up"
```

### 3. Test on a Copy First
For critical repositories:
```bash
# Clone to a test location
git clone /important/repo /tmp/test-repo
cd /tmp/test-repo

# Test the rewrite there first
git-history-rewriter rewrite --dry-run --save-plan test.json ...
git-history-rewriter apply-plan --plan test.json --repo .

# If it works well, use the same plan on the real repo
```

### 4. Save Important Plans
Keep plans for documentation:
```bash
mkdir -p .git-rewrite-history/
cp cleanup-plan.json .git-rewrite-history/2025-01-07-feature-cleanup.json
```

### 5. Coordinate with Team
- Never rewrite public/shared history without coordination
- Use `--force-with-lease` instead of `--force` when pushing
- Communicate with team members who have the branch checked out

## Troubleshooting

### Plan Generation Fails

**Problem:** Claude can't understand the repository structure

**Solution:** Be more specific in your prompt:
```bash
--prompt "The commits from abc123 to def456 implement user authentication. 
          Squash implementation commits together, keep bug fixes separate, 
          and improve messages to follow format: type(scope): description"
```

### Plan Application Fails

**Problem:** Git commands in plan fail to execute

**Solutions:**
1. Check for uncommitted changes: `git status`
2. Ensure you're on the right branch: `git branch`
3. Verify commits exist: `git log --oneline`
4. Use `--verbose` flag to see detailed errors

### Wrong Changes Applied

**Problem:** The plan did something unexpected

**Solutions:**
1. Immediately restore from backup: `git reset --hard backup-[timestamp]`
2. Review the plan file to understand what happened
3. Generate a new plan with more specific instructions

### Merge Conflicts After Rewrite

**Problem:** Rewritten branch conflicts with other branches

**Solutions:**
1. This is normal when rewriting history
2. Resolve conflicts as usual during merge/rebase
3. Consider rewriting before branching in the future

## Advanced Scenarios

### Handling Merge Commits

When your history includes merges:

```bash
git-history-rewriter rewrite \
  --repo . \
  --prompt "Clean up feature branch but preserve merge commits from main" \
  --initial-commit main \
  --final-commit HEAD \
  --dry-run \
  --save-plan plan.json
```

### Rewriting After Code Review

Clean up commits after addressing review comments:

```bash
git-history-rewriter rewrite \
  --repo . \
  --prompt "Squash all 'address review comments' commits into the relevant feature commits" \
  --initial-commit origin/feature-branch \
  --final-commit HEAD \
  --dry-run \
  --save-plan post-review-cleanup.json
```

### Preparing for Release

Clean history before merging to main:

```bash
git-history-rewriter rewrite \
  --repo . \
  --prompt "Prepare for release: ensure each commit is atomic, 
           remove all WIP/temporary commits, 
           format messages as 'type(scope): description' for changelog generation" \
  --initial-commit main \
  --final-commit HEAD \
  --dry-run \
  --save-plan release-prep.json \
  --model claude-3-opus  # Use more powerful model for complex rewrite
```

## Summary

The two-phase approach (plan then apply) provides:
1. **Safety**: Review before making changes
2. **Flexibility**: Edit plans if needed
3. **Collaboration**: Share plans with team
4. **Documentation**: Keep plans as records
5. **Confidence**: Automatic backups ensure you can recover

This workflow transforms git history rewriting from a risky operation into a controlled, reviewable process.