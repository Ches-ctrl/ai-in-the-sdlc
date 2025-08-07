# Fixed Issues

This document tracks issues that have been resolved for historical reference.

## 1. Apply-Plan Command Shell Execution Issue

**Issue:** The `apply-plan` command was executing plan commands as literal shell commands instead of intelligently handling git operations.

**Symptoms:**
- Plans containing comment lines (starting with #) were executed as shell commands
- Interactive rebase instructions were not properly handled
- History was not actually rewritten despite "successful" execution
- Commands like `# pick abc123` did nothing when executed

**Root Cause:**
The original implementation used `subprocess.run()` to execute each command in the plan literally. This approach couldn't handle:
- Interactive rebase operations that require editor interaction
- Comment lines that are instructions for manual execution
- Complex git operations that need intelligent decision-making

**Original Implementation:**
```python
for i, command in enumerate(rewrite_plan.commands):
    result = subprocess.run(
        command,
        shell=True,
        cwd=repo,
        capture_output=True,
        text=True
    )
```

**Fix Applied:**
- **Date:** 2025-08-07
- **Solution:** Modified `apply_plan` to use Claude AI agent via `ClaudeHistoryRewriter.apply_saved_plan()`
- **Benefits:**
  - Agent now intelligently interprets and executes plan operations
  - Handles interactive rebase programmatically using custom editor scripts
  - Properly implements squash, reword, drop, and reorder operations
  - Adapts to unexpected situations during execution

**Files Modified:**
- `src/git_history_rewriter/claude_agent.py` - Added `apply_saved_plan()` method
- `src/git_history_rewriter/cli.py` - Modified `apply_plan()` function

**Status:** ✅ FIXED

---

## 2. Operation Field Mapping Error

**Issue:** Plan generation failed due to field name mismatches between Claude's response and the Operation dataclass.

**Symptoms:**
- `TypeError: Operation.__init__() got an unexpected keyword argument 'message'`
- Plan generation would fail when Claude returned operations

**Root Cause:**
Claude was returning operations with a `message` field, but the Operation dataclass expected `new_message` or `old_message`.

**Fix Applied:**
- **Date:** 2025-08-07
- **Solution:** Added flexible field mapping in `cli.py` to handle variations in field names
- **Location:** `src/git_history_rewriter/cli.py` lines 526-561

**Status:** ✅ FIXED