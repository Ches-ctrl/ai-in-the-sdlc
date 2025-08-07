#!/usr/bin/env python3
"""
Git Hunk Splitter

Provides functionality to split ambiguous hunks into smaller, more focused hunks
using git's patch editing capabilities.
"""

import subprocess
import tempfile
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib
import json


class HunkSplitter:
    """Handles splitting of ambiguous git hunks"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the hunk splitter with optional cache directory"""
        self.cache_dir = cache_dir or Path.home() / '.cache' / 'hunk_classifier'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.split_cache_file = self.cache_dir / 'split_hunks.json'
        self.split_cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load the split hunks cache for idempotency"""
        if self.split_cache_file.exists():
            try:
                with open(self.split_cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        """Save the split hunks cache"""
        with open(self.split_cache_file, 'w') as f:
            json.dump(self.split_cache, f, indent=2)

    def _get_hunk_hash(self, hunk: Dict) -> str:
        """Generate a hash for a hunk to use as cache key"""
        content = f"{hunk['hunk_header']}\n{hunk['content']}"
        return hashlib.sha256(content.encode()).hexdigest()

    def detect_ambiguous_hunk(self, hunk: Dict, context: Optional[str] = None) -> Tuple[bool, str]:
        """
        Detect if a hunk is ambiguous (contains multiple logical changes)

        Returns:
            Tuple of (is_ambiguous, reason)
        """
        content = hunk['content']
        lines = content.split('\n')

        # Heuristics for detecting ambiguous hunks
        indicators = {
            'multiple_functions': False,
            'mixed_features': False,
            'large_hunk': False,
            'disconnected_changes': False,
            'multiple_logic_blocks': False
        }

        # 1. Check for multiple function definitions/modifications
        function_patterns = [
            r'^\+\s*def\s+\w+',  # Python
            r'^\+\s*function\s+\w+',  # JavaScript
            r'^\+\s*func\s+\w+',  # Go
            r'^\+\s*public\s+\w+.*\(',  # Java/C#
            r'^\+\s*private\s+\w+.*\(',  # Java/C#
        ]

        function_count = 0
        for line in lines:
            for pattern in function_patterns:
                if re.match(pattern, line):
                    function_count += 1
                    break

        if function_count > 1:
            indicators['multiple_functions'] = True

        # 2. Check for large hunks (more than 50 lines of actual changes)
        change_lines = [l for l in lines if l.startswith('+') or l.startswith('-')]
        if len(change_lines) > 50:
            indicators['large_hunk'] = True

        # 3. Check for disconnected changes (gaps of unchanged code)
        gap_size = 0
        max_gap = 0
        has_changes_before = False
        has_changes_after = False

        for i, line in enumerate(lines):
            if line.startswith('+') or line.startswith('-'):
                if gap_size > 0:
                    has_changes_after = True
                    max_gap = max(max_gap, gap_size)
                gap_size = 0
                has_changes_before = True
            elif line.startswith(' '):
                if has_changes_before:
                    gap_size += 1

        if max_gap > 10 and has_changes_after:
            indicators['disconnected_changes'] = True

        # 4. Check for multiple distinct logic blocks
        # Look for multiple if/for/while/try blocks being added
        logic_patterns = [
            r'^\+\s*(if|for|while|try|switch|case)\s*[\(\{]',
            r'^\+\s*}?\s*else\s*(if)?\s*[\(\{]',
        ]

        logic_blocks = 0
        for line in lines:
            for pattern in logic_patterns:
                if re.match(pattern, line):
                    logic_blocks += 1
                    break

        if logic_blocks > 2:
            indicators['multiple_logic_blocks'] = True

        # 5. Check for mixed import/include statements with logic
        import_count = 0
        logic_count = 0
        for line in lines:
            if line.startswith('+'):
                if re.match(r'^\+\s*(import|from|include|require|use)\s+', line):
                    import_count += 1
                elif re.match(r'^\+\s*(def|function|class|if|for|while)', line):
                    logic_count += 1

        if import_count > 0 and logic_count > 0:
            indicators['mixed_features'] = True

        # Determine if hunk is ambiguous
        is_ambiguous = sum(indicators.values()) >= 2

        # Generate reason
        active_indicators = [k for k, v in indicators.items() if v]
        if active_indicators:
            reason = f"Hunk appears ambiguous due to: {', '.join(active_indicators)}"
        else:
            reason = "Hunk appears to be focused on a single logical change"

        return is_ambiguous, reason

    def split_hunk_interactive(self, hunk: Dict, file_path: str) -> List[Dict]:
        """
        Split a hunk interactively using git add -p simulation

        Returns a list of mini-hunks
        """
        # Check cache first
        hunk_hash = self._get_hunk_hash(hunk)
        if hunk_hash in self.split_cache:
            cached_splits = self.split_cache[hunk_hash]
            return self._reconstruct_hunks_from_cache(cached_splits, hunk)

        # If not in cache, perform the split
        mini_hunks = self._perform_hunk_split(hunk)

        # Cache the result
        self.split_cache[hunk_hash] = self._prepare_hunks_for_cache(mini_hunks)
        self._save_cache()

        return mini_hunks

    def _perform_hunk_split(self, hunk: Dict) -> List[Dict]:
        """
        Perform the actual hunk splitting logic

        This simulates git add -p behavior by analyzing the hunk
        and creating logical splits
        """
        content = hunk['content']
        lines = content.split('\n')

        mini_hunks = []
        current_mini = []

        # Track the line numbers for proper hunk headers
        original_start = self._parse_hunk_header(hunk['hunk_header'])
        current_old_line = original_start[0]
        current_new_line = original_start[1]
        mini_old_start = current_old_line
        mini_new_start = current_new_line

        def create_mini_hunk():
            nonlocal current_mini, mini_old_start, mini_new_start, current_old_line, current_new_line
            if not current_mini:
                return

            # Calculate line counts
            old_count = sum(1 for l in current_mini if not l.startswith('+'))
            new_count = sum(1 for l in current_mini if not l.startswith('-'))

            # Create hunk header
            mini_header = f"@@ -{mini_old_start},{old_count} +{mini_new_start},{new_count} @@"

            mini_hunks.append({
                'index': len(mini_hunks),
                'header': hunk['header'],
                'hunk_header': mini_header,
                'content': '\n'.join(current_mini),
                'full_patch': f"{hunk['header']}\n{mini_header}\n" + '\n'.join(current_mini),
                'parent_hunk_hash': self._get_hunk_hash(hunk)
            })

            current_mini = []
            mini_old_start = current_old_line
            mini_new_start = current_new_line

        # Analyze lines and split at logical boundaries
        for i, line in enumerate(lines):
            # Update line counters
            if line.startswith('-'):
                current_old_line += 1
            elif line.startswith('+'):
                current_new_line += 1
            elif line.startswith(' '):
                current_old_line += 1
                current_new_line += 1

            # Detect split points
            should_split = False

            # Split before new function/class definitions
            if i > 0 and re.match(r'^\+\s*(def|class|function|func|public|private)\s+', line):
                should_split = True

            # Split after complete logical blocks (look ahead for blank lines or new blocks)
            if i < len(lines) - 1:
                next_line = lines[i + 1]
                if line.startswith('+') and next_line.startswith(' ') and not next_line.strip():
                    # Blank context line after addition
                    if i < len(lines) - 2:
                        line_after_blank = lines[i + 2]
                        if line_after_blank.startswith('+'):
                            should_split = True

            # Split if we have accumulated enough changes (>20 lines)
            if len(current_mini) > 20 and line.startswith(' '):
                should_split = True

            if should_split and current_mini:
                create_mini_hunk()

            current_mini.append(line)

        # Don't forget the last mini-hunk
        create_mini_hunk()

        # If no meaningful splits were created, return the original hunk
        if len(mini_hunks) <= 1:
            return [{
                'index': 0,
                'header': hunk['header'],
                'hunk_header': hunk['hunk_header'],
                'content': hunk['content'],
                'full_patch': hunk['full_patch'],
                'parent_hunk_hash': self._get_hunk_hash(hunk)
            }]

        return mini_hunks

    def _parse_hunk_header(self, header: str) -> Tuple[int, int, int, int]:
        """Parse hunk header to extract line numbers"""
        # Format: @@ -old_start,old_count +new_start,new_count @@
        match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', header)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) else 1
            return old_start, new_start, old_count, new_count
        return 1, 1, 0, 0

    def _prepare_hunks_for_cache(self, hunks: List[Dict]) -> List[Dict]:
        """Prepare hunks for caching (remove non-serializable data)"""
        cached_hunks = []
        for hunk in hunks:
            cached_hunks.append({
                'hunk_header': hunk['hunk_header'],
                'content': hunk['content']
            })
        return cached_hunks

    def _reconstruct_hunks_from_cache(self, cached_hunks: List[Dict], original_hunk: Dict) -> List[Dict]:
        """Reconstruct full hunk objects from cached data"""
        reconstructed = []
        for i, cached in enumerate(cached_hunks):
            reconstructed.append({
                'index': i,
                'header': original_hunk['header'],
                'hunk_header': cached['hunk_header'],
                'content': cached['content'],
                'full_patch': f"{original_hunk['header']}\n{cached['hunk_header']}\n{cached['content']}",
                'parent_hunk_hash': self._get_hunk_hash(original_hunk)
            })
        return reconstructed

    def clear_cache(self):
        """Clear the split hunks cache"""
        self.split_cache = {}
        if self.split_cache_file.exists():
            self.split_cache_file.unlink()
