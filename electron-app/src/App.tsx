import React, { useState, useEffect } from 'react'
import { GitBranch, GitCommit, RefreshCw, FolderOpen, Activity, MessageCircle, Send, ChevronRight, Code, Zap, Clock, User, Hash, ArrowLeft, Search, Link, Database } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card'
import { Input } from './components/ui/input'
import { StashLogo } from './components/StashLogo'
import { gitServiceAPI, type Commit, type SearchResult } from './services/api'

function App() {
  const [repoPath, setRepoPath] = useState<string>('')
  const [repoName, setRepoName] = useState<string>('No repository')
  const [repoUrl, setRepoUrl] = useState<string>('')
  const [branch, setBranch] = useState<string>('--')
  const [commits, setCommits] = useState<Commit[]>([])
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [isConnected, setIsConnected] = useState<boolean>(false)
  const [stats, setStats] = useState({
    commitsToday: 0,
    linesChanged: 0,
    activeBranches: 0
  })
  const [chatMessages, setChatMessages] = useState<Array<{id: string, type: 'user' | 'assistant', content: string, timestamp: Date, searchResults?: SearchResult[]}>>([])
  const [chatInput, setChatInput] = useState<string>('')
  const [showChat, setShowChat] = useState<boolean>(false)
  const [selectedCommit, setSelectedCommit] = useState<Commit | null>(null)
  const [currentView, setCurrentView] = useState<'overview' | 'commits' | 'commit-detail' | 'analysis'>('overview')
  const [analysisStatus, setAnalysisStatus] = useState<'idle' | 'analyzing' | 'complete'>('idle')
  const [isSearching, setIsSearching] = useState<boolean>(false)

  // Check backend connection on startup
  useEffect(() => {
    const checkConnection = async () => {
      try {
        console.log('Checking backend connection...')
        const health = await gitServiceAPI.healthCheck()
        console.log('Health check response:', health)
        setIsConnected(true)
        console.log('Loading recent commits...')
        await loadRecentCommits()
        console.log('Connection established successfully!')
      } catch (error) {
        console.error('Backend not available:', error)
        setIsConnected(false)
      }
    }
    
    checkConnection()
  }, [])

  // Auto-refresh commits every 30 seconds when connected
  useEffect(() => {
    if (!isConnected) return
    
    const interval = setInterval(async () => {
      await loadRecentCommits()
    }, 30000)
    
    return () => clearInterval(interval)
  }, [isConnected])

  const loadRecentCommits = async () => {
    try {
      const recentCommits = await gitServiceAPI.getRecentCommits(10)
      console.log('Loaded commits:', recentCommits)
      setCommits(recentCommits)
      
      // Update stats based on real data
      const today = new Date().toDateString()
      const commitsToday = recentCommits.filter(commit => 
        new Date(commit.timestamp).toDateString() === today
      ).length
      
      setStats({
        commitsToday,
        linesChanged: recentCommits.reduce((acc, commit) => acc + commit.files_changed.length * 20, 0), // Rough estimate
        activeBranches: 1 // Would need separate API for branch info
      })
    } catch (error) {
      console.error('Failed to load commits:', error)
    }
  }

  const connectRepository = async () => {
    if (!repoUrl.trim()) return
    
    // Extract repo name from URL
    const urlParts = repoUrl.split('/')
    const name = urlParts[urlParts.length - 1].replace('.git', '')
    setRepoName(name)
    setRepoPath(repoUrl)
    
    // Load commits from backend
    await loadRecentCommits()
    setCurrentView('commits')
  }
  
  const openRepository = async () => {
    console.log('Open repository')
    await loadRecentCommits()
    setCurrentView('commits')
  }

  const refreshRepository = async () => {
    console.log('Refresh repository')
    await loadRecentCommits()
  }

  const sendChatMessage = async () => {
    if (!chatInput.trim() || isSearching) return
    
    const userMessage = {
      id: Date.now().toString(),
      type: 'user' as const,
      content: chatInput,
      timestamp: new Date()
    }
    
    setChatMessages(prev => [...prev, userMessage])
    const query = chatInput
    setChatInput('')
    setIsSearching(true)
    
    try {
      // Perform semantic search
      const results = await gitServiceAPI.searchCommits(query, 5, 0.6)
      
      let responseContent
      if (results.length === 0) {
        responseContent = `I couldn't find any commits related to "${query}". Try rephrasing your search or being more specific.`
      } else {
        responseContent = `Found ${results.length} relevant commits for "${query}":`
      }
      
      const aiResponse = {
        id: (Date.now() + 1).toString(),
        type: 'assistant' as const,
        content: responseContent,
        timestamp: new Date(),
        searchResults: results
      }
      
      setChatMessages(prev => [...prev, aiResponse])
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
      const errorResponse = {
        id: (Date.now() + 1).toString(),
        type: 'assistant' as const,
        content: `Sorry, I encountered an error while searching: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date()
      }
      setChatMessages(prev => [...prev, errorResponse])
    } finally {
      setIsSearching(false)
    }
  }

  const handleChatKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendChatMessage()
    }
  }

  const selectCommit = (commit: any) => {
    setSelectedCommit(commit)
    setCurrentView('commit-detail')
  }

  const analyzeCommit = () => {
    setAnalysisStatus('analyzing')
    setCurrentView('analysis')
    
    // Mock analysis process
    setTimeout(() => {
      setAnalysisStatus('complete')
    }, 3000)
  }

  const goBack = () => {
    if (currentView === 'commit-detail') {
      setCurrentView('commits')
    } else if (currentView === 'analysis') {
      setCurrentView('commit-detail')
    } else if (currentView === 'commits') {
      setCurrentView('overview')
    }
  }

  return (
    <div className="flex h-screen bg-background">
      <div className="w-64 border-r bg-card/50 p-4 space-y-4">
        <div className="pt-8 pb-4 border-b" style={{ WebkitAppRegion: 'drag' } as any}>
          <div className="flex items-center gap-2" style={{ WebkitAppRegion: 'no-drag' } as any}>
            <StashLogo width={20} height={6} className="text-muted-foreground" />
            <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
              Git Daddy
            </span>
          </div>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Current Repository</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium">{repoName}</p>
            <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
              <GitBranch className="w-3 h-3" />
              {branch}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Statistics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground">Commits today</span>
              <span className="text-sm font-mono">{stats.commitsToday}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground">Lines changed</span>
              <span className="text-sm font-mono">{stats.linesChanged}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground">Active branches</span>
              <span className="text-sm font-mono">{stats.activeBranches}</span>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-3">
          <div className="space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-4 h-4" />
              <span className="text-xs font-medium">Backend Status</span>
              <div className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`} />
            </div>
            <Input
              placeholder="GitHub repository URL"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              className="text-xs"
            />
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full justify-start"
              onClick={connectRepository}
              disabled={!repoUrl.trim()}
            >
              <Link className="w-4 h-4 mr-2" />
              Connect Repository
            </Button>
          </div>
          
          <div className="space-y-2">
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full justify-start"
              onClick={openRepository}
            >
              <FolderOpen className="w-4 h-4 mr-2" />
              View Commits
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full justify-start"
              onClick={refreshRepository}
              disabled={!isConnected}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        <div className="border-b p-4 flex justify-between items-center" style={{ WebkitAppRegion: 'drag' } as any}>
          <div className="flex items-center gap-3" style={{ WebkitAppRegion: 'no-drag' } as any}>
            {currentView !== 'overview' && (
              <Button variant="ghost" size="sm" onClick={goBack}>
                <ArrowLeft className="w-4 h-4" />
              </Button>
            )}
            <h1 className="text-lg font-semibold">
              {currentView === 'overview' && 'Repository Overview'}
              {currentView === 'commits' && 'Commit History'}
              {currentView === 'commit-detail' && 'Commit Details'}
              {currentView === 'analysis' && 'AI Analysis'}
            </h1>
          </div>
          <div className="flex items-center gap-3" style={{ WebkitAppRegion: 'no-drag' } as any}>
            <Button 
              variant={showChat ? "default" : "outline"} 
              size="sm"
              onClick={() => setShowChat(!showChat)}
              className="flex items-center gap-2"
              disabled={!isConnected}
            >
              <Search className="w-4 h-4" />
              Semantic Search
            </Button>
          </div>
        </div>

        <div className="flex-1 flex">
          <div className={`flex-1 p-6 overflow-auto transition-all duration-300 ${showChat ? 'mr-80' : ''}`}>
            {currentView === 'overview' && (
              <div className="space-y-6">
                <div className="flex flex-col items-center justify-center text-center py-12">
                  <Activity className="w-12 h-12 text-muted-foreground/50 mb-4" />
                  <h2 className="text-lg font-semibold mb-2">
                    {isConnected ? 'Ready to analyze commits' : 'Backend not connected'}
                  </h2>
                  <p className="text-sm text-muted-foreground max-w-md">
                    {isConnected 
                      ? 'Connect a GitHub repository to start tracking your commits with AI-powered analysis'
                      : 'Make sure the Git Service backend is running on localhost:8000'
                    }
                  </p>
                </div>
                
                {commits.length > 0 && (
                  <div>
                    <h3 className="text-base font-semibold mb-4 flex items-center gap-2">
                      <Clock className="w-4 h-4" />
                      Recent Activity
                    </h3>
                    <div className="space-y-2">
                      {commits.slice(0, 3).map((commit) => (
                        <Card key={commit._id} className="cursor-pointer hover:bg-accent/50" 
                              onClick={() => { setSelectedCommit(commit); setCurrentView('commit-detail'); }}>
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <p className="text-sm font-medium line-clamp-1">{commit.message}</p>
                                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                                  <span className="flex items-center gap-1">
                                    <User className="w-3 h-3" />
                                    {commit.author}
                                  </span>
                                  <span className="flex items-center gap-1">
                                    <Hash className="w-3 h-3" />
                                    {(commit.commit_hash || 'no-hash').substring(0, 7)}
                                  </span>
                                  <span>{new Date(commit.timestamp).toLocaleDateString()}</span>
                                </div>
                              </div>
                              <ChevronRight className="w-4 h-4 text-muted-foreground" />
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                    {commits.length > 3 && (
                      <Button variant="outline" size="sm" className="mt-4 w-full" onClick={() => setCurrentView('commits')}>
                        View all {commits.length} commits
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}

            {currentView === 'commits' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-semibold">Recent Commits</h3>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className={`w-2 h-2 rounded-full ${
                      isConnected ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                    {commits.length} commits loaded
                  </div>
                </div>
                {commits.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <GitCommit className="w-12 h-12 text-muted-foreground/50 mb-4" />
                    <h3 className="text-lg font-semibold mb-2">No commits found</h3>
                    <p className="text-sm text-muted-foreground">
                      {isConnected 
                        ? 'No commits are available in the database yet. Try connecting a repository or creating some commits.'
                        : 'Cannot load commits - backend not connected.'
                      }
                    </p>
                  </div>
                ) : (
                  commits.map((commit) => (
                    <Card key={commit._id} className="hover:bg-muted/30 transition-colors cursor-pointer" onClick={() => selectCommit(commit)}>
                      <CardContent className="pt-4">
                        <div className="flex justify-between items-start mb-2">
                          <div className="flex items-center gap-2">
                            <Hash className="w-3 h-3 text-muted-foreground" />
                            <code className="text-xs text-primary">{(commit.commit_hash || 'no-hash').substring(0, 7)}</code>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Clock className="w-3 h-3" />
                            {new Date(commit.timestamp).toLocaleDateString()}
                          </div>
                        </div>
                        <p className="text-sm mb-2">{commit.message}</p>
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <User className="w-3 h-3" />
                            {commit.author}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span>{commit.files_changed.length} files</span>
                            <ChevronRight className="w-4 h-4" />
                          </div>
                        </div>
                        {commit.files_changed.length > 0 && (
                          <div className="mt-2 pt-2 border-t text-xs text-muted-foreground">
                            <div className="line-clamp-1">
                              Files: {commit.files_changed.slice(0, 3).join(', ')}
                              {commit.files_changed.length > 3 && ` +${commit.files_changed.length - 3} more`}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            )}

            {currentView === 'commit-detail' && selectedCommit && (
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-base">{selectedCommit.message}</CardTitle>
                        <CardDescription className="flex items-center gap-4 mt-2">
                          <span className="flex items-center gap-1">
                            <Hash className="w-3 h-3" />
                            {selectedCommit.commit_hash || 'no-hash'}
                          </span>
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {selectedCommit.author}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(selectedCommit.timestamp).toLocaleDateString()}
                          </span>
                        </CardDescription>
                      </div>
                      <Button onClick={analyzeCommit} className="flex items-center gap-2">
                        <Zap className="w-4 h-4" />
                        Analyze with AI
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="text-center p-3 bg-muted/30 rounded">
                        <div className="text-lg font-semibold">{selectedCommit.files_changed.length}</div>
                        <div className="text-xs text-muted-foreground">Files Changed</div>
                      </div>
                      
                      {selectedCommit.prompt && (
                        <div className="p-3 bg-blue-500/10 rounded">
                          <div className="text-sm font-medium text-blue-600 mb-1">Original Prompt</div>
                          <div className="text-xs text-muted-foreground">{selectedCommit.prompt}</div>
                        </div>
                      )}
                      
                      {selectedCommit.files_changed.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-sm font-medium">Files Changed</div>
                          <div className="grid gap-2">
                            {selectedCommit.files_changed.map((file, index) => (
                              <div key={index} className="p-2 bg-muted/30 rounded text-xs font-mono">
                                {file}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Code className="w-4 h-4" />
                      Files Changed
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {['src/auth/login.js', 'src/utils/validation.js', 'tests/auth.test.js'].map((file, i) => (
                      <div key={i} className="flex justify-between items-center py-2 px-3 bg-muted/20 rounded text-sm">
                        <span className="font-mono">{file}</span>
                        <div className="flex gap-2 text-xs">
                          <span className="text-green-500">+{Math.floor(Math.random() * 20) + 1}</span>
                          <span className="text-red-500">-{Math.floor(Math.random() * 10) + 1}</span>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            )}

            {currentView === 'analysis' && (
              <div className="space-y-6">
                {analysisStatus === 'analyzing' && (
                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center text-center">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4"></div>
                        <h3 className="text-lg font-semibold mb-2">Analyzing commit...</h3>
                        <p className="text-sm text-muted-foreground">
                          Claude is analyzing the changes in commit {selectedCommit?.hash}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {analysisStatus === 'complete' && (
                  <div className="space-y-4">
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                          <Zap className="w-4 h-4 text-yellow-500" />
                          AI Analysis Results
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-medium mb-2">Issues Identified:</h4>
                            <ul className="space-y-1 text-sm text-muted-foreground ml-4">
                              <li>• Potential memory leak in authentication handler</li>
                              <li>• Missing error handling for edge cases</li>
                              <li>• Inefficient database query patterns</li>
                            </ul>
                          </div>
                          
                          <div>
                            <h4 className="font-medium mb-2">Recommended Fixes:</h4>
                            <div className="bg-muted/30 rounded p-4 font-mono text-sm">
                              <pre className="whitespace-pre-wrap">
{`// Fix memory leak by properly closing connections
const handleAuth = async (req, res) => {
  const connection = await db.connect();
  try {
    // ... existing logic
  } finally {
    await connection.close(); // Add this
  }
}`}
                              </pre>
                            </div>
                          </div>

                          <div className="flex gap-2">
                            <Button variant="outline" size="sm">
                              Copy Claude Prompt
                            </Button>
                            <Button size="sm">
                              Apply Suggested Fix
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Chat Panel */}
          <div className={`fixed top-0 right-0 h-full w-80 bg-background/95 backdrop-blur-sm border-l transform transition-transform duration-300 ${showChat ? 'translate-x-0' : 'translate-x-full'} flex flex-col`}>
            <div className="p-4 border-b">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Repository Assistant</h2>
                <Button variant="ghost" size="sm" onClick={() => setShowChat(false)}>
                  ×
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-1">Ask about your repository</p>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-auto p-4 space-y-3">
              {chatMessages.length === 0 ? (
                <div className="text-center text-muted-foreground text-sm mt-8">
                  <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>Semantic search examples:</p>
                  <div className="mt-2 space-y-1 text-xs">
                    <p className="bg-muted/50 rounded px-2 py-1 mx-4">"Which commit broke the build?"</p>
                    <p className="bg-muted/50 rounded px-2 py-1 mx-4">"Show me authentication changes"</p>
                    <p className="bg-muted/50 rounded px-2 py-1 mx-4">"Database migration commits"</p>
                  </div>
                  <p className="mt-3 text-xs opacity-70">
                    {isConnected ? 'Connected to Git Service' : 'Backend not connected'}
                  </p>
                </div>
              ) : (
                chatMessages.map((message) => (
                  <div key={message.id} className="space-y-2">
                    <div className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                        message.type === 'user' 
                          ? 'bg-primary text-primary-foreground' 
                          : 'bg-muted/60 backdrop-blur-sm shadow-sm border border-border/50'
                      }`}>
                        {message.content}
                      </div>
                    </div>
                    
                    {/* Display search results */}
                    {message.searchResults && message.searchResults.length > 0 && (
                      <div className="space-y-2 ml-4">
                        {message.searchResults.map((result) => (
                          <Card key={result._id} className="text-xs cursor-pointer hover:bg-accent/50" 
                                onClick={() => { setSelectedCommit(result); setCurrentView('commit-detail'); setShowChat(false); }}>
                            <CardContent className="p-3">
                              <div className="flex justify-between items-start mb-1">
                                <code className="text-xs text-primary">{(result.commit_hash || 'no-hash').substring(0, 7)}</code>
                                <span className="text-xs text-green-600 font-mono">
                                  {(result.score * 100).toFixed(1)}%
                                </span>
                              </div>
                              <p className="text-xs font-medium line-clamp-2 mb-1">{result.message}</p>
                              <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <span>{result.author}</span>
                                <span>{new Date(result.timestamp).toLocaleDateString()}</span>
                              </div>
                              {result.files_changed.length > 0 && (
                                <div className="mt-1 text-xs text-muted-foreground line-clamp-1">
                                  Files: {result.files_changed.slice(0, 2).join(', ')}
                                  {result.files_changed.length > 2 && ` +${result.files_changed.length - 2} more`}
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
              
              {isSearching && (
                <div className="flex justify-start">
                  <div className="bg-muted/60 rounded-lg px-3 py-2 text-sm flex items-center gap-2">
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary"></div>
                    Searching commits...
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="p-4 border-t">
              <div className="flex gap-2">
                <Input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={handleChatKeyPress}
                  placeholder={isConnected ? "Search commits semantically..." : "Backend not connected"}
                  className="flex-1"
                  disabled={!isConnected || isSearching}
                />
                <Button 
                  size="sm" 
                  onClick={sendChatMessage} 
                  disabled={!chatInput.trim() || !isConnected || isSearching}
                >
                  {isSearching ? (
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-current"></div>
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
              {!isConnected && (
                <p className="text-xs text-muted-foreground mt-2 text-center">
                  Start the Git Service backend to enable semantic search
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App