# Git History Rewriter - Command Reference

Git History Rewriter is an AI-powered CLI tool that uses Claude to intelligently rewrite git repository history based on natural language instructions.

## Installation

```bash
# Install with pip
pip install -e .

# Or with uv
uv pip install -e .
```

## Commands Overview

| Command | Purpose | Changes Repository |
|---------|---------|-------------------|
| `clone` | Clone repository and checkout branch | No (creates new) |
| `history` | View commit history between two points | No |
| `analyze` | AI analysis of commits with suggestions | No |
| `rewrite` | AI-powered history rewriting | Yes (unless --dry-run) |
| `prepare` | Prepare for rewriting (coming soon) | No |

## Command Details

### `clone` - Clone and Checkout Repositories

Clone a repository and checkout a specific branch.

#### Syntax
```bash
git-history-rewriter clone [OPTIONS]
```

#### Options
| Option | Required | Description |
|--------|----------|-------------|
| `--repo-url` | Yes | Repository URL (HTTPS or SSH) |
| `--branch` | Yes | Branch to checkout |
| `--target-dir` | Yes | Target directory for clone |
| `--depth` | No | Create shallow clone with specified depth |
| `--verbose` | No | Enable verbose output |

#### Example
```bash
git-history-rewriter clone \
  --repo-url https://github.com/octocat/Hello-World.git \
  --branch master \
  --target-dir ./hello-world \
  --depth 1
```

#### Output
- Clones repository to specified directory
- Checks out requested branch
- Shows repository information (commits, location, branch)

---

### `history` - View Commit History

Display commit history between two commits in chronological order.

#### Syntax
```bash
git-history-rewriter history [OPTIONS]
```

#### Options
| Option | Required | Description |
|--------|----------|-------------|
| `--repo` | Yes | Path to git repository |
| `--initial-commit` | Yes | Starting commit SHA (older) |
| `--final-commit` | Yes | Ending commit SHA (newer) |
| `--verbose` | No | Show detailed statistics |

#### Example
```bash
git-history-rewriter history \
  --repo ./my-project \
  --initial-commit HEAD~10 \
  --final-commit HEAD \
  --verbose
```

#### Output
- Commit list with SHA, author, date, and message
- File statistics (with --verbose)
- Summary of total commits

---

### `analyze` - AI-Powered Commit Analysis

Use Claude to analyze commit history and suggest improvements without making changes.

#### Syntax
```bash
git-history-rewriter analyze [OPTIONS]
```

#### Options
| Option | Required | Description |
|--------|----------|-------------|
| `--repo` | Yes | Path to git repository |
| `--initial-commit` | Yes | Starting commit SHA |
| `--final-commit` | Yes | Ending commit SHA |
| `--verbose` | No | Enable verbose output |

#### Example
```bash
git-history-rewriter analyze \
  --repo ./my-project \
  --initial-commit main \
  --final-commit feature-branch
```

#### Output
- Total number of commits analyzed
- Summary of changes (files modified, lines added/removed)
- Identified patterns (WIP commits, duplicates, poor messages)
- Actionable suggestions for improvement

---

### `rewrite` - AI-Powered History Rewriting

Use Claude to intelligently rewrite git history based on natural language instructions.

#### Syntax
```bash
git-history-rewriter rewrite [OPTIONS]
```

#### Options
| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--repo` | Yes | Path to git repository | - |
| `--prompt` | Yes | Natural language rewrite instructions | - |
| `--initial-commit` | Yes | Starting commit SHA (older) | - |
| `--final-commit` | Yes | Ending commit SHA (newer) | - |
| `--model` | No | Claude model to use | Claude's default |
| `--permission-mode` | No | Tool permission level | `acceptEdits` |
| `--dry-run` | No | Preview without making changes | False |
| `--verbose` | No | Enable verbose output | False |

#### Permission Modes
- `default`: CLI prompts for dangerous operations
- `acceptEdits`: Auto-accept file edits (recommended)
- `bypassPermissions`: Allow all operations (use with caution)

#### Example - Dry Run
```bash
git-history-rewriter rewrite \
  --repo ./my-project \
  --prompt "Squash all WIP commits and improve commit messages" \
  --initial-commit HEAD~10 \
  --final-commit HEAD \
  --dry-run
