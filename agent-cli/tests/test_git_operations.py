"""Tests for git operations."""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from git import Repo, GitCommandError

from git_history_rewriter.git import GitCloner, GitError


class TestGitCloner:
    """Test suite for GitCloner class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cloner = GitCloner(verbose=False)
        self.temp_dir = None
    
    def teardown_method(self):
        """Clean up after tests."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_url_https(self):
        """Test URL validation for HTTPS URLs."""
        # Valid HTTPS URLs
        assert self.cloner.validate_url("https://github.com/user/repo.git")
        assert self.cloner.validate_url("https://github.com/user/repo")
        assert self.cloner.validate_url("http://gitlab.com/org/project.git")
        
        # Invalid URLs
        assert not self.cloner.validate_url("not-a-url")
        assert not self.cloner.validate_url("ftp://github.com/user/repo.git")
        assert not self.cloner.validate_url("https://")
    
    def test_validate_url_ssh(self):
        """Test URL validation for SSH URLs."""
        # Valid SSH URLs
        assert self.cloner.validate_url("git@github.com:user/repo.git")
        assert self.cloner.validate_url("git@gitlab.com:org/project.git")
        assert self.cloner.validate_url("git@github.com:user/repo")
        
        # Invalid SSH URLs
        assert not self.cloner.validate_url("git@github.com")
        assert not self.cloner.validate_url("git@:repo.git")
    
    @patch('git_history_rewriter.git.operations.Repo.clone_from')
    def test_clone_repository_success(self, mock_clone):
        """Test successful repository cloning."""
        # Setup
        self.temp_dir = tempfile.mkdtemp()
        target_dir = Path(self.temp_dir) / "test-repo"
        mock_repo = Mock(spec=Repo)
        mock_clone.return_value = mock_repo
        
        # Execute
        result = self.cloner.clone_repository(
            repo_url="https://github.com/user/repo.git",
            target_dir=target_dir,
        )
        
        # Assert
        assert result == mock_repo
        mock_clone.assert_called_once()
        args, kwargs = mock_clone.call_args
        assert args[0] == "https://github.com/user/repo.git"
        assert args[1] == target_dir
    
    @patch('git_history_rewriter.git.operations.Repo.clone_from')
    def test_clone_repository_with_branch(self, mock_clone):
        """Test cloning with branch checkout."""
        # Setup
        self.temp_dir = tempfile.mkdtemp()
        target_dir = Path(self.temp_dir) / "test-repo"
        mock_repo = Mock(spec=Repo)
        mock_repo.remotes.origin.fetch = Mock()
        mock_repo.git.checkout = Mock()
        mock_repo.branches = []
        mock_repo.remotes.origin.refs = [
            Mock(name="origin/main"),
            Mock(name="origin/develop"),
        ]
        mock_clone.return_value = mock_repo
        
        # Execute
        with patch.object(self.cloner, 'checkout_branch') as mock_checkout:
            result = self.cloner.clone_repository(
                repo_url="https://github.com/user/repo.git",
                target_dir=target_dir,
                branch="develop",
            )
            
            # Assert
            mock_checkout.assert_called_once_with(mock_repo, "develop")
    
    def test_clone_repository_invalid_url(self):
        """Test cloning with invalid URL."""
        self.temp_dir = tempfile.mkdtemp()
        target_dir = Path(self.temp_dir) / "test-repo"
        
        with pytest.raises(GitError) as exc_info:
            self.cloner.clone_repository(
                repo_url="not-a-valid-url",
                target_dir=target_dir,
            )
        
        assert "Invalid repository URL format" in str(exc_info.value)
    
    def test_clone_repository_existing_directory(self):
        """Test cloning to existing non-empty directory."""
        self.temp_dir = tempfile.mkdtemp()
        target_dir = Path(self.temp_dir) / "test-repo"
        target_dir.mkdir(parents=True)
        (target_dir / "existing-file.txt").write_text("content")
        
        with pytest.raises(GitError) as exc_info:
            self.cloner.clone_repository(
                repo_url="https://github.com/user/repo.git",
                target_dir=target_dir,
            )
        
        assert "already exists and is not empty" in str(exc_info.value)
    
    @patch('git_history_rewriter.git.operations.Repo.clone_from')
    def test_clone_repository_auth_failure(self, mock_clone):
        """Test handling of authentication failures."""
        self.temp_dir = tempfile.mkdtemp()
        target_dir = Path(self.temp_dir) / "test-repo"
        mock_clone.side_effect = GitCommandError(
            "git clone",
            128,
            stderr="Authentication failed"
        )
        
        with pytest.raises(GitError) as exc_info:
            self.cloner.clone_repository(
                repo_url="https://github.com/user/private-repo.git",
                target_dir=target_dir,
            )
        
        assert "Authentication failed" in str(exc_info.value)
        assert "SSH URL with configured SSH keys" in str(exc_info.value)
    
    def test_checkout_branch_local(self):
        """Test checking out a local branch."""
        mock_repo = Mock(spec=Repo)
        mock_branch = Mock(name="feature")
        mock_repo.branches = [mock_branch]
        mock_repo.remotes.origin.refs = []
        mock_repo.remotes.origin.fetch = Mock()
        mock_repo.git.checkout = Mock()
        
        self.cloner.checkout_branch(mock_repo, "feature")
        
        mock_repo.git.checkout.assert_called_once_with("feature")
    
    def test_checkout_branch_remote(self):
        """Test checking out a remote branch."""
        mock_repo = Mock(spec=Repo)
        mock_repo.branches = []
        mock_repo.remotes.origin.refs = [
            Mock(name="origin/develop"),
        ]
        mock_repo.remotes.origin.fetch = Mock()
        mock_repo.git.checkout = Mock()
        
        self.cloner.checkout_branch(mock_repo, "develop")
        
        mock_repo.git.checkout.assert_called_once_with(
            "-b", "develop", "origin/develop"
        )
    
    def test_checkout_branch_not_found(self):
        """Test checking out non-existent branch."""
        mock_repo = Mock(spec=Repo)
        mock_repo.branches = [Mock(name="main")]
        mock_repo.remotes.origin.refs = [
            Mock(name="origin/main"),
        ]
        mock_repo.remotes.origin.fetch = Mock()
        
        with pytest.raises(GitError) as exc_info:
            self.cloner.checkout_branch(mock_repo, "non-existent")
        
        assert "Branch 'non-existent' not found" in str(exc_info.value)
        assert "Available branches:" in str(exc_info.value)
        assert "main" in str(exc_info.value)
    
    def test_list_branches(self):
        """Test listing repository branches."""
        mock_repo = Mock(spec=Repo)
        mock_repo.branches = [
            Mock(name="main"),
            Mock(name="develop"),
        ]
        mock_repo.remotes.origin.refs = [
            Mock(name="origin/feature/new"),
            Mock(name="origin/HEAD"),
            Mock(name="origin/main"),
        ]
        
        branches = self.cloner.list_branches(mock_repo)
        
        assert "main" in branches
        assert "develop" in branches
        assert "feature/new" in branches
        assert "HEAD" not in branches
        assert len(branches) == 3
    
    def test_get_repo_info(self):
        """Test getting repository information."""
        mock_repo = Mock(spec=Repo)
        mock_repo.active_branch.name = "main"
        mock_repo.remotes.origin.url = "https://github.com/user/repo.git"
        mock_repo.working_dir = "/path/to/repo"
        mock_repo.iter_commits = Mock(return_value=[Mock(), Mock(), Mock()])
        
        info = self.cloner.get_repo_info(mock_repo)
        
        assert info["branch"] == "main"
        assert info["url"] == "https://github.com/user/repo.git"
        assert info["location"] == "/path/to/repo"
        assert info["commits"] == 3
    
    def test_get_repo_info_detached_head(self):
        """Test getting repository info in detached HEAD state."""
        mock_repo = Mock(spec=Repo)
        mock_repo.active_branch.name = Mock(side_effect=TypeError)
        mock_repo.head.commit.hexsha = "abc123def456"
        mock_repo.remotes.origin.url = "https://github.com/user/repo.git"
        mock_repo.working_dir = "/path/to/repo"
        mock_repo.iter_commits = Mock(return_value=[Mock()])
        
        info = self.cloner.get_repo_info(mock_repo)
        
        assert "detached HEAD" in info["branch"]
        assert "abc123d" in info["branch"]