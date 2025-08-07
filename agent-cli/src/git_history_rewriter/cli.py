#!/usr/bin/env python3
"""Command-line interface for git-history-rewriter."""

import json
import sys
from pathlib import Path
from typing import Optional
import anyio

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from git_history_rewriter.git import GitCloner, GitError
from git_history_rewriter.claude_agent import ClaudeHistoryRewriter
from git_history_rewriter.prompt_builder import PromptBuilder
from git_history_rewriter.plan_schema import RewritePlan, PlanMetadata, Operation, CommitInfo


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="git-history-rewriter")
def cli():
    """AI-powered git history rewriting tool.
    
    This tool helps you clone repositories and rewrite their git history
    using AI assistance from Claude Code SDK.
    """
    pass


@cli.command()
@click.option(
    "--repo-url",
    required=True,
    help="Repository URL (HTTPS or SSH)",
)
@click.option(
    "--branch",
    required=True,
    help="Branch to checkout",
)
@click.option(
    "--target-dir",
    required=True,
    type=click.Path(path_type=Path),
    help="Target directory for clone",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="Create shallow clone with specified depth",
)
def clone(
    repo_url: str,
    branch: str,
    target_dir: Path,
    verbose: bool,
    depth: Optional[int],
):
    """Clone a repository and checkout a specific branch.
    
    Examples:
    
        git-history-rewriter clone --repo-url https://github.com/user/repo.git --branch main --target-dir ./workspace
        
        git-history-rewriter clone --repo-url git@github.com:user/repo.git --branch develop --target-dir /tmp/repo --verbose
    """
    try:
        # Initialize cloner
        cloner = GitCloner(verbose=verbose)
        
        # Display operation summary
        if verbose:
            console.print("[bold]Clone Operation Summary:[/bold]")
            table = Table(show_header=False, box=None)
            table.add_row("Repository URL:", repo_url)
            table.add_row("Branch:", branch)
            table.add_row("Target Directory:", str(target_dir))
            if depth:
                table.add_row("Shallow Depth:", str(depth))
            console.print(table)
            console.print()
        
        # Perform clone operation
        repo = cloner.clone_repository(
            repo_url=repo_url,
            target_dir=target_dir,
            branch=branch,
            depth=depth,
        )
        
        # Get repository info
        info = cloner.get_repo_info(repo)
        
        # Display success message
        console.print()
        console.print("[bold green]✓ Repository cloned successfully[/bold green]")
        console.print(f"  URL: {info['url']}")
        console.print(f"  Branch: {info['branch']}")
        console.print(f"  Location: {info['location']}")
        console.print(f"  Commits: {info['commits']} commits")
        
    except GitError as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        console.print_exception()  # Always show exception for debugging
        sys.exit(1)


