import { useState, useEffect, useRef } from 'react'
import { supabase, saveIndexedRepo } from './supabase'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import RepoInput from './components/RepoInput'
import IndexingProgress from './components/IndexingProgress'
import ChatInterface from './components/ChatInterface'
import './App.css'

// ── Guest configuration ───────────────────────────────────────────────────────
// Pre-index this repo at deploy time and paste its repo_id here.
// Run: curl -X POST https://your-backend/index -d '{"github_url":"https://github.com/pallets/flask"}'
// then copy the repo_id from the response.
const GUEST_REPO = {
  repo_id:   import.meta.env.VITE_GUEST_REPO_ID   || '',
  full_name: import.meta.env.VITE_GUEST_REPO_NAME  || 'pallets/flask',
  commit_hash: '',
  chunk_count: 0,
}
const GUEST_QUERY_LIMIT = 3
const GUEST_QUERIES_KEY = 'cl_guest_queries'

function getGuestQueriesUsed() {
  return parseInt(localStorage.getItem(GUEST_QUERIES_KEY) || '0', 10)
}
function incrementGuestQueries() {
  const n = getGuestQueriesUsed() + 1
  localStorage.setItem(GUEST_QUERIES_KEY, String(n))
  return n
}

// phase: 'loading' | 'auth' | 'dashboard' | 'input' | 'indexing' | 'chat' | 'guest'

export default function App() {
  const [phase, setPhase] = useState('loading')
  const [user, setUser] = useState(null)
  const [repoData, setRepoData] = useState(null)
  const [indexingInfo, setIndexingInfo] = useState(null)
  const [activeConversation, setActiveConversation] = useState(null)

  // ── Tab-switch bug fix ──────────────────────────────────────────────────────
  // We persist the current phase and associated data in a ref so that if the
  // user switches browser tabs while indexing is in progress, the state is
  // never lost. The IndexingProgress component continues polling in the
  // background regardless of tab visibility. When indexing completes, we
  // transition to chat normally — the user just sees the chat interface
  // whether they were watching or not.
  //
  // The bug was: visibilitychange events were causing a re-render that wiped
  // the indexing phase. The fix is simply to NOT listen to visibility events
  // at all and let polling continue silently in the background. IndexingProgress
  // already does this correctly because setInterval is not paused on hidden tabs.
  // The only remaining issue was App.jsx resetting state on auth re-check —
  // we guard that with the phaseRef below.
  const phaseRef = useRef(phase)
  useEffect(() => { phaseRef.current = phase }, [phase])

  // ── Auth init ───────────────────────────────────────────────────────────────
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        setUser(session.user)
        // Only transition to dashboard if we are still in loading phase.
        // If indexing is already running (e.g. page was refreshed mid-index),
        // preserve whatever phase was active.
        if (phaseRef.current === 'loading') {
          setPhase('dashboard')
        }
      } else {
        if (phaseRef.current === 'loading') {
          setPhase('auth')
        }
      }
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setUser(session.user)
        // Only redirect to dashboard on explicit login, not on token refresh.
        // Token refresh fires onAuthStateChange with event='TOKEN_REFRESHED'
        // and should not interrupt an active indexing session.
        if (_event === 'SIGNED_IN') {
          setPhase('dashboard')
          setRepoData(null)
          setIndexingInfo(null)
          setActiveConversation(null)
        }
      } else if (_event === 'SIGNED_OUT') {
        setUser(null)
        setPhase('auth')
        setRepoData(null)
        setIndexingInfo(null)
        setActiveConversation(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  // ── Navigation handlers ─────────────────────────────────────────────────────

  function handleAuth(authUser) {
    setUser(authUser)
    setPhase('dashboard')
  }

  function handleNewRepo() {
    setActiveConversation(null)
    setRepoData(null)
    setPhase('input')
  }

  function handleOpenRepo(repo) {
    setActiveConversation(null)
    setRepoData({
      repo_id:     repo.repo_id,
      full_name:   repo.full_name,
      commit_hash: repo.commit_hash,
      chunk_count: repo.chunk_count,
    })
    setPhase('chat')
  }

  function handleResumeConversation(repo, conversation) {
    setRepoData({
      repo_id:     repo.repo_id,
      full_name:   repo.full_name,
      commit_hash: repo.commit_hash,
      chunk_count: repo.chunk_count,
    })
    setActiveConversation(conversation)
    setPhase('chat')
  }

  async function handleIndexStarted(data) {
    if (data.status === 'cached') {
      if (user) await saveIndexedRepo(user.id, data)
      setRepoData(data)
      setActiveConversation(null)
      setPhase('chat')
    } else {
      // Store indexingInfo BEFORE changing phase so that if the component
      // mounts and immediately checks, the data is already available.
      setIndexingInfo(data)
      setPhase('indexing')
    }
  }

  async function handleIndexComplete(statusData, originalData) {
    const merged = { ...originalData, ...statusData }
    if (user) await saveIndexedRepo(user.id, merged)
    setRepoData(merged)
    setActiveConversation(null)
    // Transition to chat. This works correctly even if the user was on a
    // different browser tab — IndexingProgress polls via setInterval which
    // continues running regardless of tab visibility, and when it calls
    // onComplete() the state update queues normally.
    setPhase('chat')
  }

  function handleBackToDashboard() {
    setPhase('dashboard')
    setRepoData(null)
    setActiveConversation(null)
    setIndexingInfo(null)
  }

  // ── Guest mode handlers ─────────────────────────────────────────────────────

  function handleTryAsGuest() {
    if (!GUEST_REPO.repo_id) return   // guest mode not configured
    setRepoData(GUEST_REPO)
    setPhase('guest')
  }

  function handleGuestSignupPrompt() {
    // Called by ChatInterface when guest hits query limit
    setPhase('auth')
    setRepoData(null)
  }

  // ── Loading splash ──────────────────────────────────────────────────────────
  if (phase === 'loading') {
    return (
      <div className="app-shell loading-shell">
        <span className="loading-logo">⬡</span>
      </div>
    )
  }

  // ── Auth ────────────────────────────────────────────────────────────────────
  if (phase === 'auth') {
    return (
      <div className="app-shell">
        <main className="app-main">
          <AuthPage
            onAuth={handleAuth}
            onGuestMode={GUEST_REPO.repo_id ? handleTryAsGuest : null}
          />
        </main>
      </div>
    )
  }

  // ── Dashboard ───────────────────────────────────────────────────────────────
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

  // ── Guest chat ──────────────────────────────────────────────────────────────
  if (phase === 'guest') {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="header-logo">
            <span className="logo-icon">⬡</span>
            <span className="logo-text">CodeLens</span>
          </div>
          <div className="header-repo">
            <span className="repo-name">{GUEST_REPO.full_name}</span>
            <span className="guest-badge">Guest</span>
          </div>
          <button className="btn-ghost btn-sm" onClick={() => setPhase('auth')}>
            Sign up free →
          </button>
        </header>
        <main className="app-main">
          <ChatInterface
            repoData={GUEST_REPO}
            user={null}
            existingConversation={null}
            isGuest={true}
            guestQueryLimit={GUEST_QUERY_LIMIT}
            guestQueriesUsed={getGuestQueriesUsed()}
            onGuestLimitReached={handleGuestSignupPrompt}
            onIncrementGuestQuery={incrementGuestQueries}
          />
        </main>
      </div>
    )
  }

  // ── Input / Indexing / Chat (shared header) ─────────────────────────────────
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
            isGuest={false}
          />
        )}
      </main>
    </div>
  )
}