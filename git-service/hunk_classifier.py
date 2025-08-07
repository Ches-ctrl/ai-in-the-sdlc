#!/usr/bin/env python3
"""
Git Hunk Classifier and Committer

Classifies git hunks from a single file into two feature branches using OpenAI's structured output.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re
import os
from openai import OpenAI
from pydantic import BaseModel, Field


class HunkClassification(BaseModel):
    """Structured output model for hunk classification"""
    hunk_index: int = Field(description="Index of the hunk being classified")
    feature: str = Field(description="Either 'feature1' or 'feature2'")
    reasoning: str = Field(description="Explanation for the classification decision")


class GitHunkClassifier:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the classifier with OpenAI API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=self.api_key)

    def extract_hunks_from_file(self, file_path: str) -> List[Dict[str, any]]:
        """Extract hunks from a staged file using git diff"""
        try:
            # Determine the git repository directory
            file_path = Path(file_path).resolve()
            repo_dir = file_path.parent

            # Get the staged diff for the file
            result = subprocess.run(
                ["git", "-C", str(repo_dir), "diff", "--cached", "--no-color", "--no-ext-diff", file_path.name],
                capture_output=True,
                text=True,
                check=True
            )

            if not result.stdout:
                print(f"No staged changes found for {file_path}")
                return []

            # Parse the diff output to extract individual hunks
            hunks = self._parse_diff_into_hunks(result.stdout)
            return hunks

        except subprocess.CalledProcessError as e:
            print(f"Error extracting hunks: {e}")
            return []

    def _parse_diff_into_hunks(self, diff_output: str) -> List[Dict[str, any]]:
        """Parse git diff output into individual hunks"""
        hunks = []
        lines = diff_output.split('\n')

        # Find the header end
        header_end = 0
        for i, line in enumerate(lines):
            if line.startswith('@@'):
                header_end = i
                break

        # Extract file header
        file_header = '\n'.join(lines[:header_end])

        # Split by hunk headers (@@)
        current_hunk = []
        hunk_header = None
        hunk_index = 0

        for line in lines[header_end:]:
            if line.startswith('@@'):
                # Save previous hunk if exists
                if current_hunk and hunk_header:
                    hunks.append({
                        'index': hunk_index,
                        'header': file_header,
                        'hunk_header': hunk_header,
                        'content': '\n'.join(current_hunk),
                        'full_patch': file_header + '\n' + hunk_header + '\n' + '\n'.join(current_hunk)
                    })
                    hunk_index += 1

                # Start new hunk
                hunk_header = line
                current_hunk = []
            else:
                current_hunk.append(line)

        # Don't forget the last hunk
        if current_hunk and hunk_header:
            hunks.append({
                'index': hunk_index,
                'header': file_header,
                'hunk_header': hunk_header,
                'content': '\n'.join(current_hunk),
                'full_patch': file_header + '\n' + hunk_header + '\n' + '\n'.join(current_hunk)
            })

        return hunks

    def classify_hunk(self, hunk: Dict, feature1_desc: str, feature2_desc: str) -> HunkClassification:
        """Classify a single hunk using OpenAI API with structured output"""

        prompt = f"""Classify this git hunk into one of two features.

Feature 1: {feature1_desc}
Feature 2: {feature2_desc}

Git Hunk:
```
{hunk['hunk_header']}
{hunk['content']}
```

