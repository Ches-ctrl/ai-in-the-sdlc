"""Issue Investigation Agent using Claude/Anthropic API."""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import anthropic
from dotenv import load_dotenv

from .agent_base import AgentBase, ProgressReporter
from ..models import (
    CommitAnalysis, CommitSummary, IssueInvestigationRequest
)

load_dotenv()


class IssueInvestigatorAgent(AgentBase):
    """Agent that investigates issues to find root cause commits."""
    
    def __init__(self, mongo_client, verbose: bool = False):
        """Initialize the issue investigator agent.
        
        Args:
            mongo_client: MongoDB client service instance
            verbose: Enable verbose logging
        """
        super().__init__(name="IssueInvestigator", verbose=verbose)
        self.mongo_client = mongo_client
        self.anthropic_client = anthropic.AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY"))
        )
        self.progress_reporter = None
        
    async def execute(
        self,
        request: IssueInvestigationRequest,
        progress_callback=None
    ) -> Dict[str, Any]:
        """Execute the issue investigation.
        
        Args:
            request: Investigation request with issue details
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary containing investigation results
        """
        self.progress_reporter = ProgressReporter(
            total_steps=5,
            callback=progress_callback
        )
        
        try:
            # Step 1: Search for similar commits
            await self.progress_reporter.update(
                1, "Searching for similar commits in database"
            )
            similar_commits = await self._search_similar_commits(request)
            
            # Step 2: Get recent commits for context
            await self.progress_reporter.update(
                2, "Gathering recent commits for temporal context",
                {"commits_found": len(similar_commits)}
            )
            recent_commits = await self._get_recent_commits(request)
            
            # Step 3: Analyze commits with Claude
            await self.progress_reporter.update(
                3, "Analyzing commits with AI to identify patterns",
                {"total_commits": len(similar_commits) + len(recent_commits)}
            )
            analysis_result = await self._analyze_commits_with_claude(
                request, similar_commits, recent_commits
            )
            
            # Step 4: Rank and score commits
            await self.progress_reporter.update(
                4, "Ranking commits by likelihood of causing issue"
            )
            ranked_commits = await self._rank_commits(analysis_result)
            
            # Step 5: Generate recommendations
            await self.progress_reporter.update(
                5, "Generating fix recommendations"
            )
            recommendations = await self._generate_recommendations(
                request, ranked_commits, analysis_result
            )
            
            return {
                "root_cause_commits": ranked_commits[:5],  # Top 5 most likely
                "related_commits": similar_commits[:10],
                "pattern_analysis": analysis_result.get("pattern_analysis", ""),
                "suggested_fixes": recommendations.get("fixes", []),
                "affected_components": recommendations.get("components", []),
                "confidence_score": analysis_result.get("confidence", 0.0),
                "total_commits_analyzed": len(similar_commits) + len(recent_commits),
                "search_strategy_used": "vector_similarity_and_temporal"
            }
            
        except Exception as e:
            self._log(f"Investigation failed: {str(e)}", "error")
            raise
    
    async def _search_similar_commits(
        self, request: IssueInvestigationRequest
    ) -> List[CommitSummary]:
        """Search for commits similar to the issue description.
        
        Args:
            request: Investigation request
            
        Returns:
            List of similar commits
        """
        try:
            # Build search query from issue description and error messages
            search_query = request.issue_description
            if request.error_messages:
                search_query += " " + " ".join(request.error_messages)
            
            # Use vector similarity search
            similar_commits = self.mongo_client.get_commits_by_similarity(
                query_text=search_query,
                limit=request.max_commits_to_analyze or 50,
                min_score=0.5 if request.investigation_depth == "exhaustive" else 0.7
            )
            
            # Convert to CommitSummary objects
            commit_summaries = []
            for commit in similar_commits:
                commit_summaries.append(CommitSummary(
                    commit_hash=commit.get("commit_hash", ""),
                    message=commit.get("message", ""),
                    author=commit.get("author", ""),
                    timestamp=commit.get("timestamp", datetime.now()),
                    files_changed=commit.get("files_changed", []),
                    similarity_score=commit.get("score", 0.0)
                ))
            
            self._log(f"Found {len(commit_summaries)} similar commits")
            return commit_summaries
            
        except Exception as e:
            self._log(f"Error searching similar commits: {str(e)}", "error")
            return []
    
    async def _get_recent_commits(
        self, request: IssueInvestigationRequest
    ) -> List[CommitSummary]:
        """Get recent commits for temporal context.
        
        Args:
            request: Investigation request
            
        Returns:
            List of recent commits
        """
        try:
            # Get recent commits
            recent_commits = self.mongo_client.get_recent_commits(
                limit=20 if request.investigation_depth == "quick" else 50
            )
            
            # Filter by time range if provided
            commit_summaries = []
            for commit in recent_commits:
                commit_time = commit.get("timestamp", datetime.now())
                
                # Check time range
                if request.time_range:
                    if request.time_range.start and commit_time < request.time_range.start:
                        continue
                    if request.time_range.end and commit_time > request.time_range.end:
                        continue
                
                # Check affected files
                if request.affected_files:
                    files_changed = commit.get("files_changed", [])
                    if not any(f in files_changed for f in request.affected_files):
                        continue
                
                commit_summaries.append(CommitSummary(
                    commit_hash=commit.get("commit_hash", ""),
                    message=commit.get("message", ""),
                    author=commit.get("author", ""),
                    timestamp=commit_time,
                    files_changed=commit.get("files_changed", [])
                ))
            
            self._log(f"Found {len(commit_summaries)} recent commits in range")
            return commit_summaries
            
        except Exception as e:
            self._log(f"Error getting recent commits: {str(e)}", "error")
            return []
    
    async def _analyze_commits_with_claude(
        self,
        request: IssueInvestigationRequest,
        similar_commits: List[CommitSummary],
        recent_commits: List[CommitSummary]
    ) -> Dict[str, Any]:
        """Analyze commits using Claude to identify patterns and root causes.
        
        Args:
            request: Investigation request
            similar_commits: Commits similar to the issue
            recent_commits: Recent commits for context
            
        Returns:
            Analysis results dictionary
        """
        try:
            # Prepare commit data for Claude
            commits_data = {
                "similar_commits": [
                    {
                        "hash": c.commit_hash,
                        "message": c.message,
                        "files": c.files_changed,
                        "similarity": c.similarity_score
                    }
                    for c in similar_commits[:20]  # Limit for context window
                ],
                "recent_commits": [
                    {
                        "hash": c.commit_hash,
                        "message": c.message,
                        "files": c.files_changed,
                        "timestamp": c.timestamp.isoformat()
                    }
                    for c in recent_commits[:20]
                ]
            }
            
            # Build prompt for Claude
            prompt = f"""You are a git forensics expert investigating a software issue.

Issue Description: {request.issue_description}
Error Messages: {json.dumps(request.error_messages or [])}
Affected Files: {json.dumps(request.affected_files or [])}
Severity: {request.severity}

Similar Commits (ranked by semantic similarity to the issue):
{json.dumps(commits_data['similar_commits'], indent=2)}

Recent Commits (temporal context):
{json.dumps(commits_data['recent_commits'], indent=2)}

Please analyze these commits and provide:
1. Which commits are most likely to have caused this issue (with likelihood scores 0-1)
2. Pattern analysis - what patterns do you see across these commits
3. Risk factors for each suspicious commit
4. Your confidence level (0-1) in this analysis

Return your analysis as a JSON object with this structure:
{{
    "suspicious_commits": [
        {{
            "hash": "commit_hash",
            "likelihood": 0.0-1.0,
            "reasoning": "why this commit is suspicious",
            "risk_factors": ["factor1", "factor2"],
            "matching_indicators": ["what matched"],
            "blast_radius": "low/medium/high/critical"
        }}
    ],
    "pattern_analysis": "patterns you identified",
    "confidence": 0.0-1.0
}}"""

            # Call Claude API
            response = await self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse Claude's response
            response_text = response.content[0].text
            
            # Try to extract JSON from response
            try:
                # Look for JSON in the response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    # Fallback if no JSON found
                    analysis = {
                        "suspicious_commits": [],
                        "pattern_analysis": response_text,
                        "confidence": 0.5
                    }
            except json.JSONDecodeError:
                self._log("Could not parse JSON from Claude response", "warning")
                analysis = {
                    "suspicious_commits": [],
                    "pattern_analysis": response_text,
                    "confidence": 0.5
                }
            
            # Merge commit data with analysis
            for suspicious in analysis.get("suspicious_commits", []):
                # Find full commit data
                commit_hash = suspicious.get("hash")
                for commit in similar_commits + recent_commits:
                    if commit.commit_hash == commit_hash:
                        suspicious["message"] = commit.message
                        suspicious["author"] = commit.author
                        suspicious["timestamp"] = commit.timestamp.isoformat()
                        suspicious["files_changed"] = commit.files_changed
                        break
            
            return analysis
            
        except Exception as e:
            self._log(f"Error analyzing with Claude: {str(e)}", "error")
            return {
                "suspicious_commits": [],
                "pattern_analysis": "Analysis failed",
                "confidence": 0.0
            }
    
    async def _rank_commits(self, analysis_result: Dict[str, Any]) -> List[CommitAnalysis]:
        """Rank commits by likelihood of causing the issue.
        
        Args:
            analysis_result: Analysis results from Claude
            
        Returns:
            List of ranked CommitAnalysis objects
        """
        commit_analyses = []
        
        for suspicious in analysis_result.get("suspicious_commits", []):
            try:
                # Get full commit data from database
                commit_data = self.mongo_client.get_commit_by_hash(
                    suspicious.get("hash", "")
                )
                
                commit_analyses.append(CommitAnalysis(
                    commit_hash=suspicious.get("hash", ""),
                    likelihood_score=suspicious.get("likelihood", 0.0),
                    reasoning=suspicious.get("reasoning", ""),
                    matching_indicators=suspicious.get("matching_indicators", []),
                    message=suspicious.get("message", commit_data.get("message", "") if commit_data else ""),
                    author=suspicious.get("author", commit_data.get("author", "") if commit_data else ""),
                    timestamp=datetime.fromisoformat(suspicious.get("timestamp", datetime.now().isoformat())),
                    files_changed=suspicious.get("files_changed", []),
                    original_prompt=commit_data.get("prompt") if commit_data else None,
                    risk_factors=suspicious.get("risk_factors", []),
                    blast_radius=suspicious.get("blast_radius", "medium")
                ))
            except Exception as e:
                self._log(f"Error processing commit {suspicious.get('hash')}: {str(e)}", "warning")
                continue
        
        # Sort by likelihood score
        commit_analyses.sort(key=lambda x: x.likelihood_score, reverse=True)
        
        return commit_analyses
    
    async def _generate_recommendations(
        self,
        request: IssueInvestigationRequest,
        ranked_commits: List[CommitAnalysis],
        analysis_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate fix recommendations based on the investigation.
        
        Args:
            request: Original investigation request
            ranked_commits: Ranked commits by likelihood
            analysis_result: Analysis results
            
        Returns:
            Dictionary with recommendations
        """
        try:
            if not ranked_commits:
                return {
                    "fixes": ["No specific commits identified as root cause"],
                    "components": []
                }
            
            # Get top suspect commit
            top_commit = ranked_commits[0]
            
            # Build prompt for recommendations
            prompt = f"""Based on this git forensics investigation, provide specific fix recommendations.

Issue: {request.issue_description}
Most Likely Cause: Commit {top_commit.commit_hash}
Commit Message: {top_commit.message}
Files Changed: {json.dumps(top_commit.files_changed)}
Risk Factors: {json.dumps(top_commit.risk_factors)}
Reasoning: {top_commit.reasoning}

Provide:
1. Specific fixes to resolve the issue (3-5 actionable steps)
2. Affected components/modules that need attention

Return as JSON:
{{
    "fixes": ["fix1", "fix2", "fix3"],
    "components": ["component1", "component2"]
}}"""

            response = await self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = response.content[0].text
            
            # Parse response
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    recommendations = json.loads(json_match.group())
                else:
                    recommendations = {
                        "fixes": [response_text],
                        "components": []
                    }
            except json.JSONDecodeError:
                recommendations = {
                    "fixes": [response_text],
                    "components": []
                }
            
            return recommendations
            
        except Exception as e:
            self._log(f"Error generating recommendations: {str(e)}", "error")
            return {
                "fixes": ["Unable to generate specific recommendations"],
                "components": []
            }