import { useState, useEffect } from 'react'
import { supabase, saveIndexedRepo } from './supabase'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import RepoInput from './components/RepoInput'
import IndexingProgress from './components/IndexingProgress'
import ChatInterface from './components/ChatInterface'
import './App.css'

// phase: 'loading' | 'auth' | 'dashboard' | 'input' | 'indexing' | 'chat'

export default function App() {
  const [phase, setPhase] = useState('loading')
  const [user, setUser] = useState(null)
  const [repoData, setRepoData] = useState(null)
  const [indexingInfo, setIndexingInfo] = useState(null)
  const [activeConversation, setActiveConversation] = useState(null)

  // Check existing session on mount
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        setUser(session.user)
        setPhase('dashboard')
      } else {
        setPhase('auth')
      }
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setUser(session.user)
        setPhase('dashboard')
      } else {
        setUser(null)
        setPhase('auth')
        setRepoData(null)
        setIndexingInfo(null)
        setActiveConversation(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  function handleAuth(authUser) {
    setUser(authUser)
    setPhase('dashboard')
  }

  // User clicks "New chat" or "Index new repo" from dashboard
  function handleNewRepo() {
    setActiveConversation(null)
    setRepoData(null)
    setPhase('input')
  }

  // User clicks existing repo card → new chat on that repo
  function handleOpenRepo(repo) {
    setActiveConversation(null)
    setRepoData({
      repo_id: repo.repo_id,
      full_name: repo.full_name,
      commit_hash: repo.commit_hash,
      chunk_count: repo.chunk_count,
    })
    setPhase('chat')
  }

  // User clicks a past conversation → resume it
  function handleResumeConversation(repo, conversation) {
    setRepoData({
      repo_id: repo.repo_id,
      full_name: repo.full_name,
      commit_hash: repo.commit_hash,
      chunk_count: repo.chunk_count,
    })
    setActiveConversation(conversation)
    setPhase('chat')
  }

  // Index started from RepoInput
  async function handleIndexStarted(data) {
    if (data.status === 'cached') {
      // Already indexed — save to Supabase and go to chat
      if (user) {
        await saveIndexedRepo(user.id, data)
      }
      setRepoData(data)
      setActiveConversation(null)
      setPhase('chat')
    } else {
      setIndexingInfo(data)
      setPhase('indexing')
    }
  }

  // Indexing completed
  async function handleIndexComplete(statusData, originalData) {
    const merged = { ...originalData, ...statusData }
    if (user) {
      await saveIndexedRepo(user.id, merged)
    }
    setRepoData(merged)
    setActiveConversation(null)
    setPhase('chat')
  }

  // Back to dashboard from chat or input
  function handleBackToDashboard() {
    setPhase('dashboard')
    setRepoData(null)
    setActiveConversation(null)
    setIndexingInfo(null)
  }

  if (phase === 'loading') {
    return (
      <div className="app-shell" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--accent)', fontSize: 24 }}>⬡</span>
      </div>
    )
  }

  if (phase === 'auth') {
    return (
      <div className="app-shell">
        <main className="app-main">
          <AuthPage onAuth={handleAuth} />
        </main>
      </div>
    )
  }

  if (phase === 'dashboard') {
    return (
      <div className="app-shell">
        <main className="app-main">
          <Dashboard
            user={user}
            onOpenRepo={handleOpenRepo}
            onResumeConversation={handleResumeConversation}
            onNewRepo={handleNewRepo}
          />
        </main>
      </div>
    )
  }

  // input / indexing / chat all share the top header
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-logo">
          <span className="logo-icon">⬡</span>
          <span className="logo-text">CodeLens</span>
        </div>
        {repoData && (
          <div className="header-repo">
            <span className="repo-name">{repoData.full_name}</span>
          </div>
        )}
        <button className="btn-ghost btn-sm" onClick={handleBackToDashboard}>
          ← Dashboard
        </button>
      </header>

      <main className="app-main">
        {phase === 'input' && (
          <RepoInput onIndexStarted={handleIndexStarted} />
        )}
        {phase === 'indexing' && (
          <IndexingProgress
            indexingInfo={indexingInfo}
            onComplete={handleIndexComplete}
          />
        )}
        {phase === 'chat' && (
          <ChatInterface
            repoData={repoData}
            user={user}
            existingConversation={activeConversation}
          />
        )}
      </main>
    </div>
  )
}