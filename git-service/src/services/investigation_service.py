"""Service for orchestrating issue investigations."""

import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from ..models import (
    IssueInvestigationRequest,
    IssueInvestigationResponse,
    InvestigationProgress,
    CommitAnalysis,
    CommitSummary
)
from ..agents.issue_investigator import IssueInvestigatorAgent
from repository.mongo_client import MongoClientService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InvestigationService:
    """Service for managing issue investigations."""
    
    def __init__(self, mongo_client: MongoClientService):
        """Initialize the investigation service.
        
        Args:
            mongo_client: MongoDB client service
        """
        self.mongo_client = mongo_client
        self.active_investigations = {}
        self.investigation_results = {}
        
    async def start_investigation(
        self,
        request: IssueInvestigationRequest,
        progress_callback=None
    ) -> str:
        """Start a new issue investigation.
        
        Args:
            request: Investigation request
            progress_callback: Optional callback for progress updates
            
        Returns:
            Investigation ID
        """
        investigation_id = str(uuid.uuid4())
        
        # Store investigation metadata
        self.active_investigations[investigation_id] = {
            "request": request,
            "status": "initializing",
            "start_time": datetime.now(),
            "progress_callback": progress_callback
        }
        
        # Start investigation in background
        asyncio.create_task(
            self._run_investigation(investigation_id, request, progress_callback)
        )
        
        logger.info(f"Started investigation {investigation_id}")
        return investigation_id
    
    async def _run_investigation(
        self,
        investigation_id: str,
        request: IssueInvestigationRequest,
        progress_callback=None
    ):
        """Run the investigation process.
        
        Args:
            investigation_id: Unique investigation ID
            request: Investigation request
            progress_callback: Optional callback for progress updates
        """
        start_time = datetime.now()
        
        try:
            # Update status
            self.active_investigations[investigation_id]["status"] = "in_progress"
            
            # Create progress callback wrapper
            async def wrapped_progress_callback(update: Dict[str, Any]):
                progress = InvestigationProgress(
                    investigation_id=investigation_id,
                    stage=self._get_stage_from_step(update.get("step", 0)),
                    progress_percentage=update.get("percentage", 0),
                    current_action=update.get("message", ""),
                    commits_found=update.get("details", {}).get("commits_found", 0),
                    timestamp=datetime.now()
                )
                
                if progress_callback:
                    await progress_callback(progress)
                
                # Store latest progress
                self.active_investigations[investigation_id]["latest_progress"] = progress
            
            # Create and run the investigator agent
            investigator = IssueInvestigatorAgent(
                mongo_client=self.mongo_client,
                verbose=True
            )
            
            result = await investigator.run(
                request=request,
                progress_callback=wrapped_progress_callback
            )
            
            # Process results
            if result["success"]:
                investigation_result = result["result"]
                
                # Calculate processing time
                processing_time_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )
                
                # Create response
                response = IssueInvestigationResponse(
                    investigation_id=investigation_id,
                    status="completed",
                    root_cause_commits=investigation_result.get("root_cause_commits", []),
                    confidence_score=investigation_result.get("confidence_score", 0.0),
                    related_commits=investigation_result.get("related_commits", []),
                    pattern_analysis=investigation_result.get("pattern_analysis", ""),
                    suggested_fixes=investigation_result.get("suggested_fixes", []),
                    affected_components=investigation_result.get("affected_components", []),
                    total_commits_analyzed=investigation_result.get("total_commits_analyzed", 0),
                    search_strategy_used=investigation_result.get("search_strategy_used", ""),
                    processing_time_ms=processing_time_ms
                )
                
                # Store results
                self.investigation_results[investigation_id] = response
                self.active_investigations[investigation_id]["status"] = "completed"
                
                # Log to MongoDB
                self._log_investigation_to_db(investigation_id, request, response)
                
                logger.info(f"Investigation {investigation_id} completed successfully")
                
            else:
                # Handle failure
                error_message = result.get("error", "Unknown error occurred")
                
                response = IssueInvestigationResponse(
                    investigation_id=investigation_id,
                    status="failed",
                    root_cause_commits=[],
                    confidence_score=0.0,
                    related_commits=[],
                    pattern_analysis="",
                    suggested_fixes=[],
                    affected_components=[],
                    total_commits_analyzed=0,
                    search_strategy_used="",
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                    error=error_message
                )
                
                self.investigation_results[investigation_id] = response
                self.active_investigations[investigation_id]["status"] = "failed"
                
                logger.error(f"Investigation {investigation_id} failed: {error_message}")
                
        except Exception as e:
            logger.error(f"Investigation {investigation_id} crashed: {str(e)}")
            
            # Create error response
            response = IssueInvestigationResponse(
                investigation_id=investigation_id,
                status="failed",
                root_cause_commits=[],
                confidence_score=0.0,
                related_commits=[],
                pattern_analysis="",
                suggested_fixes=[],
                affected_components=[],
                total_commits_analyzed=0,
                search_strategy_used="",
                processing_time_ms=int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
                error=str(e)
            )
            
            self.investigation_results[investigation_id] = response
            self.active_investigations[investigation_id]["status"] = "failed"
    
    def _get_stage_from_step(self, step: int) -> str:
        """Convert step number to stage name.
        
        Args:
            step: Step number (1-5)
            
        Returns:
            Stage name
        """
        stages = {
            0: "initializing",
            1: "searching",
            2: "searching",
            3: "analyzing",
            4: "ranking",
            5: "complete"
        }
        return stages.get(step, "in_progress")
    
    def _log_investigation_to_db(
        self,
        investigation_id: str,
        request: IssueInvestigationRequest,
        response: IssueInvestigationResponse
    ):
        """Log investigation results to MongoDB.
        
        Args:
            investigation_id: Investigation ID
            request: Original request
            response: Investigation response
        """
        try:
            log_entry = {
                "type": "issue_investigation",
                "investigation_id": investigation_id,
                "request": {
                    "issue_description": request.issue_description,
                    "severity": request.severity,
                    "affected_files": request.affected_files,
                    "error_messages": request.error_messages
                },
                "results": {
                    "status": response.status,
                    "confidence_score": response.confidence_score,
                    "root_cause_commits": [
                        {
                            "hash": c.commit_hash,
                            "likelihood": c.likelihood_score,
                            "message": c.message
                        }
                        for c in response.root_cause_commits[:3]  # Top 3
                    ],
                    "suggested_fixes": response.suggested_fixes[:3],  # Top 3
                    "processing_time_ms": response.processing_time_ms
                },
                "timestamp": datetime.now()
            }
            
            self.mongo_client.insert_log(log_entry)
            
        except Exception as e:
            logger.error(f"Failed to log investigation to DB: {str(e)}")
    
    async def get_investigation_status(
        self, investigation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the status of an investigation.
        
        Args:
            investigation_id: Investigation ID
            
        Returns:
            Status dictionary or None if not found
        """
        if investigation_id in self.active_investigations:
            investigation = self.active_investigations[investigation_id]
            
            status_info = {
                "investigation_id": investigation_id,
                "status": investigation["status"],
                "start_time": investigation["start_time"].isoformat(),
                "request": investigation["request"].model_dump()
            }
            
            # Add progress if available
            if "latest_progress" in investigation:
                status_info["latest_progress"] = investigation["latest_progress"].model_dump()
            
            # Add results if completed
            if investigation_id in self.investigation_results:
                status_info["results"] = self.investigation_results[investigation_id].model_dump()
            
            return status_info
        
        return None
    
    async def get_investigation_results(
        self, investigation_id: str
    ) -> Optional[IssueInvestigationResponse]:
        """Get the results of a completed investigation.
        
        Args:
            investigation_id: Investigation ID
            
        Returns:
            Investigation response or None if not found/not completed
        """
        return self.investigation_results.get(investigation_id)
    
    def list_investigations(self) -> List[Dict[str, Any]]:
        """List all investigations.
        
        Returns:
            List of investigation summaries
        """
        investigations = []
        
        for inv_id, inv_data in self.active_investigations.items():
            investigations.append({
                "investigation_id": inv_id,
                "status": inv_data["status"],
                "start_time": inv_data["start_time"].isoformat(),
                "issue_description": inv_data["request"].issue_description[:100]  # First 100 chars
            })
        
        return investigations