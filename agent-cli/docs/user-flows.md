# Git History Rewriter - User Flows

## Overview
This document describes the expected user flows and interactions with the git-history-rewriter CLI tool. These flows serve as both documentation and test scenarios for the implementation.

## Table of Contents
1. [Basic Clone Operations](#basic-clone-operations)
2. [Error Handling Scenarios](#error-handling-scenarios)
3. [Authentication Flows](#authentication-flows)
4. [Advanced Operations](#advanced-operations)
5. [Future Features](#future-features)

## Basic Clone Operations

### 1. Simple Repository Clone
**Goal:** Clone a public repository and checkout a specific branch

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/project.git \
  --branch main \
  --target-dir ./workspace/project
```

**Expected Flow:**
1. Validate the repository URL format
2. Check if target directory exists (create if not)
3. Clone the repository to the target directory
4. Checkout the specified branch
5. Display success message with repository info

**Success Output:**
```
✓ Repository cloned successfully
  URL: https://github.com/user/project.git
  Branch: main
  Location: ./workspace/project
  Commits: 234 commits
```

### 2. Clone with Feature Branch
**Goal:** Clone a repository and checkout a feature branch

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/org/app.git \
  --branch feature/new-authentication \
  --target-dir /tmp/review/app
```

**Expected Flow:**
1. Clone the repository
2. Fetch all remote branches
3. Checkout the feature branch
4. Verify branch exists remotely
5. Display branch information

### 3. Verbose Clone Operation
**Goal:** Clone with detailed progress information

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/large/repository.git \
  --branch develop \
  --target-dir ./repos/large-repo \
  --verbose
```

**Expected Output:**
```
[INFO] Validating repository URL...
[INFO] Creating target directory: ./repos/large-repo
[INFO] Initiating clone operation...
[PROGRESS] Cloning: 15% (234/1560 objects)
[PROGRESS] Cloning: 30% (468/1560 objects)
[PROGRESS] Cloning: 60% (936/1560 objects)
[PROGRESS] Cloning: 100% (1560/1560 objects)
[INFO] Fetching branch information...
[INFO] Checking out branch: develop
[SUCCESS] Clone operation completed in 45.2 seconds
```

## Error Handling Scenarios

### 1. Invalid Repository URL
**Command:**
```bash
git-history-rewriter clone \
  --repo-url not-a-valid-url \
  --branch main \
  --target-dir ./workspace
```

**Expected Error:**
```
✗ Error: Invalid repository URL format
  Provided: not-a-valid-url
  Expected format: https://github.com/user/repo.git or git@github.com:user/repo.git
```

### 2. Non-Existent Branch
**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/project.git \
  --branch non-existent-branch \
  --target-dir ./workspace
```

**Expected Flow:**
1. Clone repository successfully
2. Attempt to checkout branch
3. Display error with available branches

**Error Output:**
```
✓ Repository cloned successfully
✗ Error: Branch 'non-existent-branch' not found
  
Available branches:
  - main
  - develop
  - feature/login
  - feature/dashboard
  
Tip: Use one of the available branches or check the branch name
```

### 3. Target Directory Already Exists
**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/project.git \
  --branch main \
  --target-dir ./existing-directory
```

**Expected Options:**
```
⚠ Warning: Directory './existing-directory' already exists

Options:
1. Delete existing directory and clone
2. Clone to a subdirectory (./existing-directory/project)
3. Cancel operation

Choose option [1-3]: _
```

### 4. Network Connection Issues
**Scenario:** Repository unreachable due to network issues

**Expected Error:**
```
✗ Error: Failed to connect to repository
  URL: https://github.com/user/project.git
  Reason: Connection timeout after 30 seconds
  
Troubleshooting:
  - Check your internet connection
  - Verify the repository URL is correct
  - Try again with --verbose for detailed output
```

### 5. Permission Denied
**Scenario:** No write permissions for target directory

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/project.git \
  --branch main \
  --target-dir /system/protected/
```

**Expected Error:**
```
✗ Error: Permission denied
  Cannot create directory: /system/protected/
  Reason: Insufficient permissions
  
Tip: Choose a directory where you have write permissions
```

## Authentication Flows

### 1. SSH Repository Clone
**Goal:** Clone a private repository using SSH

**Command:**
```bash
git-history-rewriter clone \
  --repo-url git@github.com:org/private-repo.git \
  --branch main \
  --target-dir ./private/repo
```

**Expected Flow:**
1. Detect SSH URL format
2. Use system SSH keys for authentication
3. Clone repository if authentication succeeds
4. Handle SSH key issues gracefully

**Potential SSH Key Error:**
```
✗ Error: SSH authentication failed
  Repository: git@github.com:org/private-repo.git
  
Troubleshooting:
  - Ensure your SSH key is added to GitHub
  - Check if ssh-agent is running
  - Verify key permissions (should be 600)
  
Test SSH connection:
  ssh -T git@github.com
```

### 2. HTTPS with Credentials
**Goal:** Clone private repository with HTTPS credentials

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/org/private-repo.git \
  --branch main \
  --target-dir ./workspace \
  --auth-token $GITHUB_TOKEN
```

**Expected Flow:**
1. Validate authentication token
2. Configure git credentials temporarily
3. Clone repository
4. Clear credentials after operation

### 3. Two-Factor Authentication
**Scenario:** Repository requires 2FA

**Expected Interaction:**
```
Authenticating with GitHub...
✓ Username accepted
⚠ Two-factor authentication required

Enter 2FA code: ******
✓ Authentication successful
Proceeding with clone operation...
```

## Advanced Operations

### 1. Shallow Clone
**Goal:** Clone only recent history for faster operation

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/large/monorepo.git \
  --branch main \
  --target-dir ./workspace \
  --depth 10
```

**Expected Behavior:**
- Clone only last 10 commits
- Faster clone for large repositories
- Display warning about limited history

### 2. Clone Specific Commit
**Goal:** Clone and checkout a specific commit

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/project.git \
  --commit abc123def456 \
  --target-dir ./workspace
```

**Expected Flow:**
1. Clone repository
2. Checkout specific commit (detached HEAD)
3. Display warning about detached HEAD state

### 3. Clone with Submodules
**Goal:** Clone repository including all submodules

**Command:**
```bash
git-history-rewriter clone \
  --repo-url https://github.com/user/project-with-submodules.git \
  --branch main \
  --target-dir ./workspace \
  --recurse-submodules
```

**Expected Output:**
```
✓ Repository cloned successfully
✓ Initializing submodules...
  - vendor/library1 (v1.2.3)
  - vendor/library2 (v2.0.1)
✓ All submodules initialized
```

## Future Features

### 1. History Rewriting Preparation
**Goal:** Clone and prepare for history rewriting with context

**Command:**
```bash
git-history-rewriter prepare \
  --repo-url https://github.com/user/project.git \
  --initial-commit abc123 \
  --final-commit def456 \
  --conversation context.jsonl \
  --target-dir ./rewrite-workspace
```

**Expected Flow:**
1. Clone repository
2. Create working branch
3. Load conversation context
4. Analyze commit range
5. Display readiness status

### 2. Batch Clone Operations
**Goal:** Clone multiple repositories from a configuration file

**Config File (repos.yaml):**
```yaml
repositories:
  - url: https://github.com/org/service1.git
    branch: main
    target: ./services/service1
  - url: https://github.com/org/service2.git
    branch: develop
    target: ./services/service2
```

**Command:**
```bash
git-history-rewriter clone-batch --config repos.yaml
```

### 3. Interactive Mode
**Goal:** Guide users through clone process interactively

**Command:**
```bash
git-history-rewriter clone --interactive
```

**Expected Interaction:**
```
Git History Rewriter - Interactive Clone

Repository URL: https://github.com/user/project.git
✓ Valid repository URL

Available branches:
1. main (default)
2. develop
3. feature/new-ui

Select branch [1-3]: 2

Target directory [./project]: ./my-workspace/project
✓ Directory will be created

Additional options:
- Include submodules? [y/N]: n
- Shallow clone (faster)? [y/N]: y
  Depth [10]: 20

Ready to clone? [Y/n]: y

Cloning...
✓ Clone completed successfully
```

## Testing Scenarios

### Unit Test Coverage
Each user flow should have corresponding unit tests:

1. **Valid Input Tests**
   - Various URL formats (HTTPS, SSH, with/without .git)
   - Different branch name formats
   - Path normalization

2. **Error Handling Tests**
   - Invalid URLs
   - Non-existent branches
   - Network failures (mocked)
   - Permission issues

3. **Integration Tests**
   - Clone public repository (using test repo)
   - Branch checkout verification
   - Directory creation and cleanup

### Performance Benchmarks
- Small repository (<10MB): < 5 seconds
- Medium repository (10-100MB): < 30 seconds
- Large repository (>100MB): Progress indication required

## CLI Help Documentation

### Main Help
```bash
$ git-history-rewriter --help

Usage: git-history-rewriter [OPTIONS] COMMAND [ARGS]...

  AI-powered git history rewriting tool

Options:
  --version  Show version
  --help     Show this message and exit

Commands:
  clone     Clone a repository and checkout a branch
  rewrite   Rewrite git history using AI assistance
  prepare   Prepare repository for history rewriting
```

### Clone Command Help
```bash
$ git-history-rewriter clone --help

Usage: git-history-rewriter clone [OPTIONS]

  Clone a repository and checkout a specific branch

Options:
  --repo-url TEXT       Repository URL (HTTPS or SSH)  [required]
  --branch TEXT         Branch to checkout  [required]
  --target-dir TEXT     Target directory for clone  [required]
  --verbose            Enable verbose output
  --depth INTEGER      Create shallow clone with specified depth
  --auth-token TEXT    Authentication token for private repos
  --recurse-submodules Include submodules in clone
  --help              Show this message and exit

Examples:
  git-history-rewriter clone --repo-url https://github.com/user/repo.git --branch main --target-dir ./workspace
  git-history-rewriter clone --repo-url git@github.com:user/repo.git --branch develop --target-dir /tmp/repo --verbose
```

## Success Metrics

1. **Reliability**
   - 99% success rate for valid public repositories
   - Clear error messages for all failure scenarios
   - Graceful handling of interruptions (Ctrl+C)

2. **Performance**
   - Clone operation starts within 1 second
   - Progress indication for operations > 5 seconds
   - Efficient memory usage for large repositories

3. **Usability**
   - Intuitive command structure
   - Helpful error messages with solutions
   - Consistent output format

4. **Compatibility**
   - Works with GitHub, GitLab, Bitbucket
   - Supports both HTTPS and SSH protocols
   - Cross-platform (Linux, macOS, Windows)