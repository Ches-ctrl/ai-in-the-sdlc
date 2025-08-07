import React, { useState, useEffect } from 'react'
import { GitBranch, GitCommit, RefreshCw, FolderOpen, Activity } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card'
import { Input } from './components/ui/input'

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

  const openRepository = async () => {
    console.log('Open repository')
  }

  const refreshRepository = () => {
    console.log('Refresh')
  }

  return (
    <div className="flex h-screen bg-background">
      <div className="w-64 border-r bg-card/50 p-4 space-y-4">
        <div className="pt-8 pb-4 border-b" style={{ WebkitAppRegion: 'drag' } as any}>
          <div className="flex items-center" style={{ WebkitAppRegion: 'no-drag' } as any}>
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
          <h1 className="text-lg font-semibold" style={{ WebkitAppRegion: 'no-drag' } as any}>Repository Overview</h1>
          <Input 
            className="w-64"
            style={{ WebkitAppRegion: 'no-drag' } as any} 
            placeholder="Search commits..."
            type="search"
          />
        </div>

        <div className="flex-1 p-6 overflow-auto">
          {commits.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Activity className="w-12 h-12 text-muted-foreground/50 mb-4" />
              <h2 className="text-lg font-semibold mb-2">No repository selected</h2>
              <p className="text-sm text-muted-foreground max-w-md">
                Open a git repository to start tracking your coding vibe
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {commits.map((commit, index) => (
                <Card key={index}>
                  <CardContent className="pt-4">
                    <div className="flex justify-between items-start mb-2">
                      <code className="text-xs text-primary">{commit.hash}</code>
                      <span className="text-xs text-muted-foreground">{commit.time}</span>
                    </div>
                    <p className="text-sm mb-2">{commit.message}</p>
                    <p className="text-xs text-muted-foreground">by {commit.author}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App