@cli.command()
@click.option(
    "--repo",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to git repository",
)
@click.option(
    "--initial-commit",
    required=True,
    help="Starting commit SHA (older commit)",
)
@click.option(
    "--final-commit",
    required=True,
    help="Ending commit SHA (newer commit)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def history(
    repo: Path,
    initial_commit: str,
    final_commit: str,
    verbose: bool,
):
    """Get commit history between two commits.
    
    This command displays all commits between the initial commit (exclusive)
    and final commit (inclusive) in chronological order.
    
    Examples:
    
        git-history-rewriter history --repo ./my-repo --initial-commit abc123 --final-commit def456
        
        git-history-rewriter history --repo /path/to/repo --initial-commit HEAD~10 --final-commit HEAD --verbose
    """
    try:
        # Initialize cloner (reusing for history functionality)
        cloner = GitCloner(verbose=verbose)
        
        # Display operation summary
        if verbose:
            console.print("[bold]History Operation Summary:[/bold]")
            table = Table(show_header=False, box=None)
            table.add_row("Repository:", str(repo))
            table.add_row("Initial Commit:", initial_commit)
            table.add_row("Final Commit:", final_commit)
            console.print(table)
            console.print()
        
        # Get commit history
        console.print("[blue]Retrieving commit history...[/blue]")
        commits = cloner.get_commit_history(repo, initial_commit, final_commit)
        
        if not commits:
            console.print("[yellow]No commits found in the specified range[/yellow]")
            return
        
        # Display commit history
        console.print(f"\n[bold green]Found {len(commits)} commits:[/bold green]\n")
        
        for commit in commits:
            # Display commit header
            console.print(f"[yellow]commit {commit['sha']}[/yellow]")
            console.print(f"Author: {commit['author']} <{commit['author_email']}>")
            console.print(f"Date:   {commit['date']}")
            
            # Display stats if verbose
            if verbose:
                console.print(f"Files:  {commit['files_changed']} changed, "
                            f"[green]+{commit['insertions']}[/green], "
                            f"[red]-{commit['deletions']}[/red]")
            
            # Display commit message
            console.print()
            for line in commit['message'].split('\n'):
                console.print(f"    {line}")
            console.print()
        
        # Display summary
        console.print(f"[bold]Summary:[/bold] {len(commits)} commits from {commits[0]['short_sha']} to {commits[-1]['short_sha']}")
        
    except GitError as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        console.print_exception()  # Always show exception for debugging
        sys.exit(1)


@cli.command()
@click.option(
    "--repo-url",
    required=True,
    help="Repository URL to prepare for rewriting",
)
@click.option(
    "--initial-commit",
    required=True,
    help="Starting commit SHA for rewrite range",
)
@click.option(
    "--final-commit",
    required=True,
    help="Ending commit SHA for rewrite range",
)
@click.option(
    "--conversation",
    type=click.Path(exists=True, path_type=Path),
    help="Path to JSONL conversation file for context",
)
@click.option(
    "--target-dir",
    required=True,
    type=click.Path(path_type=Path),
    help="Target directory for clone",
)
def prepare(
    repo_url: str,
    initial_commit: str,
    final_commit: str,
    conversation: Optional[Path],
    target_dir: Path,
):
    """Prepare repository for history rewriting.
    
    This command clones the repository and sets up the environment
    for AI-assisted history rewriting.
    """
    console.print("[yellow]⚠ This command is not yet implemented[/yellow]")
    console.print("The 'prepare' command will be available in a future version.")
    console.print("\nPlanned features:")
    console.print("  • Clone repository to workspace")
    console.print("  • Analyze commit range")
    console.print("  • Load conversation context")
    console.print("  • Prepare for AI-assisted rewriting")


@cli.command()
@click.option(
    "--repo",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Repository path",
)
@click.option(
    "--initial-commit",
    required=True,
    help="Starting commit SHA (older commit)",
)
@click.option(
    "--final-commit",
    required=True,
    help="Ending commit SHA (newer commit)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def analyze(
    repo: Path,
    initial_commit: str,
    final_commit: str,
    verbose: bool,
):
    """Analyze commits using Claude to suggest improvements.
    
    This command uses Claude to analyze the commit history and suggest
    how it could be improved without making any changes.
    
    Examples:
    
        git-history-rewriter analyze --repo ./my-repo --initial-commit HEAD~10 --final-commit HEAD
        
        git-history-rewriter analyze --repo ./my-repo --initial-commit abc123 --final-commit def456 --verbose
    """
    try:
        # Initialize components
        prompt_builder = PromptBuilder(verbose=verbose)
        rewriter = ClaudeHistoryRewriter(verbose=verbose)
        
        # Display operation summary
        console.print("[bold]Analyze Operation Summary:[/bold]")
        table = Table(show_header=False, box=None)
        table.add_row("Repository:", str(repo))
        table.add_row("Initial Commit:", initial_commit)
        table.add_row("Final Commit:", final_commit)
        console.print(table)
        console.print()
        
        # Build analysis prompt
        analyze_prompt = prompt_builder.build_analyze_prompt(
            repo_path=repo,
            initial_commit=initial_commit,
            final_commit=final_commit
        )
        
        # Run analysis
        console.print("[blue]Analyzing commits with Claude...[/blue]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running analysis...", total=None)
            
            analysis = anyio.run(
                rewriter.analyze_commits,
                repo,
                initial_commit,
                final_commit
            )
            
            progress.update(task, completed=True)
        
        # Display analysis
        console.print("\n[bold green]Analysis Complete:[/bold green]\n")
        console.print(analysis)
        
    except GitError as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        console.print_exception()  # Always show exception for debugging
        sys.exit(1)


