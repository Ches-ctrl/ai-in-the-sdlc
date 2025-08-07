#!/usr/bin/env python3
"""
Enhanced Git Hunk Classifier

Extends the base hunk classifier to handle ambiguous hunks by detecting and splitting them
into smaller, more focused hunks before classification.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib
from datetime import datetime

from hunk_classifier import GitHunkClassifier, HunkClassification
from hunk_splitter import HunkSplitter


class AmbiguousHunkDetection:
    """Structured output for ambiguous hunk detection"""
    def __init__(self, is_ambiguous: bool, reason: str, confidence: float = 0.0):
        self.is_ambiguous = is_ambiguous
        self.reason = reason
        self.confidence = confidence


class EnhancedGitHunkClassifier(GitHunkClassifier):
    """Enhanced classifier that handles ambiguous hunks"""

    def __init__(self, api_key: Optional[str] = None, enable_splitting: bool = True):
        """Initialize the enhanced classifier"""
        super().__init__(api_key)
        self.enable_splitting = enable_splitting
        self.splitter = HunkSplitter() if enable_splitting else None
        self.processing_log = []

        # Track processing state for idempotency
        self.state_file = Path.home() / '.cache' / 'hunk_classifier' / 'processing_state.json'
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.processing_state = self._load_state()

    def _load_state(self) -> Dict:
        """Load processing state for idempotency"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_state(self):
        """Save processing state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.processing_state, f, indent=2)

    def _get_file_state_key(self, file_path: str) -> str:
        """Generate a state key for a file"""
        file_path = Path(file_path).resolve()
        # Include file modification time in the key for change detection
        try:
            mtime = file_path.stat().st_mtime
            content_hash = hashlib.sha256(f"{file_path}:{mtime}".encode()).hexdigest()[:16]
            return f"{file_path.name}_{content_hash}"
        except:
            return hashlib.sha256(str(file_path).encode()).hexdigest()[:16]

    def _is_already_processed(self, file_path: str) -> bool:
        """Check if a file has already been processed"""
        state_key = self._get_file_state_key(file_path)
        if state_key in self.processing_state:
            state = self.processing_state[state_key]
            # Check if the file was successfully processed
            return state.get('status') == 'completed'
        return False

    def _mark_as_processed(self, file_path: str, result: Dict):
        """Mark a file as processed"""
        state_key = self._get_file_state_key(file_path)
        self.processing_state[state_key] = {
            'status': 'completed' if result.get('status') == 'success' else 'failed',
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_hunks': result.get('total_hunks', 0),
                'split_hunks': result.get('split_hunks_count', 0),
                'feature1_count': result.get('feature1_count', 0),
                'feature2_count': result.get('feature2_count', 0)
            }
        }
        self._save_state()

    def detect_and_split_ambiguous_hunks(self, hunks: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        Detect ambiguous hunks and split them if necessary

        Returns:
            Tuple of (processed_hunks, split_info)
        """
        processed_hunks = []
        split_info = {
            'total_original': len(hunks),
            'ambiguous_count': 0,
            'split_count': 0,
            'split_details': []
        }

        for hunk in hunks:
            # Detect if hunk is ambiguous
            is_ambiguous, reason = self.splitter.detect_ambiguous_hunk(hunk)

            if is_ambiguous and self.enable_splitting:
                self.processing_log.append({
                    'action': 'ambiguous_detected',
                    'hunk_index': hunk['index'],
                    'reason': reason
                })

                # Split the ambiguous hunk
                mini_hunks = self.splitter.split_hunk_interactive(hunk, '')

                if len(mini_hunks) > 1:
                    split_info['ambiguous_count'] += 1
                    split_info['split_count'] += len(mini_hunks)
                    split_info['split_details'].append({
                        'original_index': hunk['index'],
                        'split_into': len(mini_hunks),
                        'reason': reason
                    })

                    # Re-index mini-hunks to maintain unique indices
                    base_index = len(processed_hunks)
                    for i, mini_hunk in enumerate(mini_hunks):
                        mini_hunk['index'] = base_index + i
                        mini_hunk['is_split'] = True
                        mini_hunk['parent_index'] = hunk['index']
                        processed_hunks.append(mini_hunk)

                    self.processing_log.append({
                        'action': 'hunk_split',
                        'original_index': hunk['index'],
                        'split_count': len(mini_hunks)
                    })
                else:
                    # Splitting didn't produce multiple hunks, use original
                    hunk['is_split'] = False
                    processed_hunks.append(hunk)
            else:
                # Not ambiguous or splitting disabled
                hunk['is_split'] = False
                processed_hunks.append(hunk)

        split_info['total_processed'] = len(processed_hunks)
        return processed_hunks, split_info

    def classify_hunks_with_context(self, hunks: List[Dict], feature1_desc: str,
                                   feature2_desc: str) -> List[HunkClassification]:
        """
        Classify hunks with additional context about split hunks
        """
        classifications = []

        for hunk in hunks:
            # Add context about whether this is a split hunk
            context = ""
            if hunk.get('is_split'):
                context = f" (This is a mini-hunk split from a larger ambiguous hunk)"

            # Classify the hunk
            classification = self.classify_hunk(hunk, feature1_desc + context, feature2_desc)

            # Add metadata about splitting
            classification_dict = classification.model_dump()
            classification_dict['is_split'] = hunk.get('is_split', False)
            if hunk.get('parent_index') is not None:
                classification_dict['parent_index'] = hunk['parent_index']

            classifications.append(classification)

            self.processing_log.append({
                'action': 'classified',
                'hunk_index': hunk['index'],
                'feature': classification.feature,
                'is_split': hunk.get('is_split', False)
            })

        return classifications

    def apply_hunks_with_partial_commits(self, hunks: List[Dict],
                                        classifications: List[HunkClassification],
                                        file_path: str, feature: str,
                                        commit_message: str) -> Dict:
        """
        Enhanced commit logic that handles partial commits from split hunks
        """
        # Group hunks by parent (for split hunks)
        hunk_groups = {}
        for i, hunk in enumerate(hunks):
            if hunk.get('is_split') and hunk.get('parent_index') is not None:
                parent = hunk['parent_index']
                if parent not in hunk_groups:
                    hunk_groups[parent] = []
                hunk_groups[parent].append(i)
            else:
                # Non-split hunks are their own group
                hunk_groups[hunk['index']] = [i]

        # Collect hunks for this feature
        feature_hunks = []
        partial_commits = []

        for c in classifications:
            if c.feature == feature and c.hunk_index < len(hunks):
                hunk = hunks[c.hunk_index]
                feature_hunks.append(hunk)

                # Track if this is part of a partial commit
                if hunk.get('is_split'):
                    parent = hunk.get('parent_index')
                    if parent is not None:
                        # Check if all mini-hunks from this parent are for the same feature
                        sibling_indices = hunk_groups.get(parent, [])
                        sibling_features = [
                            classifications[idx].feature
                            for idx in sibling_indices
                            if idx < len(classifications)
                        ]
                        if not all(f == feature for f in sibling_features):
                            partial_commits.append({
                                'parent_index': parent,
                                'feature_hunks': sum(1 for f in sibling_features if f == feature),
                                'total_hunks': len(sibling_features)
                            })

        if not feature_hunks:
            return {
                'success': False,
                'message': f"No hunks classified for {feature}"
            }

        # Apply the hunks
        success = self.apply_hunks_and_commit(
            feature_hunks,
            [c for c in classifications if c.feature == feature],
            file_path,
            feature,
            commit_message
        )

        result = {
            'success': success,
            'feature': feature,
            'hunks_committed': len(feature_hunks),
            'partial_commits': partial_commits
        }

        if partial_commits:
            result['message'] = (
                f"Committed {len(feature_hunks)} hunks for {feature}, "
                f"including {len(partial_commits)} partial commits from split ambiguous hunks"
            )

        return result

    def process_file_enhanced(self, file_path: str, feature1_desc: str, feature2_desc: str,
                             feature1_commit_msg: Optional[str] = None,
                             feature2_commit_msg: Optional[str] = None,
                             force_reprocess: bool = False) -> Dict:
        """
        Enhanced file processing with ambiguous hunk detection and splitting
        """
        print(f"Enhanced processing for file: {file_path}")

        # Check if already processed (idempotency)
        if not force_reprocess and self._is_already_processed(file_path):
            print(f"File already processed. Use force_reprocess=True to reprocess.")
            return {
                'status': 'skipped',
                'message': 'File already processed',
                'file': file_path
            }

        # Clear processing log for new run
        self.processing_log = []

        # Extract hunks
        hunks = self.extract_hunks_from_file(file_path)
        if not hunks:
            return {
                'status': 'error',
                'message': 'No hunks found in file',
                'file': file_path
            }

        print(f"Found {len(hunks)} original hunks")

        # Detect and split ambiguous hunks
        processed_hunks, split_info = self.detect_and_split_ambiguous_hunks(hunks)

        print(f"Ambiguous hunks detected: {split_info['ambiguous_count']}")
        print(f"Total hunks after splitting: {split_info['total_processed']}")

        # Classify all hunks (including split ones)
        classifications = self.classify_hunks_with_context(
            processed_hunks,
            feature1_desc,
            feature2_desc
        )

        # Count classifications
        feature1_count = sum(1 for c in classifications if c.feature == 'feature1')
        feature2_count = sum(1 for c in classifications if c.feature == 'feature2')

        print(f"\nClassification Summary:")
        print(f"  Feature 1: {feature1_count} hunks")
        print(f"  Feature 2: {feature2_count} hunks")

        # Prepare result
        result = {
            'status': 'success',
            'file': file_path,
            'original_hunks': len(hunks),
            'processed_hunks': len(processed_hunks),
            'split_info': split_info,
            'classifications': [c.model_dump() for c in classifications],
            'feature1_count': feature1_count,
            'feature2_count': feature2_count,
            'processing_log': self.processing_log
        }

        # Apply and commit feature1 hunks
        if feature1_count > 0:
            commit_msg = feature1_commit_msg or f"Feature 1: {feature1_desc[:50]}"
            commit_result = self.apply_hunks_with_partial_commits(
                processed_hunks,
                classifications,
                file_path,
                'feature1',
                commit_msg
            )
            result['feature1_commit'] = commit_result

        # Generate patch for feature2 hunks
        if feature2_count > 0:
            feature2_hunks = [
                processed_hunks[c.hunk_index]
                for c in classifications
                if c.feature == 'feature2' and c.hunk_index < len(processed_hunks)
            ]

            feature2_patch = self._create_patch_from_hunks(feature2_hunks)
            result['feature2_patch'] = feature2_patch

            # Save patch to file
            patch_path = f"{file_path}.feature2.enhanced.patch"
            with open(patch_path, 'w') as f:
                f.write(feature2_patch)
            result['feature2_patch_file'] = patch_path
            print(f"\nFeature 2 patch saved to: {patch_path}")

        # Mark as processed for idempotency
        self._mark_as_processed(file_path, result)

        return result

    def clear_processing_state(self):
        """Clear all processing state (useful for testing)"""
        self.processing_state = {}
        self._save_state()
        if self.splitter:
            self.splitter.clear_cache()

    def _analyze_mixed_content(self, hunk: Dict, feature1_desc: str, feature2_desc: str) -> bool:
        """Check if a hunk likely contains both features (legacy method)"""
        content = hunk['content'].lower()

        # Quick heuristic check first
        feature1_keywords = set(feature1_desc.lower().split())
        feature2_keywords = set(feature2_desc.lower().split())

        # Look for explicit feature markers
        has_feature1_marker = any(marker in content for marker in ['feature 1', 'feature1', '# upload'])
        has_feature2_marker = any(marker in content for marker in ['feature 2', 'feature2', '# guideline', '# serve'])

        if has_feature1_marker and has_feature2_marker:
            return True

        # Check for multiple route definitions (common in Flask)
        route_count = content.count('@app.route')
        if route_count > 1:
            return True

        # Check for significant presence of both feature keywords
        feature1_matches = sum(1 for kw in feature1_keywords if kw in content)
        feature2_matches = sum(1 for kw in feature2_keywords if kw in content)

        # If both features have significant keyword matches, it's likely mixed
        if feature1_matches >= 2 and feature2_matches >= 2:
            return True

        # Check line count - very large hunks are more likely to be mixed
        line_count = len(hunk['content'].split('\n'))
        if line_count > 30:  # Arbitrary threshold
            return True

        return False