```

#### Example - Actual Rewrite
```bash
git-history-rewriter rewrite \
  --repo ./my-project \
  --prompt "Group commits by feature, use conventional commit format" \
  --initial-commit abc123 \
  --final-commit def456 \
  --permission-mode acceptEdits
```

#### Output
- Creates backup branch before modifications
- Executes git operations (rebase, squash, reword, etc.)
- Shows operation summary:
  - Duration
  - Number of Claude turns
  - Cost in USD
  - Tools used count
- Provides next steps for review and push

#### Safety Features
- Automatic backup branch creation
- Dry-run mode for preview
- State verification after rewrite
- Clear error messages with recovery hints

---

## Common Workflows

### 1. Clean Up Recent Work
```bash
# Analyze first
git-history-rewriter analyze \
  --repo . \
  --initial-commit HEAD~5 \
  --final-commit HEAD

# Then rewrite
git-history-rewriter rewrite \
  --repo . \
  --prompt "Squash fixup commits, improve messages, group by feature" \
  --initial-commit HEAD~5 \
  --final-commit HEAD
```

### 2. Prepare Feature Branch for PR
```bash
# Preview changes
git-history-rewriter rewrite \
  --repo . \
  --prompt "Clean up for PR: squash WIP, use conventional commits" \
  --initial-commit main \
  --final-commit feature-branch \
  --dry-run

# Apply if satisfied
git-history-rewriter rewrite \
  --repo . \
  --prompt "Clean up for PR: squash WIP, use conventional commits" \
  --initial-commit main \
  --final-commit feature-branch
```

### 3. Clone and Clean External Repository
```bash
# Clone repository
git-history-rewriter clone \
  --repo-url git@github.com:user/project.git \
  --branch develop \
  --target-dir ./project

# Analyze commit quality
git-history-rewriter analyze \
  --repo ./project \
  --initial-commit HEAD~20 \
  --final-commit HEAD

# Rewrite based on analysis
git-history-rewriter rewrite \
  --repo ./project \
  --prompt "Fix issues from analysis: improve messages, remove duplicates" \
  --initial-commit HEAD~20 \
  --final-commit HEAD
```

### 4. Conventional Commit Migration
```bash
git-history-rewriter rewrite \
  --repo . \
  --prompt "Convert all commits to conventional commit format (feat, fix, chore, docs)" \
  --initial-commit origin/main \
  --final-commit HEAD
```

## Prompt Examples

### Effective Prompts for `rewrite`

**Good Prompts:**
- "Squash all commits with 'WIP' or 'temp' in the message"
- "Group commits by feature and use conventional commit format"
- "Combine the two 'feat: tools' commits into one"
- "Improve commit messages to be more descriptive, explain the why not just what"
- "Organize commits: first infrastructure, then features, then tests"

**Less Effective Prompts:**
- "Fix commits" (too vague)
- "Make better" (not specific)
- "Change everything" (too broad)

## Tips and Best Practices

1. **Always use dry-run first** to preview changes before actual rewriting
2. **Start with analyze** to understand the current state
3. **Be specific in prompts** - Claude works best with clear instructions
4. **Work with small ranges** - Rewriting 5-20 commits is more reliable than 100+
5. **Check backup branches** - Tool creates backups, keep them until you're sure
6. **Review before pushing** - Always review with `git log` before force-pushing

## Troubleshooting

### Common Issues

**"No commits found in range"**
- Ensure initial_commit is an ancestor of final_commit
- Use `git log` to verify commit SHAs exist

**"Authentication failed"**
- For private repos, ensure SSH keys are configured
- Use SSH URLs (git@github.com:...) for private repositories

**High API costs**
- Use --dry-run to preview before actual rewriting
- Work with smaller commit ranges
- Be specific in prompts to reduce back-and-forth

## Requirements

- Python 3.10+
- Git installed and configured
- Claude API access (via Claude Code SDK)
- Repository with git history to rewrite

## Related Documentation

- [User Flows](./user-flows.md) - Detailed usage scenarios
- [Architecture](../sessions/architecture/git-history-rewriter-cli.md) - Technical design
- [README](../README.md) - Project overview and setup