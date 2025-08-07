"""Example client for testing the issue investigation API."""

import asyncio
import json
import aiohttp
import websockets
from datetime import datetime
from typing import Optional


class InvestigationClient:
    """Client for interacting with the investigation API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the client.
        
        Args:
            base_url: Base URL of the git-service API
        """
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws")
    
    async def investigate_issue(self, issue_data: dict) -> dict:
        """Start an issue investigation via REST API.
        
        Args:
            issue_data: Issue investigation request data
            
        Returns:
            Response from the API
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/investigate/issue",
                json=issue_data
            ) as response:
                return await response.json()
    
    async def get_investigation_status(self, investigation_id: str) -> dict:
        """Get the status of an investigation.
        
        Args:
            investigation_id: Investigation ID
            
        Returns:
            Investigation status
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/investigate/{investigation_id}"
            ) as response:
                return await response.json()
    
    async def get_investigation_results(self, investigation_id: str) -> dict:
        """Get the results of a completed investigation.
        
        Args:
            investigation_id: Investigation ID
            
        Returns:
            Investigation results
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/investigate/{investigation_id}/results"
            ) as response:
                return await response.json()
    
    async def investigate_with_websocket(self, issue_data: dict):
        """Investigate an issue using WebSocket for real-time updates.
        
        Args:
            issue_data: Issue investigation request data
        """
        uri = f"{self.ws_url}/ws/investigate"
        
        async with websockets.connect(uri) as websocket:
            # Send investigation request
            await websocket.send(json.dumps(issue_data))
            
            # Listen for updates
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data["type"] == "started":
                        print(f"✅ Investigation started: {data['investigation_id']}")
                    
                    elif data["type"] == "progress":
                        progress = data["data"]
                        print(f"📊 Progress: {progress['stage']} - {progress['progress_percentage']}%")
                        print(f"   Current: {progress['current_action']}")
                        if progress.get('commits_found'):
                            print(f"   Commits found: {progress['commits_found']}")
                    
                    elif data["type"] == "completed":
                        results = data["data"]
                        print("\n✅ Investigation Complete!")
                        self._print_results(results)
                        break
                    
                    elif data["type"] == "failed":
                        print(f"❌ Investigation failed: {data.get('error', 'Unknown error')}")
                        break
                    
                    elif data["type"] == "error":
                        print(f"❌ Error: {data.get('error', 'Unknown error')}")
                        break
                        
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
    
    def _print_results(self, results: dict):
        """Pretty print investigation results.
        
        Args:
            results: Investigation results dictionary
        """
        print("\n" + "="*60)
        print("INVESTIGATION RESULTS")
        print("="*60)
        
        print(f"\n📈 Confidence Score: {results.get('confidence_score', 0):.2%}")
        print(f"📊 Total Commits Analyzed: {results.get('total_commits_analyzed', 0)}")
        print(f"⚙️ Search Strategy: {results.get('search_strategy_used', 'N/A')}")
        print(f"⏱️ Processing Time: {results.get('processing_time_ms', 0)}ms")
        
        # Root cause commits
        print("\n🎯 ROOT CAUSE COMMITS (Most Likely):")
        for i, commit in enumerate(results.get('root_cause_commits', [])[:5], 1):
            print(f"\n  {i}. Commit: {commit['commit_hash'][:8]}")
            print(f"     Likelihood: {commit['likelihood_score']:.2%}")
            print(f"     Message: {commit['message']}")
            print(f"     Reasoning: {commit['reasoning']}")
            print(f"     Risk Factors: {', '.join(commit.get('risk_factors', []))}")
            print(f"     Blast Radius: {commit.get('blast_radius', 'unknown')}")
        
        # Pattern analysis
        print(f"\n🔍 PATTERN ANALYSIS:")
        print(f"   {results.get('pattern_analysis', 'No patterns identified')}")
        
        # Suggested fixes
        print("\n💡 SUGGESTED FIXES:")
        for i, fix in enumerate(results.get('suggested_fixes', []), 1):
            print(f"  {i}. {fix}")
        
        # Affected components
        if results.get('affected_components'):
            print("\n🔧 AFFECTED COMPONENTS:")
            for component in results['affected_components']:
                print(f"  • {component}")
        
        print("\n" + "="*60)


async def main():
    """Main function to demonstrate the investigation client."""
    
    client = InvestigationClient()
    
    # Example 1: Simple investigation
    print("\n" + "="*60)
    print("EXAMPLE 1: Simple Issue Investigation")
    print("="*60)
    
    simple_issue = {
        "issue_description": "Login fails with 500 error after recent deployment",
        "error_messages": ["TypeError: Cannot read property 'id' of undefined"],
        "severity": "high"
    }
    
    print("\n🔍 Investigating: Login fails with 500 error")
    print("📝 Error: TypeError: Cannot read property 'id' of undefined")
    
    # Start investigation
    response = await client.investigate_issue(simple_issue)
    print(f"\n✅ Investigation started: {response['investigation_id']}")
    
    # Poll for results
    investigation_id = response['investigation_id']
    for _ in range(30):  # Poll for up to 30 seconds
        await asyncio.sleep(1)
        status = await client.get_investigation_status(investigation_id)
        
        if status['status'] == 'completed':
            print("✅ Investigation completed!")
            results = await client.get_investigation_results(investigation_id)
            client._print_results(results)
            break
        elif status['status'] == 'failed':
            print(f"❌ Investigation failed: {status.get('error', 'Unknown error')}")
            break
        else:
            print(f"⏳ Status: {status['status']}...")
    
    # Example 2: Complex investigation with WebSocket
    print("\n" + "="*60)
    print("EXAMPLE 2: Complex Investigation with Real-time Updates")
    print("="*60)
    
    complex_issue = {
        "issue_description": "Database connection pool exhausted causing application crashes",
        "error_messages": [
            "ConnectionPoolError: No available connections",
            "TimeoutError: Connection timeout after 30s"
        ],
        "affected_files": ["src/db/connection.py", "src/api/handlers.py"],
        "severity": "critical",
        "investigation_depth": "exhaustive",
        "max_commits_to_analyze": 100
    }
    
    print("\n🔍 Investigating: Database connection pool exhaustion")
    print("📝 Using WebSocket for real-time updates...")
    
    await client.investigate_with_websocket(complex_issue)
    
    # Example 3: Time-bounded investigation
    print("\n" + "="*60)
    print("EXAMPLE 3: Time-bounded Investigation")
    print("="*60)
    
    time_bounded_issue = {
        "issue_description": "Performance degradation in search functionality",
        "time_range": {
            "start": "2024-01-15T00:00:00Z",
            "end": "2024-01-20T23:59:59Z"
        },
        "affected_files": ["src/search/engine.py"],
        "severity": "medium",
        "investigation_depth": "quick"
    }
    
    print("\n🔍 Investigating: Performance degradation in search")
    print("📅 Time range: 2024-01-15 to 2024-01-20")
    
    await client.investigate_with_websocket(time_bounded_issue)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("GIT SERVICE ISSUE INVESTIGATION CLIENT")
    print("="*60)
    print("\nThis client demonstrates the issue investigation API.")
    print("Make sure the git-service is running on localhost:8000")
    print("and MongoDB is configured with commit data.\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Client interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        print("Make sure the git-service is running and MongoDB is configured")