def compare_processing_methods(file_path: str, feature1_desc: str, feature2_desc: str):
    """Compare results with and without splitting"""

    print("\n" + "="*70)
    print("COMPARISON: Standard vs. Enhanced Processing")
    print("="*70)

    classifier = EnhancedGitHunkClassifier()

    # Process with enhanced splitting
    print("\n" + "="*70)
    print("ENHANCED PROCESSING (with splitting):")
    print("="*70)

    result = classifier.process_file_enhanced(
        file_path, feature1_desc, feature2_desc,
        "feat: Add upload functionality",
        "feat: Add guidelines endpoint"
    )

    print("\n" + "="*70)
    print("FINAL RESULT:")
    print("-"*40)
    print(json.dumps(result, indent=2))

    return result


def main():
    """CLI entry point for enhanced classifier"""
    if len(sys.argv) < 4:
        print("Usage: python enhanced_classifier.py <file_path> <feature1_desc> <feature2_desc> [options]")
        print("\nOptions:")
        print("  --feature1-commit <msg>  : Commit message for feature 1")
        print("  --feature2-commit <msg>  : Commit message for feature 2")
        print("  --no-split              : Disable ambiguous hunk splitting")
        print("  --force                 : Force reprocess even if already processed")
        print("  --clear-cache           : Clear all caches before processing")
        sys.exit(1)

    file_path = sys.argv[1]
    feature1_desc = sys.argv[2]
    feature2_desc = sys.argv[3]

    # Parse additional options
    feature1_commit = None
    feature2_commit = None
    enable_splitting = True
    force_reprocess = False
    clear_cache = False

    i = 4
    while i < len(sys.argv):
        if sys.argv[i] == '--feature1-commit' and i + 1 < len(sys.argv):
            feature1_commit = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--feature2-commit' and i + 1 < len(sys.argv):
            feature2_commit = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--no-split':
            enable_splitting = False
            i += 1
        elif sys.argv[i] == '--force':
            force_reprocess = True
            i += 1
        elif sys.argv[i] == '--clear-cache':
            clear_cache = True
            i += 1
        else:
            print(f"Unknown option: {sys.argv[i]}")
            i += 1

    try:
        classifier = EnhancedGitHunkClassifier(enable_splitting=enable_splitting)

        if clear_cache:
            print("Clearing all caches...")
            classifier.clear_processing_state()

        result = classifier.process_file_enhanced(
            file_path,
            feature1_desc,
            feature2_desc,
            feature1_commit,
            feature2_commit,
            force_reprocess=force_reprocess
        )

        # Output result as JSON
        print("\n" + "="*50)
        print("ENHANCED CLASSIFIER RESULT:")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
