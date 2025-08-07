#!/usr/bin/env python3
"""
Example usage of the Enhanced Git Hunk Classifier

This script demonstrates how to use both the basic and enhanced hunk classifier
with ambiguous hunk detection and splitting capabilities.
"""

import os
import subprocess
import tempfile
import json
from pathlib import Path
from hunk_classifier import GitHunkClassifier
from enhanced_classifier import EnhancedGitHunkClassifier


def create_test_file():
    """Create a test Python file with mixed changes for two features"""

    test_file = "test_example.py"

    # Initial content (simulate existing file)
    initial_content = '''class Calculator:
    def __init__(self):
        self.result = 0

    def add(self, x, y):
        return x + y

    def subtract(self, x, y):
        return x - y
'''

    # Modified content with changes for two features
    modified_content = '''import logging

class Calculator:
    def __init__(self):
        self.result = 0
        self.history = []  # Feature 1: Add history tracking
        logging.info("Calculator initialized")  # Feature 2: Add logging

    def add(self, x, y):
        result = x + y
        self.history.append(f"add({x}, {y}) = {result}")  # Feature 1: Track operation
        return result

    def subtract(self, x, y):
        result = x - y
        self.history.append(f"subtract({x}, {y}) = {result}")  # Feature 1: Track operation
        return result

    def multiply(self, x, y):
        """New multiplication method"""
        logging.debug(f"Multiplying {x} * {y}")  # Feature 2: Add logging
        return x * y

    def get_history(self):
        """Get calculation history"""  # Feature 1: History retrieval
        return self.history

    def clear_history(self):
        """Clear calculation history"""  # Feature 1: History management
        logging.info("Clearing history")  # Feature 2: Add logging
        self.history = []
'''

    # Create the file with initial content
    with open(test_file, 'w') as f:
        f.write(initial_content)

    # Initialize git repo if not exists
    if not Path('.git').exists():
        subprocess.run(['git', 'init'], capture_output=True)

    # Stage and commit initial version
    subprocess.run(['git', 'add', test_file], capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial calculator'], capture_output=True)

    # Write modified content
    with open(test_file, 'w') as f:
        f.write(modified_content)

    # Stage the changes
    subprocess.run(['git', 'add', test_file], capture_output=True)

    print(f"Test file '{test_file}' created and staged with mixed changes")
    return test_file


def create_ambiguous_test_file():
    """Create a test file with highly ambiguous hunks that mix multiple features"""

    test_file = "ambiguous_example.py"

    # Initial content
    initial_content = '''# Simple web application

def hello():
    return "Hello World"
'''

    # Modified content with very mixed features in single hunks
    modified_content = '''# Enhanced web application with file upload and content serving
import os
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def hello():
    return "Hello World"

# Feature 1: File upload functionality
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logger.warning("No file in upload request")  # Feature 2: Logging
        return jsonify({'error': 'No file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.info(f"File uploaded: {filename}")  # Feature 2: Logging
        return jsonify({'message': 'File uploaded', 'filename': filename})

# Feature 2: Content serving functionality
@app.route('/guidelines')
def get_guidelines():
    """Serve application guidelines"""
    logger.debug("Guidelines requested")  # Feature 2: Logging
    guidelines = {
        'upload_rules': ['Max 16MB', 'No executable files'],  # Feature 1: Upload info
        'api_usage': 'Use POST /upload for files',  # Feature 1: Upload info
        'support': 'Contact admin for help'
    }
    return jsonify(guidelines)

# Mixed utility function used by both features
def validate_file_type(filename):
    """Validate file type for uploads and content serving"""
    allowed_extensions = {'txt', 'pdf', 'png', 'jpg', 'gif'}  # Feature 1: Upload validation
    logger.debug(f"Validating file type: {filename}")  # Feature 2: Logging
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Feature 1: Upload status endpoint
@app.route('/upload/status')
def upload_status():
    upload_dir = app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_dir):
        files = os.listdir(upload_dir)
        logger.info(f"Status check: {len(files)} files")  # Feature 2: Logging
        return jsonify({'uploaded_files': files, 'count': len(files)})
    return jsonify({'uploaded_files': [], 'count': 0})

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    logger.info("Starting application")  # Feature 2: Logging
    app.run(debug=True)
'''

    # Create the file with initial content
    with open(test_file, 'w') as f:
        f.write(initial_content)

    # Initialize git repo if not exists
    if not Path('.git').exists():
        subprocess.run(['git', 'init'], capture_output=True)

    # Stage and commit initial version
    subprocess.run(['git', 'add', test_file], capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial web app'], capture_output=True)

    # Write modified content
    with open(test_file, 'w') as f:
        f.write(modified_content)

    # Stage the changes
    subprocess.run(['git', 'add', test_file], capture_output=True)

    print(f"Ambiguous test file '{test_file}' created with highly mixed features")
    return test_file


def run_basic_example():
    """Run the basic classifier example"""

    print("="*60)
    print("BASIC GIT HUNK CLASSIFIER EXAMPLE")
    print("="*60)

    # Create test file
    test_file = create_test_file()

    # Show the diff
    print("\nStaged changes:")
    print("-"*40)
    diff_result = subprocess.run(['git', 'diff', '--cached', test_file],
                                capture_output=True, text=True)
    print(diff_result.stdout)

    # Feature descriptions
    feature1_desc = "Add history tracking functionality to track all calculations"
    feature2_desc = "Add logging capabilities for debugging and monitoring"

    print("\nFeature Descriptions:")
    print(f"Feature 1: {feature1_desc}")
    print(f"Feature 2: {feature2_desc}")
    print("\n" + "="*60)

    # Run the classifier
    try:
        classifier = GitHunkClassifier()
        result = classifier.process_file(
            test_file,
            feature1_desc,
            feature2_desc,
            "feat: Add calculation history tracking",
            "feat: Add logging support"
        )

        print("\n" + "="*60)
        print("CLASSIFICATION RESULTS:")
        print("-"*40)

        for classification in result['classifications']:
            print(f"\nHunk {classification['hunk_index']}:")
            print(f"  Feature: {classification['feature']}")
            print(f"  Reasoning: {classification['reasoning']}")

        print("\n" + "="*60)
        print("SUMMARY:")
        print(f"  Total hunks: {result['total_hunks']}")
        print(f"  Feature 1 hunks: {result['feature1_count']}")
        print(f"  Feature 2 hunks: {result['feature2_count']}")

        if result.get('feature1_committed'):
            print(f"\n✓ Feature 1 changes committed successfully")

        if result.get('feature2_patch_file'):
            print(f"\n✓ Feature 2 patch saved to: {result['feature2_patch_file']}")

        return result

    except Exception as e:
        print(f"\nError running basic classifier: {e}")
        return None


def run_enhanced_example():
    """Run the enhanced classifier example with ambiguous hunk detection"""

    print("\n" + "="*70)
    print("ENHANCED HUNK CLASSIFIER EXAMPLE (with splitting)")
    print("="*70)

    # Create ambiguous test file
    test_file = create_ambiguous_test_file()

    # Show the diff stats
    print("\nStaged changes summary:")
    print("-"*40)
    stat_result = subprocess.run(['git', 'diff', '--cached', '--stat', test_file],
                                capture_output=True, text=True)
    print(stat_result.stdout)

    # Feature descriptions for the web app
    feature1_desc = "File upload functionality allowing users to upload and manage files"
    feature2_desc = "Logging and monitoring capabilities for debugging and tracking"

    print("\nFeature Descriptions:")
    print(f"Feature 1: {feature1_desc}")
    print(f"Feature 2: {feature2_desc}")
    print("\n" + "="*70)

    # Run the enhanced classifier
    try:
        enhanced_classifier = EnhancedGitHunkClassifier(enable_splitting=True)

        result = enhanced_classifier.process_file_enhanced(
            test_file,
            feature1_desc,
            feature2_desc,
            "feat: Add file upload functionality",
            "feat: Add logging and monitoring",
            force_reprocess=True  # Force reprocess for demo
        )

        print("\n" + "="*70)
        print("ENHANCED CLASSIFICATION RESULTS:")
        print("-"*40)

        # Show split information
        if result['split_info']['ambiguous_count'] > 0:
            print(f"\n🔍 AMBIGUOUS HUNK DETECTION:")
            print(f"  Detected {result['split_info']['ambiguous_count']} ambiguous hunk(s)")
            print(f"  Split into {result['split_info']['split_count']} mini-hunks")

            for detail in result['split_info']['split_details']:
                print(f"  - Hunk {detail['original_index']} split into {detail['split_into']} pieces")
                print(f"    Reason: {detail['reason']}")

        print(f"\n📊 PROCESSING SUMMARY:")
        print(f"  Original hunks: {result['original_hunks']}")
        print(f"  Processed hunks: {result['processed_hunks']}")
        print(f"  Feature 1 hunks: {result['feature1_count']}")
        print(f"  Feature 2 hunks: {result['feature2_count']}")

        # Show some classification details
        print(f"\n🏷️  CLASSIFICATION DETAILS:")
        for i, classification in enumerate(result['classifications'][:5]):  # Show first 5
            split_indicator = " (split)" if classification.get('is_split') else ""
            print(f"  Hunk {classification['hunk_index']}{split_indicator}: {classification['feature']}")
            print(f"    → {classification['reasoning'][:80]}...")

        if len(result['classifications']) > 5:
            print(f"  ... and {len(result['classifications']) - 5} more hunks")

        # Show commit results
        if result.get('feature1_commit', {}).get('success'):
            print(f"\n✅ Feature 1 committed: {result['feature1_commit']['hunks_committed']} hunks")
            if result['feature1_commit'].get('partial_commits'):
                print(f"   Including {len(result['feature1_commit']['partial_commits'])} partial commits")

        if result.get('feature2_patch_file'):
            print(f"\n📄 Feature 2 patch saved to: {result['feature2_patch_file']}")

        return result

    except Exception as e:
        print(f"\nError running enhanced classifier: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_comparison():
    """Run both classifiers and compare results"""

    print("\n" + "="*80)
    print("COMPARISON: Basic vs Enhanced Classifier")
    print("="*80)

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\nERROR: Please set OPENAI_API_KEY environment variable")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return

    try:
        # Run basic example
        basic_result = run_basic_example()

        # Run enhanced example
        enhanced_result = run_enhanced_example()

        if basic_result and enhanced_result:
            print("\n" + "="*80)
            print("COMPARISON SUMMARY")
            print("="*80)
            print(f"Basic Classifier:")
            print(f"  - Processed: {basic_result['total_hunks']} hunks")
            print(f"  - Feature 1: {basic_result['feature1_count']} hunks")
            print(f"  - Feature 2: {basic_result['feature2_count']} hunks")

            print(f"\nEnhanced Classifier:")
            print(f"  - Original: {enhanced_result['original_hunks']} hunks")
            print(f"  - Processed: {enhanced_result['processed_hunks']} hunks")
            print(f"  - Ambiguous detected: {enhanced_result['split_info']['ambiguous_count']}")
            print(f"  - Feature 1: {enhanced_result['feature1_count']} hunks")
            print(f"  - Feature 2: {enhanced_result['feature2_count']} hunks")

            efficiency_gain = enhanced_result['processed_hunks'] - enhanced_result['original_hunks']
            if efficiency_gain > 0:
                print(f"\n🎯 Enhanced classifier created {efficiency_gain} additional focused hunks")
                print(f"   This allows for more precise feature separation!")

        # Show final git log
        print("\n" + "="*80)
        print("FINAL GIT HISTORY:")
        print("-"*40)
        log_result = subprocess.run(['git', 'log', '--oneline', '-n', '10'],
                                  capture_output=True, text=True)
        print(log_result.stdout)

        print("\n" + "="*80)
        print("🎉 Comparison completed successfully!")
        print("="*80)

    except Exception as e:
        print(f"\nError in comparison: {e}")
        return


def cleanup_example():
    """Clean up test files and commits"""
    print("\nCleaning up example files...")

    # Remove test files
    files_to_remove = [
        'test_example.py',
        'test_example.py.feature2.patch',
        'ambiguous_example.py',
        'ambiguous_example.py.feature2.enhanced.patch'
    ]

    for file in files_to_remove:
        if Path(file).exists():
            Path(file).unlink()
            print(f"  Removed {file}")

    # Remove cache directories
    cache_dir = Path.home() / '.cache' / 'hunk_classifier'
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)
        print(f"  Removed cache directory: {cache_dir}")

    # Reset git to remove test commits (optional)
    # subprocess.run(['git', 'reset', '--hard', 'HEAD~4'], capture_output=True)

    print("Cleanup complete!")


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--basic':
            # Check for API key
            if not os.getenv("OPENAI_API_KEY"):
                print("ERROR: Please set OPENAI_API_KEY environment variable")
                sys.exit(1)
            run_basic_example()
        elif sys.argv[1] == '--enhanced':
            # Check for API key
            if not os.getenv("OPENAI_API_KEY"):
                print("ERROR: Please set OPENAI_API_KEY environment variable")
                sys.exit(1)
            run_enhanced_example()
        elif sys.argv[1] == '--cleanup':
            cleanup_example()
            sys.exit(0)
        else:
            print("Usage: python example_usage.py [--basic|--enhanced|--cleanup]")
            sys.exit(1)
    else:
        # Default: run comparison
        run_comparison()

    # Optional: Ask user if they want to clean up
    try:
        response = input("\nDo you want to clean up the test files? (y/n): ")
        if response.lower() == 'y':
            cleanup_example()
    except KeyboardInterrupt:
        print("\nExiting without cleanup.")
