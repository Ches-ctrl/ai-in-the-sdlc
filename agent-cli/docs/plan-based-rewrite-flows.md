# Git History Rewriter - Plan-Based Rewrite Flows

## Overview
This document describes the two-phase plan-based approach for rewriting git history. The system separates planning from execution, allowing users to review and approve changes before they are applied.

## Table of Contents
1. [Core Workflow](#core-workflow)
2. [Plan Generation](#plan-generation)
3. [Plan Review](#plan-review)
4. [Plan Application](#plan-application)
5. [Error Scenarios](#error-scenarios)
6. [Plan File Format](#plan-file-format)

## Core Workflow

The plan-based rewrite follows a two-phase approach:

1. **Planning Phase**: Analyze repository and generate a rewrite plan
2. **Execution Phase**: Apply the saved plan to rewrite history

### Benefits of Two-Phase Approach
- **Safety**: Review changes before execution
- **Reproducibility**: Save and reuse plans
- **Collaboration**: Share plans with team for review
- **Debugging**: Inspect what AI plans to do
- **Control**: Modify plans manually if needed

## Plan Generation

### Basic Plan Generation
**Goal:** Generate a plan to improve commit history

**Command:**
```bash
git-history-rewriter rewrite \
  --repo ./my-project \
  --prompt "Squash all WIP commits and improve commit messages" \
  --initial-commit HEAD~10 \
  --final-commit HEAD \
  --dry-run \
  --save-plan ./rewrite-plan.json
```

**Expected Output:**
```
Analyzing repository history...
Found 10 commits to process

Generating rewrite plan with Claude...
✓ Plan generated successfully

Plan Summary:
- Original commits: 10
- Planned commits: 6
- Operations: 4 squashes, 6 rewords

Plan saved to: ./rewrite-plan.json

Review the plan with: cat ./rewrite-plan.json
Apply the plan with: git-history-rewriter apply-plan --plan ./rewrite-plan.json --repo ./my-project
```

### Plan Generation with Specific Instructions
**Goal:** Generate a plan with detailed instructions

**Command:**
```bash
git-history-rewriter rewrite \
  --repo ./backend-api \
  --prompt "Group commits by feature: auth, database, api. Each group should have one commit with a conventional commit message" \
  --initial-commit abc123 \
  --final-commit def456 \
  --dry-run \
  --save-plan ./feature-grouping-plan.json \
  --verbose
```

**Verbose Output:**
```
[INFO] Repository: ./backend-api
[INFO] Analyzing commits from abc123 to def456
[INFO] Found 15 commits in range

[INFO] Sending to Claude for analysis...
[INFO] Model: claude-3.5-sonnet

Claude Analysis:
- Identified 3 feature groups:
  * Authentication (5 commits)
  * Database migrations (4 commits)  
  * API endpoints (6 commits)

[INFO] Generating rewrite operations...

Operations:
1. Squash commits 1-5 → "feat(auth): implement JWT authentication"
2. Squash commits 6-9 → "feat(db): add user and session tables"
3. Squash commits 10-15 → "feat(api): add user management endpoints"

✓ Plan generated and saved to: ./feature-grouping-plan.json
```

### Plan Generation for Complex Scenarios
**Goal:** Handle merge commits and complex history

**Command:**
```bash
git-history-rewriter rewrite \
  --repo ./monorepo \
  --prompt "Clean up messy feature branch: remove debug commits, squash fixes, improve messages" \
  --initial-commit feature-start \
  --final-commit feature-end \
  --dry-run \
  --save-plan ./cleanup-plan.json \
  --model claude-3-opus \
  --permission-mode acceptEdits
```

## Plan Review

### Viewing Plan Summary
**Command:**
```bash
cat ./rewrite-plan.json | jq '.metadata'
```

**Output:**
```json
{
  "version": "1.0",
  "created_at": "2025-01-07T10:30:00Z",
  "repository": "./my-project",
  "initial_commit": "abc123",
  "final_commit": "def456",
  "original_commit_count": 10,
  "planned_commit_count": 6,
  "prompt": "Squash all WIP commits and improve commit messages"
}
```

### Viewing Planned Operations
**Command:**
```bash
cat ./rewrite-plan.json | jq '.operations'
```

**Output:**
```json
[
  {
    "type": "squash",
    "commits": ["abc123", "bcd234", "cde345"],
    "new_message": "feat: add user authentication",
    "description": "Combines WIP auth commits into single feature commit"
  },
  {
    "type": "reword",
    "commit": "def456",
    "old_message": "fix bug",
    "new_message": "fix(api): resolve null pointer in user endpoint"
  }
]
```

### Human-Readable Plan Review
**Command:**
```bash
git-history-rewriter show-plan --plan ./rewrite-plan.json
```

**Output:**
```
Git History Rewrite Plan
========================
Created: 2025-01-07 10:30:00
Repository: ./my-project
Commits: 10 → 6

Operations:
-----------
1. SQUASH (3 commits → 1)
   - abc123: WIP: auth
   - bcd234: more auth work
   - cde345: finish auth
   Into: "feat: add user authentication"

2. REWORD
   - def456: "fix bug" 
   → "fix(api): resolve null pointer in user endpoint"

3. DROP
   - efg567: "debug logging"
   (Temporary debug code, safe to remove)

4. SQUASH (2 commits → 1)
   - fgh678: "database changes"
   - ghi789: "fix migration"
   Into: "feat(db): add indexes for performance"
```

## Plan Application

### Basic Plan Application
**Goal:** Apply a saved plan to rewrite history

**Command:**
```bash
git-history-rewriter apply-plan \
  --plan ./rewrite-plan.json \
  --repo ./my-project
```

**Expected Flow:**
```
Loading plan from: ./rewrite-plan.json

Git History Rewrite Plan
========================
Created: 2025-01-07 10:30:00
Repository: ./my-project
Commits: abc123..def456
Original commits: 10
Planned commits: 6

Operations:
-----------
  reword: 2
  squash: 2

This will rewrite git history from abc123 to def456
Current branch: feature-branch

⚠ WARNING: This will rewrite history. Make sure to:
  - Have no uncommitted changes
  - Not rewrite public/shared commits
  - Have a backup of important work

Continue? [y/N]: y

Creating backup branch: backup-2025-01-07-103500

Executing plan with Claude agent...

Claude: I'll execute the git history rewrite plan step by step...
[Using Claude AI to intelligently handle interactive rebase]

✓ Plan applied successfully!
  Backup branch: backup-2025-01-07-103500
  Duration: 45.2 seconds
  Turns: 15
  Cost: $0.3521
  Tools used: 12 times

Next steps:
1. Review with: git log --oneline
2. If satisfied: git push --force-with-lease
3. To restore: git reset --hard backup-2025-01-07-103500
```

**Note:** The apply-plan command uses Claude AI agent to intelligently execute the plan. This allows it to:
- Handle interactive rebase operations programmatically
- Adapt to unexpected situations during rebase
- Create custom editor scripts for complex operations
- Verify the results match the intended plan

### Plan Application with Verbose Mode
**Command:**
```bash
git-history-rewriter apply-plan \
  --plan ./rewrite-plan.json \
  --repo ./my-project \
  --verbose
```

**Verbose Output:**
```
Loading plan from: ./rewrite-plan.json

[Plan summary displayed]

Creating backup branch: backup-2025-01-07-103500

ℹ Applying saved plan in ./my-project
ℹ Permission mode: acceptEdits

Claude: I'll execute the git history rewrite plan step by step...
ℹ Using tool: Bash
Claude: Now I'll create a script to handle the interactive rebase...
ℹ Using tool: Write
Claude: Setting up custom editor for rebase...
ℹ Using tool: Bash

[Additional Claude interactions with tools]

Claude: Verifying the rebase results...
ℹ Using tool: Bash
Claude: Perfect! The history has been successfully rewritten.

ℹ Plan applied successfully

✓ Plan applied successfully!
  Backup branch: backup-2025-01-07-103500
  Duration: 52.3 seconds
  Turns: 18
  Cost: $0.4123
  Tools used: 15 times
```

### Applying Plan with Custom Backup
**Command:**
```bash
git-history-rewriter apply-plan \
  --plan ./rewrite-plan.json \
  --repo ./my-project \
  --backup-branch pre-cleanup-backup
```

## Error Scenarios

### Plan File Not Found
**Command:**
```bash
git-history-rewriter apply-plan --plan ./missing-plan.json --repo ./my-project
```

**Error:**
```
✗ Error: Plan file not found: ./missing-plan.json
Please specify a valid plan file generated by 'rewrite --dry-run --save-plan'
```

### Repository Mismatch
**Scenario:** Attempting to apply plan to wrong repository

**Error:**
```
✗ Error: Plan repository mismatch
  Plan created for: ./project-a
  Attempting to apply to: ./project-b
  
Use --force to override this check (dangerous!)
```

### Uncommitted Changes
**Scenario:** Working directory has uncommitted changes

**Error:**
```
✗ Error: Uncommitted changes detected

Please commit or stash your changes before rewriting history:
  Modified: src/main.py
  Modified: tests/test_main.py

Run: git stash
Or:  git commit -am "Save work before rewrite"
```

### Commits Not Found
**Scenario:** Plan references commits that don't exist

**Error:**
```
✗ Error: Commit not found in repository
  Plan references: abc123
  This commit does not exist in the current repository
  
Possible causes:
  - Plan was generated for different branch
  - Repository has been modified since plan creation
  - Plan file is corrupted

Suggestion: Regenerate the plan with current repository state
```

## Plan File Format

### JSON Structure
```json
{
  "version": "1.0",
  "metadata": {
    "created_at": "2025-01-07T10:30:00Z",
    "created_by": "git-history-rewriter",
    "repository": "./my-project",
    "branch": "feature-branch",
    "initial_commit": "abc123",
    "final_commit": "def456",
    "prompt": "Original user instructions",
    "model": "claude-3.5-sonnet",
    "original_commits": [
      {
        "sha": "abc123",
        "message": "WIP: auth",
        "author": "John Doe",
        "date": "2025-01-05T10:00:00Z"
      }
    ]
  },
  "operations": [
    {
      "type": "squash",
      "commits": ["abc123", "bcd234", "cde345"],
      "new_message": "feat: add user authentication",
      "description": "Combines WIP auth commits"
    },
    {
      "type": "reword",
      "commit": "def456",
      "old_message": "fix bug",
      "new_message": "fix(api): resolve null pointer in user endpoint"
    },
    {
      "type": "drop",
      "commit": "efg567",
      "reason": "Temporary debug code"
    },
    {
      "type": "reorder",
      "from_position": 5,
      "to_position": 3,
      "commit": "fgh678"
    }
  ],
  "commands": [
    "git checkout feature-branch",
    "git rebase -i abc123^",
    "# Interactive rebase commands will be applied"
  ],
  "verification": {
    "expected_final_count": 6,
    "expected_final_sha": null
  }
}
```

### Operation Types

#### Squash Operation
```json
{
  "type": "squash",
  "commits": ["sha1", "sha2", "sha3"],
  "new_message": "Combined commit message",
  "description": "Why these commits are being squashed"
}
```

#### Reword Operation
```json
{
  "type": "reword",
  "commit": "sha",
  "old_message": "Original message",
  "new_message": "Improved message",
  "reason": "Why the message is being changed"
}
```

#### Drop Operation
```json
{
  "type": "drop",
  "commit": "sha",
  "message": "Original message",
  "reason": "Why this commit is being removed"
}
```

#### Reorder Operation
```json
{
  "type": "reorder",
  "commit": "sha",
  "from_position": 5,
  "to_position": 2,
  "reason": "Why reordering is needed"
}
```

## Advanced Usage

### Editing Plans Manually
Plans are JSON files and can be edited before application:

1. Generate plan:
   ```bash
   git-history-rewriter rewrite --dry-run --save-plan plan.json ...
   ```

2. Edit plan:
   ```bash
   vim plan.json
   # Modify operations, messages, etc.
   ```

3. Apply modified plan:
   ```bash
   git-history-rewriter apply-plan --plan plan.json --repo .
   ```

### Sharing Plans for Review
```bash
# Developer generates plan
git-history-rewriter rewrite --dry-run --save-plan cleanup.json ...

# Share with team
cp cleanup.json shared/plans/
git add shared/plans/cleanup.json
git commit -m "Plan for cleaning feature branch history"
git push

# Team reviews and approves

# Apply approved plan
git-history-rewriter apply-plan --plan shared/plans/cleanup.json --repo .
```

### Batch Processing
```bash
# Generate multiple plans
for branch in feature-1 feature-2 feature-3; do
  git checkout $branch
  git-history-rewriter rewrite \
    --dry-run \
    --save-plan plans/${branch}-cleanup.json \
    --initial-commit main \
    --final-commit HEAD \
    --prompt "Clean up feature branch"
done

# Review all plans
ls plans/*.json | xargs -I {} git-history-rewriter show-plan --plan {}

# Apply all plans
for plan in plans/*.json; do
  branch=$(basename $plan .json)
  git checkout $branch
  git-history-rewriter apply-plan --plan $plan --repo .
done
```

## Best Practices

1. **Always Create Backups**: The tool creates automatic backups, but consider additional backups for critical work

2. **Review Plans Carefully**: Especially when rewriting shared history

3. **Test on Copies First**: For complex rewrites, test on a repository copy

4. **Document Plan Decisions**: Use descriptive prompts and save plans with meaningful names

5. **Version Control Plans**: Consider storing important plans in version control for documentation

6. **Coordinate with Team**: When rewriting shared branches, coordinate with team members

## Troubleshooting

### Plan Won't Apply
- Ensure you're on the correct branch
- Check that the commit range exists
- Verify no uncommitted changes
- Try regenerating the plan

### Rewrite Failed Midway
- Check the backup branch: `git branch -a | grep backup`
- Reset to backup: `git reset --hard backup-[timestamp]`
- Review error messages for specific issues
- Consider breaking complex rewrites into smaller operations

### Unexpected Results
- Review the plan file to understand what was executed
- Use git reflog to see all operations
- Reset to backup branch if needed
- Regenerate plan with more specific instructions