Analyze the code changes and determine which feature this hunk belongs to."""

        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a code analyzer that classifies git hunks into features based on their content and purpose."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format=HunkClassification,
                temperature=0.1  # Low temperature for consistent classification
            )

            classification = response.choices[0].message.parsed
            # Ensure hunk_index matches the actual index from the hunk
            classification.hunk_index = hunk['index']
            # Ensure feature value is exactly 'feature1' or 'feature2'
            if classification.feature.lower() in ['feature1', 'feature 1', '1']:
                classification.feature = 'feature1'
            elif classification.feature.lower() in ['feature2', 'feature 2', '2']:
                classification.feature = 'feature2'

            return classification

        except Exception as e:
            print(f"Error classifying hunk {hunk['index']}: {e}")
            # Default to feature1 if classification fails
            return HunkClassification(
                hunk_index=hunk['index'],
                feature='feature1',
                reasoning=f"Classification failed: {str(e)}"
            )

    def apply_hunks_and_commit(self, hunks: List[Dict], classifications: List[HunkClassification],
                              file_path: str, feature: str, commit_message: str) -> bool:
        """Apply hunks for a specific feature and commit them"""

        # Filter hunks for this feature
        feature_hunks = [
            hunks[c.hunk_index]
            for c in classifications
            if c.feature == feature and c.hunk_index < len(hunks)
        ]

        if not feature_hunks:
            print(f"No hunks classified for {feature}")
            return False

        try:
            # Determine the git repository directory
            file_path_obj = Path(file_path).resolve()
            repo_dir = file_path_obj.parent

            # First, unstage the file
            subprocess.run(["git", "-C", str(repo_dir), "reset", "HEAD", file_path_obj.name], check=True, capture_output=True)

            # Create a patch with only the hunks for this feature
            patch_content = self._create_patch_from_hunks(feature_hunks)

            # Apply the patch
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
                patch_file.write(patch_content)
                patch_file_path = patch_file.name

            # Apply the patch to the working directory
            result = subprocess.run(
                ["git", "-C", str(repo_dir), "apply", "--cached", patch_file_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"Error applying patch: {result.stderr}")
                return False

            # Commit the changes
            subprocess.run(
                ["git", "-C", str(repo_dir), "commit", "-m", commit_message],
                check=True,
                capture_output=True
            )

            print(f"Successfully committed {len(feature_hunks)} hunks for {feature}")

            # Clean up
            Path(patch_file_path).unlink()

            return True

        except subprocess.CalledProcessError as e:
            print(f"Error during git operations: {e}")
            return False

    def _create_patch_from_hunks(self, hunks: List[Dict]) -> str:
        """Create a unified patch from selected hunks"""
        if not hunks:
            return ""

        # Use the header from the first hunk
        patch_lines = [hunks[0]['header']]

        # Add each hunk
        for hunk in hunks:
            patch_lines.append(hunk['hunk_header'])
            patch_lines.append(hunk['content'])

        return '\n'.join(patch_lines)

    def get_remaining_hunks_as_patch(self, hunks: List[Dict],
                                    classifications: List[HunkClassification],
                                    feature: str) -> str:
        """Get remaining hunks (for the other feature) as a patch"""

        # Filter hunks for this feature
        feature_hunks = [
            hunks[c.hunk_index]
            for c in classifications
            if c.feature == feature and c.hunk_index < len(hunks)
        ]

        if not feature_hunks:
            return ""

        return self._create_patch_from_hunks(feature_hunks)

    def process_file(self, file_path: str, feature1_desc: str, feature2_desc: str,
                    feature1_commit_msg: Optional[str] = None,
                    feature2_commit_msg: Optional[str] = None) -> Dict:
        """Main processing function to classify and commit hunks"""

        print(f"Processing file: {file_path}")

        # Extract hunks
        hunks = self.extract_hunks_from_file(file_path)
        if not hunks:
            return {
                'status': 'error',
                'message': 'No hunks found in file'
            }

        print(f"Found {len(hunks)} hunks to classify")

        # Classify each hunk
        classifications = []
        for hunk in hunks:
            print(f"Classifying hunk {hunk['index'] + 1}/{len(hunks)}...")
            classification = self.classify_hunk(hunk, feature1_desc, feature2_desc)
            classifications.append(classification)
            print(f"  -> Classified as {classification.feature}: {classification.reasoning[:100]}...")

        # Summary of classifications
        feature1_count = sum(1 for c in classifications if c.feature == 'feature1')
        feature2_count = sum(1 for c in classifications if c.feature == 'feature2')

        print(f"\nClassification Summary:")
        print(f"  Feature 1: {feature1_count} hunks")
        print(f"  Feature 2: {feature2_count} hunks")

        # Prepare result
        result = {
            'status': 'success',
            'file': file_path,
            'total_hunks': len(hunks),
            'classifications': [c.model_dump() for c in classifications],
            'feature1_count': feature1_count,
            'feature2_count': feature2_count
        }

        # Apply and commit feature1 hunks
        if feature1_count > 0:
            commit_msg = feature1_commit_msg or f"Feature 1: {feature1_desc[:50]}"
            success = self.apply_hunks_and_commit(hunks, classifications, file_path,
                                                 'feature1', commit_msg)
            result['feature1_committed'] = success

        # Generate patch for feature2 hunks
        if feature2_count > 0:
            feature2_patch = self.get_remaining_hunks_as_patch(hunks, classifications, 'feature2')
            result['feature2_patch'] = feature2_patch

            # Save patch to file
            patch_path = f"{file_path}.feature2.patch"
            with open(patch_path, 'w') as f:
                f.write(feature2_patch)
            result['feature2_patch_file'] = patch_path
            print(f"\nFeature 2 patch saved to: {patch_path}")
            print("Apply with: git apply --cached <patch_file>")

        return result


def main():
    """CLI entry point"""
    if len(sys.argv) < 4:
        print("Usage: python hunk_classifier.py <file_path> <feature1_desc> <feature2_desc> [feature1_commit_msg] [feature2_commit_msg]")
        sys.exit(1)

    file_path = sys.argv[1]
    feature1_desc = sys.argv[2]
    feature2_desc = sys.argv[3]
    feature1_commit = sys.argv[4] if len(sys.argv) > 4 else None
    feature2_commit = sys.argv[5] if len(sys.argv) > 5 else None

    try:
        classifier = GitHunkClassifier()
        result = classifier.process_file(
            file_path,
            feature1_desc,
            feature2_desc,
            feature1_commit,
            feature2_commit
        )

        # Output result as JSON
        print("\n" + "="*50)
        print("RESULT:")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