@cli.command()
@click.option(
    "--repo",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Repository path",
)
@click.option(
    "--prompt",
    required=True,
    help="Instructions for how to rewrite the history",
)
@click.option(
    "--initial-commit",
    required=True,
    help="Starting commit SHA (older commit)",
)
@click.option(
    "--final-commit",
    required=True,
    help="Ending commit SHA (newer commit)",
)
@click.option(
    "--model",
    help="Claude model to use (optional)",
)
@click.option(
    "--permission-mode",
    type=click.Choice(["default", "acceptEdits", "bypassPermissions"]),
    default="acceptEdits",
    help="Permission mode for tool use",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without executing",
)
@click.option(
    "--save-plan",
    type=click.Path(path_type=Path),
    help="Save the rewrite plan to a JSON file (use with --dry-run)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def rewrite(
    repo: Path,
    prompt: str,
    initial_commit: str,
    final_commit: str,
    model: Optional[str],
    permission_mode: str,
    dry_run: bool,
    save_plan: Optional[Path],
    verbose: bool,
):
    """Rewrite git history using Claude AI assistance.
    
    This command uses Claude Code SDK to intelligently rewrite git history
    based on your natural language instructions.
    
    Examples:
    
        git-history-rewriter rewrite --repo ./my-repo --prompt "Squash all WIP commits" --initial-commit HEAD~10 --final-commit HEAD
        
        git-history-rewriter rewrite --repo ./my-repo --prompt "Improve commit messages and group by feature" --initial-commit abc123 --final-commit def456 --dry-run
    """
    try:
        # Initialize components
        cloner = GitCloner(verbose=verbose)
        prompt_builder = PromptBuilder(verbose=verbose)
        rewriter = ClaudeHistoryRewriter(verbose=verbose)
        
        # Display operation summary
        console.print("[bold]Rewrite Operation Summary:[/bold]")
        table = Table(show_header=False, box=None)
        table.add_row("Repository:", str(repo))
        table.add_row("Initial Commit:", initial_commit)
        table.add_row("Final Commit:", final_commit)
        table.add_row("Instructions:", prompt[:100] + "..." if len(prompt) > 100 else prompt)
        table.add_row("Permission Mode:", permission_mode)
        if model:
            table.add_row("Model:", model)
        if dry_run:
            table.add_row("Mode:", "[yellow]DRY RUN[/yellow]")
        console.print(table)
        console.print()
        
        # Get commit history for context
        console.print("[blue]Analyzing commit history...[/blue]")
        commits = cloner.get_commit_history(repo, initial_commit, final_commit)
        
        if not commits:
            console.print("[yellow]No commits found in the specified range[/yellow]")
            console.print("Make sure initial_commit is an ancestor of final_commit")
            sys.exit(1)
        
        console.print(f"Found [green]{len(commits)}[/green] commits to potentially rewrite\n")
        
        # Build the complete prompt
        agent_prompt = prompt_builder.build_rewrite_prompt(
            repo_path=repo,
            initial_commit=initial_commit,
            final_commit=final_commit,
            user_instructions=prompt,
            commit_history=commits
        )
        
        # Execute the rewrite with Claude
        if dry_run and save_plan:
            console.print("[yellow]Generating rewrite plan...[/yellow]\n")
            
            # Create plan metadata
            plan_metadata = PlanMetadata(
                repository=str(repo),
                initial_commit=initial_commit,
                final_commit=final_commit,
                prompt=prompt,
                model=model,
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
                
                # Run the async rewrite operation to generate plan
                result = anyio.run(
                    rewriter.generate_plan,
                    agent_prompt,
                    repo,
                    commits,
                    model
                )
                
                progress.update(task, completed=True)
            
            # Add operations and commands from Claude's response
            if result.get("operations"):
                for op in result["operations"]:
                    # Map fields from Claude's response to Operation fields
                    op_data = {}
                    
                    # Required field
                    op_data['type'] = op.get('type', 'unknown')
                    
                    # Optional fields - map common variations
                    if 'commits' in op:
                        op_data['commits'] = op['commits']
                    if 'commit' in op:
                        op_data['commit'] = op['commit']
                    
                    # Handle message fields - Claude might use 'message' instead of 'new_message'
                    if 'message' in op:
                        op_data['new_message'] = op['message']
                    if 'new_message' in op:
                        op_data['new_message'] = op['new_message']
                    if 'old_message' in op:
                        op_data['old_message'] = op['old_message']
                    
                    # Other optional fields
                    if 'description' in op:
                        op_data['description'] = op['description']
                    if 'reason' in op:
                        op_data['reason'] = op['reason']
                    if 'from_position' in op:
                        op_data['from_position'] = op['from_position']
                    if 'to_position' in op:
                        op_data['to_position'] = op['to_position']
                    
                    try:
                        plan.add_operation(Operation(**op_data))
                    except TypeError as e:
                        console.print(f"[yellow]Warning: Skipping invalid operation: {e}[/yellow]")
                        if verbose:
                            console.print(f"[dim]Operation data: {op}[/dim]")
            
            if result.get("commands"):
                for cmd in result["commands"]:
                    plan.add_command(cmd)
            
            # Update planned commit count if provided
            if result.get("planned_commit_count"):
                plan.metadata.planned_commit_count = result["planned_commit_count"]
            
            # Save the plan
            plan.save(save_plan)
            
            console.print(f"\n[bold green]✓ Plan generated and saved to: {save_plan}[/bold green]\n")
            console.print(plan.get_summary())
            console.print(f"\n[bold]Next steps:[/bold]")
            console.print(f"  1. Review the plan: cat {save_plan}")
            console.print(f"  2. Apply the plan: git-history-rewriter apply-plan --plan {save_plan} --repo {repo}")
            
        elif dry_run:
            console.print("[yellow]Running in DRY RUN mode - no changes will be made[/yellow]\n")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Executing Claude agent...", total=None)
                
                # Run the async rewrite operation
                result = anyio.run(
                    rewriter.rewrite_history,
                    agent_prompt,
                    repo,
                    permission_mode,
                    model,
                    dry_run
                )
                
                progress.update(task, completed=True)
            
            # Display results
            console.print()
            if result["success"]:
                console.print("[bold green]✓ History analysis completed successfully[/bold green]")
                console.print("\n[yellow]This was a dry run - no actual changes were made[/yellow]")
                console.print("\n[bold]Tip:[/bold] Use --save-plan to save the rewrite plan for later execution")
            else:
                console.print("[bold red]✗ History analysis failed[/bold red]")
                if result.get("errors"):
                    console.print("\nErrors encountered:")
                    for error in result["errors"]:
                        console.print(f"  • {error}")
                sys.exit(1)
        else:
            # Regular execution without dry-run
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Executing Claude agent...", total=None)
                
                # Run the async rewrite operation
                result = anyio.run(
                    rewriter.rewrite_history,
                    agent_prompt,
                    repo,
                    permission_mode,
                    model,
                    dry_run
                )
                
                progress.update(task, completed=True)
            
            # Display results
            console.print()
            if result["success"]:
                console.print("[bold green]✓ History rewrite completed successfully[/bold green]")
                if result.get("duration_ms"):
                    console.print(f"  Duration: {result['duration_ms'] / 1000:.1f} seconds")
                if result.get("num_turns"):
                    console.print(f"  Turns: {result['num_turns']}")
                if result.get("total_cost_usd"):
                    console.print(f"  Cost: ${result['total_cost_usd']:.4f}")
                if result.get("tool_uses"):
                    console.print(f"  Tools used: {len(result['tool_uses'])} times")
                
                console.print("\n[bold]Next steps:[/bold]")
                console.print("  1. Review the changes with: git log --oneline")
                console.print("  2. If satisfied, push to remote with: git push --force-with-lease")
                console.print("  3. If not satisfied, restore from backup branch")
            else:
                console.print("[bold red]✗ History rewrite failed[/bold red]")
                if result.get("errors"):
                    console.print("\nErrors encountered:")
                    for error in result["errors"]:
                        console.print(f"  • {error}")
                sys.exit(1)
        
    except GitError as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        console.print_exception()  # Always show exception for debugging
        sys.exit(1)


@cli.command("apply-plan")
@click.option(
    "--plan",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to the rewrite plan JSON file",
)
@click.option(
    "--repo",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Repository path",
)
@click.option(
    "--backup-branch",
    help="Name for backup branch (default: backup-{timestamp})",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def apply_plan(
    plan: Path,
    repo: Path,
    backup_branch: Optional[str],
    force: bool,
    verbose: bool,
):
    """Apply a saved rewrite plan to rewrite git history.
    
    This command reads a plan file generated by 'rewrite --dry-run --save-plan'
    and executes the git operations to rewrite history.
    
    Examples:
    
        git-history-rewriter apply-plan --plan rewrite-plan.json --repo ./my-repo
        
        git-history-rewriter apply-plan --plan plan.json --repo . --backup-branch pre-rewrite --force
    """
    try:
        # Load the plan
        console.print(f"Loading plan from: {plan}")
        rewrite_plan = RewritePlan.load(plan)
        
        # Display plan summary
        console.print("\n" + rewrite_plan.get_summary())
        
        # Verify repository
        if str(repo.resolve()) != rewrite_plan.metadata.repository and not force:
            console.print(f"\n[yellow]⚠ Warning: Plan was created for different repository[/yellow]")
            console.print(f"  Plan repository: {rewrite_plan.metadata.repository}")
            console.print(f"  Current repository: {repo.resolve()}")
            if not click.confirm("\nDo you want to continue anyway?"):
                console.print("[red]Operation cancelled[/red]")
                sys.exit(1)
        
        # Confirm execution
        if not force:
            console.print(f"\n[bold yellow]⚠ This will rewrite git history![/bold yellow]")
            console.print(f"  Repository: {repo}")
            console.print(f"  Commits: {rewrite_plan.metadata.initial_commit[:7]}..{rewrite_plan.metadata.final_commit[:7]}")
            console.print(f"  Operations: {len(rewrite_plan.operations)}")
            
            if not click.confirm("\nDo you want to proceed?"):
                console.print("[red]Operation cancelled[/red]")
                sys.exit(1)
        
        # Create backup branch
        if not backup_branch:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_branch = f"backup-{timestamp}"
        
        console.print(f"\nCreating backup branch: {backup_branch}")
        
        # Create backup branch first
        import subprocess
        try:
            subprocess.run(
                ["git", "branch", backup_branch],
                cwd=repo,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✗ Failed to create backup branch:[/bold red] {e.stderr.decode()}")
            sys.exit(1)
        
        # Initialize Claude history rewriter for agent-based execution
        rewriter = ClaudeHistoryRewriter(verbose=verbose)
        
        # Execute the plan using Claude agent
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Executing plan with Claude agent...", total=None)
            
            # Run the async apply operation
            result = anyio.run(
                rewriter.apply_saved_plan,
                rewrite_plan,
                repo,
                "acceptEdits",  # permission_mode
                None,  # model (use default)
                backup_branch
            )
            
            progress.update(task, completed=True)
        
        # Display results
        if result["success"]:
            console.print("\n[bold green]✓ Plan applied successfully![/bold green]")
            console.print(f"  Backup branch: {backup_branch}")
            
            if result.get("duration_ms"):
                duration_sec = result["duration_ms"] / 1000
                console.print(f"  Duration: {duration_sec:.1f} seconds")
            
            if result.get("num_turns"):
                console.print(f"  Turns: {result['num_turns']}")
            
            if result.get("total_cost_usd"):
                console.print(f"  Cost: ${result['total_cost_usd']:.4f}")
            
            if result.get("tool_uses"):
                tool_count = len(result["tool_uses"])
                console.print(f"  Tools used: {tool_count} times")
            
            console.print("\n[bold]Next steps:[/bold]")
            console.print("  1. Review changes: git log --oneline")
            console.print("  2. If satisfied: git push --force-with-lease")
            console.print(f"  3. To restore: git reset --hard {backup_branch}")
        else:
            console.print("\n[bold red]✗ Failed to apply plan[/bold red]")
            if result.get("errors"):
                console.print("\nErrors encountered:")
                for error in result["errors"]:
                    console.print(f"  • {error}")
            console.print(f"\n[yellow]Tip: Restore from backup with:[/yellow]")
            console.print(f"  git reset --hard {backup_branch}")
            sys.exit(1)
        
    except FileNotFoundError:
        console.print(f"[bold red]✗ Error:[/bold red] Plan file not found: {plan}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]✗ Error:[/bold red] Invalid plan file format")
        console.print(f"  {str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option(
    "--repo-url",
    required=True,
    help="Git repository URL (HTTPS or SSH)",
)
@click.option(
    "--branch",
    required=True,
    help="Branch to checkout",
)
@click.option(
    "--initial-commit",
    required=True,
    help="Starting commit SHA (older commit)",
)
@click.option(
    "--final-commit",
    required=True,
    help="Ending commit SHA (newer commit)",
)
@click.option(
    "--output-plan",
    type=click.Path(path_type=Path),
    required=True,
    help="Path to save the generated plan JSON file (absolute or relative)",
)
@click.option(
    "--target-dir",
    type=click.Path(path_type=Path),
    help="Directory where repository will be cloned (default: temp directory)",
)
@click.option(
    "--prompt",
    help="Custom instructions for how to rewrite history",
)
@click.option(
    "--conversation",
    type=click.Path(exists=True, path_type=Path),
    help="JSONL file containing conversation history for context",
)
@click.option(
    "--model",
    help="Claude model to use (e.g., claude-3-opus-20240229)",
)
@click.option(
    "--cleanup",
    is_flag=True,
    help="Clean up temporary directory after completion (default: keep for apply-plan)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def process(
    repo_url: str,
    branch: str,
    initial_commit: str,
    final_commit: str,
    output_plan: Path,
    target_dir: Optional[Path],
    prompt: Optional[str],
    conversation: Optional[Path],
    model: Optional[str],
    cleanup: bool,
    verbose: bool,
):
    """Process complete workflow: clone, analyze, and generate rewrite plan.
    
    This command automates the entire git history rewriting workflow:
    1. Clones the repository
    2. Validates the commit range
    3. Loads conversation context (if provided)
    4. Generates a rewrite plan using Claude
    5. Saves the plan to a JSON file
    
    Examples:
    
        git-history-rewriter process --repo-url https://github.com/user/repo.git --branch main --initial-commit HEAD~10 --final-commit HEAD --output-plan rewrite.json
        
        git-history-rewriter process --repo-url git@github.com:org/repo.git --branch develop --initial-commit abc123 --final-commit def456 --prompt "Squash WIP commits" --output-plan plan.json
    """
    from .workflow import RewriteWorkflow
    
    try:
        workflow = RewriteWorkflow(verbose=verbose)
        
        plan = workflow.process(
            repo_url=repo_url,
            branch=branch,
            initial_commit=initial_commit,
            final_commit=final_commit,
            output_plan=output_plan,
            target_dir=target_dir,
            prompt=prompt,
            conversation_file=conversation,
            model=model,
            cleanup=cleanup
        )
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()