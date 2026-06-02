import { useState, useEffect } from 'react'
import { supabase, getUserRepos, getUserConversations, deleteConversation } from '../supabase'
import './Dashboard.css'

function RepoCard({ repo, conversations, onOpenRepo, onResumeConversation }) {
  const [expanded, setExpanded] = useState(false)
  const repoConvos = conversations.filter(c => c.repo_id === repo.repo_id)

  function formatDate(iso) {
    const d = new Date(iso)
    const now = new Date()
    const diff = now - d
    if (diff < 60000) return 'just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`
    return d.toLocaleDateString()
  }

  return (
    <div className="repo-card">
      <div className="repo-card-header">
        <div className="repo-card-info">
          <div className="repo-card-name-row">
            <span className="repo-card-icon">⬡</span>
            <span className="repo-card-name">{repo.full_name}</span>
          </div>
          <div className="repo-card-meta">
            <span className="repo-meta-item">{repo.chunk_count.toLocaleString()} chunks</span>
            <span className="repo-meta-dot">·</span>
            <span className="repo-meta-item">{repoConvos.length} conversation{repoConvos.length !== 1 ? 's' : ''}</span>
            <span className="repo-meta-dot">·</span>
            <span className="repo-meta-item">last used {formatDate(repo.last_queried_at)}</span>
          </div>
        </div>
        <div className="repo-card-actions">
          <button
            className="btn-new-chat"
            onClick={() => onOpenRepo(repo)}
          >
            New chat →
          </button>
          {repoConvos.length > 0 && (
            <button
              className="btn-toggle-history"
              onClick={() => setExpanded(v => !v)}
            >
              {expanded ? '▲ hide' : `▼ ${repoConvos.length} chats`}
            </button>
          )}
        </div>
      </div>

      {expanded && repoConvos.length > 0 && (
        <div className="repo-conversations fade-in">
          {repoConvos.map(convo => (
            <ConversationRow
              key={convo.id}
              convo={convo}
              onResume={() => onResumeConversation(repo, convo)}
              formatDate={formatDate}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ConversationRow({ convo, onResume, formatDate, onDelete }) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  async function handleDelete(e) {
    e.stopPropagation()
    if (!confirmDelete) {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
      return
    }
    await deleteConversation(convo.id)
    onDelete && onDelete(convo.id)
  }

  return (
    <div className="convo-row" onClick={onResume}>
      <div className="convo-row-left">
        <span className="convo-icon">💬</span>
        <span className="convo-title">{convo.title}</span>
      </div>
      <div className="convo-row-right">
        <span className="convo-date">{formatDate(convo.updated_at)}</span>
        <button
          className={`convo-delete ${confirmDelete ? 'confirm' : ''}`}
          onClick={handleDelete}
          title={confirmDelete ? 'Click again to confirm' : 'Delete'}
        >
          {confirmDelete ? '?' : '×'}
        </button>
      </div>
    </div>
  )
}

export default function Dashboard({ user, onOpenRepo, onResumeConversation, onNewRepo }) {
  const [repos, setRepos] = useState([])
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      const [reposData, convosData] = await Promise.all([
        getUserRepos(user.id),
        getUserConversations(user.id),
      ])
      setRepos(reposData)
      setConversations(convosData)
      setLoading(false)
    }
    load()
  }, [user.id])

  function handleDeleteConversation(deletedId) {
    setConversations(prev => prev.filter(c => c.id !== deletedId))
  }

  async function handleSignOut() {
    await supabase.auth.signOut()
  }

  const totalConversations = conversations.length
  const recentRepos = repos.slice(0, 3)

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="dashboard-header-left">
          <div className="dashboard-logo">
            <span className="dashboard-logo-icon">⬡</span>
            <span className="dashboard-logo-text">CodeLens</span>
          </div>
          <div className="dashboard-stats-bar">
            <span className="stat-item">
              <span className="stat-num">{repos.length}</span> repos indexed
            </span>
            <span className="stat-sep">·</span>
            <span className="stat-item">
              <span className="stat-num">{totalConversations}</span> conversations
            </span>
          </div>
        </div>
        <div className="dashboard-header-right">
          <span className="user-email">{user.email}</span>
          <button className="btn-signout" onClick={handleSignOut}>Sign out</button>
        </div>
      </div>

      <div className="dashboard-body">
        <div className="dashboard-section-header">
          <div>
            <h2 className="section-title">Your repositories</h2>
            <p className="section-sub">Click a repo to start a new conversation, or resume an existing one.</p>
          </div>
          <button className="btn-index-new" onClick={onNewRepo}>
            + Index new repo
          </button>
        </div>

        {loading ? (
          <div className="dashboard-loading">
            <span className="loading-spinner" />
            <span>Loading your repos...</span>
          </div>
        ) : repos.length === 0 ? (
          <div className="dashboard-empty">
            <div className="empty-graphic">⬡</div>
            <p className="empty-title">No repos indexed yet</p>
            <p className="empty-sub">Index your first GitHub repository to get started.</p>
            <button className="btn-index-new large" onClick={onNewRepo}>
              Index a repo →
            </button>
          </div>
        ) : (
          <div className="repos-list">
            {repos.map(repo => (
              <RepoCard
                key={repo.id}
                repo={repo}
                conversations={conversations}
                onOpenRepo={onOpenRepo}
                onResumeConversation={(repo, convo) => onResumeConversation(repo, convo)}
                onDeleteConversation={handleDeleteConversation}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}