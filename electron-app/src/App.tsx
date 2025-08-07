import React, { useState, useEffect } from 'react'
import { GitBranch, GitCommit, RefreshCw, FolderOpen, Activity, MessageCircle, Send, ChevronRight, Code, Zap, Clock, User, Hash, ArrowLeft } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card'
import { Input } from './components/ui/input'
import { StashLogo } from './components/StashLogo'

function App() {
  const [repoPath, setRepoPath] = useState<string>('')
  const [repoName, setRepoName] = useState<string>('No repository')
  const [branch, setBranch] = useState<string>('--')
  const [commits, setCommits] = useState<any[]>([])
  const [stats, setStats] = useState({
    commitsToday: 0,
    linesChanged: 0,
    activeBranches: 0
  })
  const [chatMessages, setChatMessages] = useState<Array<{id: string, type: 'user' | 'assistant', content: string, timestamp: Date}>>([])
  const [chatInput, setChatInput] = useState<string>('')
  const [showChat, setShowChat] = useState<boolean>(false)
  const [selectedCommit, setSelectedCommit] = useState<any>(null)
  const [currentView, setCurrentView] = useState<'overview' | 'commits' | 'commit-detail' | 'analysis'>('overview')
  const [analysisStatus, setAnalysisStatus] = useState<'idle' | 'analyzing' | 'complete'>('idle')

  // Mock commit data - replace with real git data later
  const mockCommits = [
    {
      hash: 'a1b2c3d',
      message: 'Fix critical bug in user authentication',
      author: 'john.doe',
      timestamp: '2 hours ago',
      changes: { files: 3, additions: 15, deletions: 8 }
    },
    {
      hash: 'e4f5g6h',
      message: 'Add new feature for dashboard analytics',
      author: 'jane.smith',
      timestamp: '1 day ago',
      changes: { files: 7, additions: 142, deletions: 23 }
    },
    {
      hash: 'i7j8k9l',
      message: 'Refactor database connection logic',
      author: 'bob.wilson',
      timestamp: '2 days ago',
      changes: { files: 4, additions: 67, deletions: 89 }
    },
    {
      hash: 'm1n2o3p',
      message: 'Update dependencies and fix security issues',
      author: 'alice.cooper',
      timestamp: '3 days ago',
      changes: { files: 12, additions: 203, deletions: 156 }
    },
    {
      hash: 'q4r5s6t',
      message: 'Broke everything trying to optimize queries',
      author: 'dev.junior',
      timestamp: '1 week ago',
      changes: { files: 15, additions: 89, deletions: 234 }
    }
  ]

  const openRepository = async () => {
    console.log('Open repository')
    // Mock loading commits
    setCommits(mockCommits)
    setCurrentView('commits')
  }

  const refreshRepository = () => {
    console.log('Refresh')
  }

  const sendChatMessage = () => {
    if (!chatInput.trim()) return
    
    const newMessage = {
      id: Date.now().toString(),
      type: 'user' as const,
      content: chatInput,
      timestamp: new Date()
    }
    
    setChatMessages(prev => [...prev, newMessage])
    setChatInput('')
    
    // Placeholder for AI response logic
    setTimeout(() => {
      const aiResponse = {
        id: (Date.now() + 1).toString(),
        type: 'assistant' as const,
        content: "I'll help you analyze your repository. This is where the AI logic will be implemented.",
        timestamp: new Date()
      }
      setChatMessages(prev => [...prev, aiResponse])
    }, 500)
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

        <div className="space-y-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="w-full justify-start"
            onClick={openRepository}
          >
            <FolderOpen className="w-4 h-4 mr-2" />
            Open Repository
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            className="w-full justify-start"
            onClick={refreshRepository}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
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
            <Input 
              className="w-64"
              placeholder="Search commits..."
              type="search"
            />
            <Button 
              variant={showChat ? "default" : "outline"} 
              size="sm"
              onClick={() => setShowChat(!showChat)}
              className="flex items-center gap-2"
            >
              <MessageCircle className="w-4 h-4" />
              Chat
            </Button>
          </div>
        </div>

        <div className="flex-1 flex">
          <div className={`flex-1 p-6 overflow-auto transition-all duration-300 ${showChat ? 'mr-80' : ''}`}>
            {currentView === 'overview' && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Activity className="w-12 h-12 text-muted-foreground/50 mb-4" />
                <h2 className="text-lg font-semibold mb-2">No repository selected</h2>
                <p className="text-sm text-muted-foreground max-w-md">
                  Open a git repository to start tracking your coding vibe
                </p>
              </div>
            )}

            {currentView === 'commits' && (
              <div className="space-y-3">
                {commits.map((commit, index) => (
                  <Card key={index} className="hover:bg-muted/30 transition-colors cursor-pointer" onClick={() => selectCommit(commit)}>
                    <CardContent className="pt-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <Hash className="w-3 h-3 text-muted-foreground" />
                          <code className="text-xs text-primary">{commit.hash}</code>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {commit.timestamp}
                        </div>
                      </div>
                      <p className="text-sm mb-2">{commit.message}</p>
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <User className="w-3 h-3" />
                          {commit.author}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                          <span className="text-green-500">+{commit.changes.additions}</span>
                          <span className="text-red-500">-{commit.changes.deletions}</span>
                          <span>{commit.changes.files} files</span>
                          <ChevronRight className="w-4 h-4" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
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
                            {selectedCommit.hash}
                          </span>
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {selectedCommit.author}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {selectedCommit.timestamp}
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
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div className="text-center p-3 bg-muted/30 rounded">
                        <div className="text-lg font-semibold">{selectedCommit.changes.files}</div>
                        <div className="text-xs text-muted-foreground">Files Changed</div>
                      </div>
                      <div className="text-center p-3 bg-green-500/10 rounded">
                        <div className="text-lg font-semibold text-green-500">+{selectedCommit.changes.additions}</div>
                        <div className="text-xs text-muted-foreground">Additions</div>
                      </div>
                      <div className="text-center p-3 bg-red-500/10 rounded">
                        <div className="text-lg font-semibold text-red-500">-{selectedCommit.changes.deletions}</div>
                        <div className="text-xs text-muted-foreground">Deletions</div>
                      </div>
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
                  <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>Ask something like:</p>
                  <div className="mt-2 space-y-1 text-xs">
                    <p className="bg-muted/50 rounded px-2 py-1 mx-4">"Which commit fucked my repository?"</p>
                    <p className="bg-muted/50 rounded px-2 py-1 mx-4">"Show me recent changes"</p>
                    <p className="bg-muted/50 rounded px-2 py-1 mx-4">"Who worked on this file?"</p>
                  </div>
                </div>
              ) : (
                chatMessages.map((message) => (
                  <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                      message.type === 'user' 
                        ? 'bg-primary text-primary-foreground' 
                        : 'bg-muted/60 backdrop-blur-sm shadow-sm border border-border/50'
                    }`}>
                      {message.content}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Chat Input */}
            <div className="p-4 border-t">
              <div className="flex gap-2">
                <Input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={handleChatKeyPress}
                  placeholder="Ask about your repository..."
                  className="flex-1"
                />
                <Button size="sm" onClick={sendChatMessage} disabled={!chatInput.trim()}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App