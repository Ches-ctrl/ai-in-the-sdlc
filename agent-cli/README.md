# Git History Rewriter

AI-powered git history rewriting tool using Claude Code SDK.

## Features

- **Repository Cloning**: Clone any git repository and checkout specific branches
- **Branch Management**: Automatically fetch and checkout remote branches
- **Flexible Authentication**: Support for both HTTPS and SSH URLs
- **Progress Indication**: Visual feedback during clone operations
- **Verbose Mode**: Detailed logging for debugging
- **Two-Phase Rewrite**: Generate plans first, then apply them for safer history rewriting
- **AI-Powered Analysis**: Use Claude to analyze and improve commit history
- **Plan-Based Workflow**: Review changes before applying them

### Key Capabilities
- Generate rewrite plans without modifying history
- Save and share plans as JSON files
- Apply plans using Claude AI agent for intelligent execution
- Handle interactive rebase operations programmatically
- Analyze commit patterns and suggest improvements
- Support for squashing, rewording, dropping, and reordering commits
- Automatic backup creation before any history modification

## Installation

### Prerequisites
- Python 3.10 or higher
- Git installed and configured

### From Source

1. Clone this repository:
```bash
git clone https://github.com/yourusername/git-history-rewriter.git
cd git-history-rewriter
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install in development mode:
```bash
pip install -e .
```

## Usage

### Plan-Based History Rewriting (Recommended)

The recommended workflow uses a two-phase approach for safer history rewriting:

#### Step 1: Generate a Rewrite Plan
```bash
git-history-rewriter rewrite \
  --repo ./my-project \
  --prompt "Squash WIP commits and improve commit messages" \
  --initial-commit HEAD~10 \
  --final-commit HEAD \
  --dry-run \
  --save-plan ./rewrite-plan.json
```

This generates a plan file without modifying your repository.

#### Step 2: Review the Plan
```bash
# View plan summary
cat ./rewrite-plan.json | jq '.metadata'

# View planned operations
cat ./rewrite-plan.json | jq '.operations'
```

#### Step 3: Apply the Plan
```bash
git-history-rewriter apply-plan \
  --plan ./rewrite-plan.json \
  --repo ./my-project
```

This uses Claude AI to intelligently execute the plan with automatic backup creation. The agent handles complex operations like interactive rebase programmatically.

### Clone a Repository

Basic usage:
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/repo.git \
  --branch main \
  --target-dir ./workspace
```

Clone with verbose output:
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/repo.git \
  --branch develop \
  --target-dir ./repos/project \
  --verbose
```

Clone private repository with SSH:
```bash
git-history-rewriter clone \
  --repo-url git@github.com:org/private-repo.git \
  --branch feature/new-feature \
  --target-dir /tmp/analysis
```

Shallow clone for faster operation:
```bash
git-history-rewriter clone \
  --repo-url https://github.com/large/repository.git \
  --branch main \
  --target-dir ./workspace \
  --depth 10
```

### Command Options

#### `rewrite` Command

| Option | Required | Description |
|--------|----------|-------------|
| `--repo` | Yes | Repository path |
| `--prompt` | Yes | Instructions for how to rewrite history |
| `--initial-commit` | Yes | Starting commit SHA (older) |
| `--final-commit` | Yes | Ending commit SHA (newer) |
| `--dry-run` | No | Generate plan without executing |
| `--save-plan` | No | Save plan to JSON file (use with --dry-run) |
| `--model` | No | Claude model to use |
| `--permission-mode` | No | Permission mode for tools |
| `--verbose` | No | Enable detailed output |

#### `apply-plan` Command

| Option | Required | Description |
|--------|----------|-------------|
| `--plan` | Yes | Path to plan JSON file |
| `--repo` | Yes | Repository path |
| `--backup-branch` | No | Custom backup branch name |
| `--force` | No | Skip confirmation prompts |
| `--verbose` | No | Enable detailed output |

#### `analyze` Command

| Option | Required | Description |
|--------|----------|-------------|
| `--repo` | Yes | Repository path |
| `--initial-commit` | Yes | Starting commit SHA |
| `--final-commit` | Yes | Ending commit SHA |
| `--verbose` | No | Enable detailed output |

#### `clone` Command

| Option | Required | Description |
|--------|----------|-------------|
| `--repo-url` | Yes | Repository URL (HTTPS or SSH format) |
| `--branch` | Yes | Branch to checkout after cloning |
| `--target-dir` | Yes | Directory where repository will be cloned |
| `--verbose` | No | Enable detailed output and logging |
| `--depth` | No | Create shallow clone with specified depth |

### Examples

#### Plan-Based Rewrite Example
```bash
# Step 1: Generate a plan to clean up feature branch
git-history-rewriter rewrite \
  --repo ./my-feature \
  --prompt "Squash all 'WIP' and 'fix' commits, group by feature" \
  --initial-commit main \
  --final-commit HEAD \
  --dry-run \
  --save-plan cleanup-plan.json

