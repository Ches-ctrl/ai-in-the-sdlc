"""Orchestrate the complete git history rewriting workflow."""

import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import anyio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .git.operations import GitCloner, GitError
from .conversation_loader import ConversationLoader
from .prompt_builder import PromptBuilder
from .claude_agent import ClaudeHistoryRewriter
from .plan_schema import RewritePlan, PlanMetadata, CommitInfo

console = Console()


class RewriteWorkflow:
    """Orchestrate the complete git history rewriting workflow."""
    
    def __init__(self, verbose: bool = False):
        """Initialize RewriteWorkflow.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.cloner = GitCloner(verbose=verbose)
        self.conversation_loader = ConversationLoader(verbose=verbose)
        self.prompt_builder = PromptBuilder(verbose=verbose)
        self.rewriter = ClaudeHistoryRewriter(verbose=verbose)
        self.temp_dir: Optional[Path] = None
    
    def _cleanup_temp_dir(self):
        """Clean up temporary directory if it exists."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                if self.verbose:
                    console.print(f"[blue]Cleaned up temporary directory: {self.temp_dir}[/blue]")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not clean up temp directory: {e}[/yellow]")
    
    def process(
        self,
        repo_url: str,
        branch: str,
        initial_commit: str,
        final_commit: str,
        output_plan: Path,
        target_dir: Optional[Path] = None,
        prompt: Optional[str] = None,
        conversation_file: Optional[Path] = None,
        model: Optional[str] = None,
        cleanup: bool = False
    ) -> RewritePlan:
        """Process the complete workflow from clone to plan generation.
        
        Args:
            repo_url: Git repository URL
            branch: Branch to checkout
            initial_commit: Starting commit SHA (older)
            final_commit: Ending commit SHA (newer)
            output_plan: Path to save the generated plan
            target_dir: Optional directory where repository will be cloned
            prompt: Optional custom instructions for rewriting
            conversation_file: Optional JSONL file with conversation history
            model: Optional Claude model to use
            cleanup: Clean up temporary directory after completion
            
        Returns:
            Generated RewritePlan
            
        Raises:
            GitError: If git operations fail
            FileNotFoundError: If conversation file doesn't exist
            Exception: For other failures
        """
        try:
            # Display workflow summary
            console.print("\n[bold]Workflow Configuration:[/bold]")
            table = Table(show_header=False, box=None)
            table.add_row("Repository:", repo_url)
            table.add_row("Branch:", branch)
            table.add_row("Commit Range:", f"{initial_commit}..{final_commit}")
            if prompt:
                table.add_row("Instructions:", prompt[:80] + "..." if len(prompt) > 80 else prompt)
            if conversation_file:
                table.add_row("Context File:", str(conversation_file))
            table.add_row("Output Plan:", str(output_plan))
            console.print(table)
            console.print()
            
            # Step 1: Clone repository
            console.print("[bold blue]Step 1: Cloning repository...[/bold blue]")
            
            # Use provided target_dir or create temp directory
            if target_dir:
                # Ensure target_dir exists
                target_dir.mkdir(parents=True, exist_ok=True)
                repo_path = target_dir
                self.temp_dir = None  # No temp dir to clean up
            else:
                self.temp_dir = Path(tempfile.mkdtemp(prefix="git_rewrite_"))
                repo_path = self.temp_dir / "repo"
            
            repo = self.cloner.clone_repository(
                repo_url=repo_url,
                target_dir=repo_path,
                branch=branch
            )
            console.print(f"[green]✓ Repository cloned to temporary directory[/green]\n")
            
            # Step 2: Validate commit range
            console.print("[bold blue]Step 2: Validating commit range...[/bold blue]")
            commits = self.cloner.get_commit_history(repo_path, initial_commit, final_commit)
            
            if not commits:
                raise GitError(f"No commits found between {initial_commit} and {final_commit}")
            
            console.print(f"[green]✓ Found {len(commits)} commits in range[/green]\n")
            
            # Step 3: Load conversation context (if provided)
            conversation_context = ""
            if conversation_file:
                console.print("[bold blue]Step 3: Loading conversation context...[/bold blue]")
                conversations = self.conversation_loader.load_jsonl(conversation_file)
                conversation_context = self.conversation_loader.format_for_prompt(conversations)
                console.print(f"[green]✓ Loaded {len(conversations)} conversation entries[/green]\n")
            else:
                if self.verbose:
                    console.print("[dim]Step 3: No conversation context provided, skipping...[/dim]\n")
            
            # Step 4: Build AI prompt
            console.print("[bold blue]Step 4: Building AI prompt...[/bold blue]")
            
            # Use default prompt if none provided
            if not prompt:
                prompt = "Clean up and improve the commit history. Squash related commits, improve commit messages, and ensure a logical progression."
            
            # Build the complete prompt with conversation context
            base_prompt = self.prompt_builder.build_rewrite_prompt(
                repo_path=repo_path,
                initial_commit=initial_commit,
                final_commit=final_commit,
                user_instructions=prompt,
                commit_history=commits
            )
            
            # Append conversation context if available
            if conversation_context:
                full_prompt = f"{base_prompt}\n\n{conversation_context}"
            else:
                full_prompt = base_prompt
            
            console.print("[green]✓ AI prompt prepared[/green]\n")
            
            # Step 5: Generate rewrite plan
            console.print("[bold blue]Step 5: Generating rewrite plan with Claude...[/bold blue]")
            
            # Use the PromptBuilder to build a proper prompt for plan generation
            from .prompt_builder import PromptBuilder
            pb = PromptBuilder(verbose=self.verbose)
            
            # Build the prompt specifically for plan generation
            plan_prompt = pb.build_rewrite_prompt(
                repo_path=repo_path,
                initial_commit=initial_commit,
                final_commit=final_commit,
                user_instructions=prompt,
                commit_history=commits
            )
            
            # Create plan metadata
            plan_metadata = PlanMetadata(
                repository=repo_url,  # Store original URL instead of temp path
                initial_commit=initial_commit,
                final_commit=final_commit,
                prompt=prompt,
                model=model,
                temp_directory=str(repo_path),  # Store cloned repo path for apply-plan
                original_commits=[
                    CommitInfo(
                        sha=commit['sha'],
                        message=commit['message'],
                        author=commit['author'],
                        author_email=commit['author_email'],
                        date=commit['date'],
                        files_changed=commit.get('files_changed'),
                        insertions=commit.get('insertions'),
                        deletions=commit.get('deletions')
                    )
                    for commit in commits
                ],
                original_commit_count=len(commits)
            )
            
            # Create the plan
            plan = RewritePlan(metadata=plan_metadata)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Generating plan with Claude...", total=None)
                
                # Call Claude to generate the plan with structured output
                result = anyio.run(
                    self.rewriter.generate_plan,
                    plan_prompt,
                    repo_path,
                    commits,
                    model
                )
                
                progress.update(task, completed=True)
            
            # Parse Claude's response into operations
            if result and result.get("operations"):
                for op in result["operations"]:
                    from .plan_schema import Operation
                    
                    # Map fields from Claude's response to Operation fields
                    op_data = {'type': op.get('type', 'unknown')}
                    
                    # Optional fields
                    for field in ['commits', 'commit', 'new_message', 'old_message', 
                                  'description', 'reason', 'from_position', 'to_position']:
                        if field in op:
                            op_data[field] = op[field]
                    
                    # Handle 'message' as 'new_message'
                    if 'message' in op and 'new_message' not in op_data:
                        op_data['new_message'] = op['message']
                    
                    try:
                        plan.operations.append(Operation(**op_data))
                    except Exception as e:
                        if self.verbose:
                            console.print(f"[yellow]Warning: Skipping invalid operation: {e}[/yellow]")
            
            # Update planned commit count if provided
            if result and result.get("planned_commit_count"):
                plan.metadata.planned_commit_count = result["planned_commit_count"]
            
            console.print(f"[green]✓ Plan generated with {len(plan.operations)} operations[/green]\n")
            
            # Step 6: Save plan
            console.print("[bold blue]Step 6: Saving plan...[/bold blue]")
            plan.save(output_plan)
            console.print(f"[green]✓ Plan saved to {output_plan}[/green]\n")
            
            # Display plan summary
            console.print("[bold]Plan Summary:[/bold]")
            table = Table(show_header=True)
            table.add_column("Operation Type", style="cyan")
            table.add_column("Count", style="green")
            
            operation_counts: Dict[str, int] = {}
            for op in plan.operations:
                op_type = op.type.value if hasattr(op.type, 'value') else str(op.type)
                operation_counts[op_type] = operation_counts.get(op_type, 0) + 1
            
            for op_type, count in operation_counts.items():
                table.add_row(op_type, str(count))
            
            if operation_counts:
                console.print(table)
            
            console.print(f"\n[bold green]✓ Workflow completed successfully![/bold green]")
            console.print(f"Plan saved to: [cyan]{output_plan.absolute()}[/cyan]")
            console.print(f"Repository cloned to: [cyan]{repo_path.absolute()}[/cyan]")
            console.print(f"\nTo apply this plan, run:")
            console.print(f"[dim]git-history-rewriter apply-plan --plan {output_plan.absolute()} --repo {repo_path.absolute()}[/dim]")
            console.print(f"\n[yellow]Note: The cloned repository is kept for the apply-plan step.[/yellow]")
            if not cleanup and self.temp_dir:
                console.print(f"[yellow]Clean up temp directory when done: rm -rf {self.temp_dir}[/yellow]\n")
            
            return plan
            
        except Exception as e:
            console.print(f"[red]✗ Workflow failed: {e}[/red]")
            raise
        finally:
            if cleanup:
                self._cleanup_temp_dir()