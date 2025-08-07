# Known Issues

## 1. Truncated Output in `analyze` Command

**Issue:** The `analyze` command output appears truncated or incomplete when Claude performs the analysis.

**Symptoms:**
- Analysis starts but only shows partial output like "Let me examine the commits..." 
- The full analysis results are not displayed to the user
- Command completes successfully but useful information is missing

**Root Cause:** 
The `analyze_commits` method in `claude_agent.py` only collects `TextBlock` content from Claude's responses. When Claude uses tools (Bash, Read) to examine the repository, those tool interactions and their results are not being captured in the final output.

**Code Location:** 
- File: `src/git_history_rewriter/claude_agent.py`
- Method: `analyze_commits()` (lines ~392-420)

**Current Implementation:**
```python
async for message in query(prompt=prompt, options=options):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                analysis += block.text + "\n"  # Only captures text blocks
```

**Proposed Fix:**
1. Capture all message types including tool use and results
2. Format tool outputs appropriately for display
3. Build a complete analysis narrative including Claude's investigation steps

**Workaround:**
- Use the `--verbose` flag to see more details during execution
- Run the `rewrite` command with `--dry-run` for more detailed analysis

**Priority:** Medium - Feature works but UX could be improved

**Reported:** 2025-01-07

---

## Contributing

If you encounter other issues, please document them here following the same format.