# Step 2: Review what will change
cat cleanup-plan.json | jq '.operations[] | {type, description}'

# Step 3: Apply the reviewed plan
git-history-rewriter apply-plan \
  --plan cleanup-plan.json \
  --repo ./my-feature \
  --backup-branch before-cleanup
```

#### Direct Rewrite (Without Plan)
```bash
# Directly rewrite history (use with caution)
git-history-rewriter rewrite \
  --repo ./my-project \
  --prompt "Improve all commit messages to follow conventional commits" \
  --initial-commit HEAD~5 \
  --final-commit HEAD \
  --permission-mode acceptEdits
```

#### Analyze Before Rewriting
```bash
# Get AI suggestions without making changes
git-history-rewriter analyze \
  --repo ./my-project \
  --initial-commit HEAD~10 \
  --final-commit HEAD
```

#### Clone Public Repository
```bash
git-history-rewriter clone \
  --repo-url https://github.com/python/cpython.git \
  --branch main \
  --target-dir ./python-source
```

#### Clone and Checkout Feature Branch
```bash
git-history-rewriter clone \
  --repo-url https://github.com/django/django.git \
  --branch stable/4.2.x \
  --target-dir ./django-stable
```

#### Clone with Progress Display
```bash
git-history-rewriter clone \
  --repo-url https://github.com/torvalds/linux.git \
  --branch master \
  --target-dir ./linux \
  --verbose
```

## Error Handling

The tool provides clear error messages for common issues:

### Invalid Repository URL
```
✗ Error: Invalid repository URL format: not-a-url
Expected format: https://github.com/user/repo.git or git@github.com:user/repo.git
```

### Non-Existent Branch
```
✗ Error: Branch 'non-existent' not found

Available branches:
  - main
  - develop
  - feature/login

Tip: Use one of the available branches or check the branch name
```

### Authentication Issues
```
✗ Error: Authentication failed for repository: https://github.com/org/private-repo.git
For private repositories:
  - Use SSH URL with configured SSH keys
  - Or provide authentication token for HTTPS
```

## Development

### Project Structure
```
git-history-rewriter/
├── src/
│   └── git_history_rewriter/
│       ├── __init__.py
│       ├── cli.py              # CLI interface with Click
│       └── git/
│           ├── __init__.py
│           └── operations.py   # Git operations
├── tests/
│   └── test_git_operations.py  # Unit tests
├── docs/
│   └── user-flows.md           # Detailed user workflows
├── requirements.txt            # Production dependencies
├── pyproject.toml             # Package configuration
└── README.md
```

### Running Tests

Install development dependencies:
```bash
pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=git_history_rewriter --cov-report=term-missing
```

### Code Quality

Format code:
```bash
black src/ tests/
```

Run linter:
```bash
ruff src/ tests/
```

Type checking:
```bash
mypy src/
```

## Roadmap

### Phase 1: Core Cloning (Completed)
- ✅ Repository cloning with branch checkout
- ✅ Support for HTTPS and SSH URLs
- ✅ Progress indication
- ✅ Error handling

### Phase 2: History Analysis (Completed)
- ✅ Commit range analysis
- ✅ Commit statistics and patterns
- ✅ AI-powered commit analysis

### Phase 3: AI Integration (Completed)
- ✅ Claude Code SDK integration
- ✅ Prompt template system
- ✅ Custom instruction processing
- ✅ Plan generation with AI

### Phase 4: History Rewriting (Completed)
- ✅ Plan-based rewriting workflow
- ✅ Two-phase approach (plan & apply)
- ✅ Intelligent commit squashing
- ✅ Commit message improvement
- ✅ Automatic backup creation

### Phase 5: Advanced Features (In Progress)
- [ ] JSONL conversation context loading
- [ ] Plan validation and verification
- [ ] Batch operations
- [ ] Configuration file support
- [ ] Web UI for monitoring
- [ ] Integration with CI/CD pipelines

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI interface
- Uses [GitPython](https://gitpython.readthedocs.io/) for git operations
- Styled with [Rich](https://rich.readthedocs.io/) for beautiful terminal output