/**
 * API client for connecting to Git Service backend
 */

const API_BASE_URL = 'http://localhost:8000';

export interface Commit {
  _id: string;
  commit_hash: string;
  message: string;
  author: string;
  prompt: string;
  timestamp: string;
  files_changed: string[];
  created_at: string;
}

export interface SearchResult extends Commit {
  score: number;
}

export class GitServiceAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<{ running: boolean }> {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }

  /**
   * Get recent commits from MongoDB
   */
  async getRecentCommits(limit: number = 10): Promise<Commit[]> {
    const response = await fetch(`${this.baseUrl}/commits/recent?limit=${limit}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch commits: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Search commits using semantic similarity
   */
  async searchCommits(
    query: string, 
    limit: number = 5, 
    minScore: number = 0.7
  ): Promise<SearchResult[]> {
    const response = await fetch(`${this.baseUrl}/commits/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query_text: query,
        limit,
        min_score: minScore,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`);
    }
    
    return response.json();
  }

  /**
   * Get commit by hash
   */
  async getCommitByHash(commitHash: string): Promise<Commit | null> {
    const response = await fetch(`${this.baseUrl}/commits/${commitHash}`);
    if (response.status === 404) {
      return null;
    }
    if (!response.ok) {
      throw new Error(`Failed to fetch commit: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Start a new session
   */
  async startSession(userPrompt: string): Promise<{ message: string; session_id: string }> {
    const response = await fetch(`${this.baseUrl}/session/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_prompt: userPrompt,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to start session: ${response.statusText}`);
    }
    
    return response.json();
  }

  /**
   * End a session
   */
  async endSession(sessionId: string, finalOutput: string, status: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/session/end`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        final_output: finalOutput,
        status,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to end session: ${response.statusText}`);
    }
  }
}

// Singleton instance
export const gitServiceAPI = new GitServiceAPI();