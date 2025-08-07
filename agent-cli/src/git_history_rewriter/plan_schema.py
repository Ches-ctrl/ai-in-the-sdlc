"""Schema definitions for git history rewrite plans."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional


class OperationType(Enum):
    """Types of git history operations."""
    SQUASH = "squash"
    REWORD = "reword"
    DROP = "drop"
    REORDER = "reorder"
    EDIT = "edit"
    FIXUP = "fixup"


@dataclass
class CommitInfo:
    """Information about a git commit."""
    sha: str
    message: str
    author: str
    author_email: str
    date: str
    files_changed: Optional[int] = None
    insertions: Optional[int] = None
    deletions: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Operation:
    """A single rewrite operation."""
    type: str  # Using string instead of OperationType for JSON compatibility
    commits: List[str] = field(default_factory=list)
    commit: Optional[str] = None
    new_message: Optional[str] = None
    old_message: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None
    from_position: Optional[int] = None
    to_position: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Operation':
        """Create Operation from dictionary."""
        return cls(**data)


@dataclass
class PlanMetadata:
    """Metadata about the rewrite plan."""
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = "git-history-rewriter"
    repository: str = ""
    branch: Optional[str] = None
    initial_commit: str = ""
    final_commit: str = ""
    prompt: str = ""
    model: Optional[str] = None
    original_commits: List[CommitInfo] = field(default_factory=list)
    original_commit_count: Optional[int] = None
    planned_commit_count: Optional[int] = None
    temp_directory: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert CommitInfo objects to dicts
        data['original_commits'] = [
            c.to_dict() if isinstance(c, CommitInfo) else c 
            for c in self.original_commits
        ]
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class RewritePlan:
    """Complete git history rewrite plan."""
    metadata: PlanMetadata
    operations: List[Operation] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    
    def to_json(self, indent: int = 2) -> str:
        """Convert plan to JSON string."""
        data = {
            "version": self.metadata.version,
            "metadata": self.metadata.to_dict(),
            "operations": [op.to_dict() for op in self.operations],
            "commands": self.commands
        }
        if self.verification:
            data["verification"] = self.verification
        return json.dumps(data, indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'RewritePlan':
        """Create RewritePlan from JSON string."""
        data = json.loads(json_str)
        
        # Parse metadata
        metadata_dict = data.get('metadata', {})
        # Convert original_commits back to CommitInfo objects
        if 'original_commits' in metadata_dict:
            metadata_dict['original_commits'] = [
                CommitInfo(**commit) if isinstance(commit, dict) else commit
                for commit in metadata_dict['original_commits']
            ]
        metadata = PlanMetadata(**metadata_dict)
        
        # Parse operations
        operations = [
            Operation.from_dict(op) 
            for op in data.get('operations', [])
        ]
        
        # Create plan
        return cls(
            metadata=metadata,
            operations=operations,
            commands=data.get('commands', []),
            verification=data.get('verification')
        )
    
    def save(self, path: Path) -> None:
        """Save plan to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
    
    @classmethod
    def load(cls, path: Path) -> 'RewritePlan':
        """Load plan from file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")
        return cls.from_json(path.read_text())
    
    def add_operation(self, operation: Operation) -> None:
        """Add an operation to the plan."""
        self.operations.append(operation)
    
    def add_command(self, command: str) -> None:
        """Add a command to the plan."""
        self.commands.append(command)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the plan."""
        lines = [
            f"Git History Rewrite Plan",
            f"========================",
            f"Created: {self.metadata.created_at}",
            f"Repository: {self.metadata.repository}",
        ]
        
        if self.metadata.branch:
            lines.append(f"Branch: {self.metadata.branch}")
        
        lines.extend([
            f"Commits: {self.metadata.initial_commit[:7]}..{self.metadata.final_commit[:7]}",
            f"Original commits: {self.metadata.original_commit_count or len(self.metadata.original_commits)}",
        ])
        
        if self.metadata.planned_commit_count:
            lines.append(f"Planned commits: {self.metadata.planned_commit_count}")
        
        lines.extend([
            "",
            "Operations:",
            "-----------"
        ])
        
        # Group operations by type
        op_counts = {}
        for op in self.operations:
            op_counts[op.type] = op_counts.get(op.type, 0) + 1
        
        for op_type, count in op_counts.items():
            lines.append(f"  {op_type}: {count}")
        
        if self.commands:
            lines.extend([
                "",
                "Commands to execute:",
                "-------------------"
            ])
            for cmd in self.commands[:5]:  # Show first 5 commands
                lines.append(f"  {cmd}")
            if len(self.commands) > 5:
                lines.append(f"  ... and {len(self.commands) - 5} more")
        
        return "\n".join(lines)


def create_example_plan() -> RewritePlan:
    """Create an example plan for testing."""
    metadata = PlanMetadata(
        repository="/path/to/repo",
        branch="feature-branch",
        initial_commit="abc123",
        final_commit="def456",
        prompt="Squash WIP commits and improve messages",
        model="claude-3.5-sonnet",
        original_commit_count=10,
        planned_commit_count=6
    )
    
    plan = RewritePlan(metadata=metadata)
    
    # Add some example operations
    plan.add_operation(Operation(
        type=OperationType.SQUASH.value,
        commits=["abc123", "bcd234", "cde345"],
        new_message="feat: add user authentication",
        description="Combines WIP auth commits"
    ))
    
    plan.add_operation(Operation(
        type=OperationType.REWORD.value,
        commit="def456",
        old_message="fix bug",
        new_message="fix(api): resolve null pointer in user endpoint"
    ))
    
    plan.add_operation(Operation(
        type=OperationType.DROP.value,
        commit="efg567",
        reason="Temporary debug code"
    ))
    
    # Add example commands
    plan.add_command("git checkout feature-branch")
    plan.add_command("git rebase -i abc123^")
    
    return plan


if __name__ == "__main__":
    # Test the schema
    plan = create_example_plan()
    print(plan.get_summary())
    print("\nJSON representation:")
    print(plan.to_json())
    
    # Test round-trip
    json_str = plan.to_json()
    plan2 = RewritePlan.from_json(json_str)
    assert plan.metadata.repository == plan2.metadata.repository
    assert len(plan.operations) == len(plan2.operations)
    print("\n✓ Round-trip test passed")