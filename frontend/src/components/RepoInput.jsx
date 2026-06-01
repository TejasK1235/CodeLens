import { useState } from 'react'
import { indexRepo } from '../api'
import './RepoInput.css'

const EXAMPLES = ['pallets/flask', 'fastapi/fastapi', 'psf/requests']
const GITHUB_PREFIX = 'https://github.com/'

export default function RepoInput({ onIndexStarted }) {
  const [slug, setSlug] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function buildUrl(value) {
    const v = value.trim()
    if (!v) return ''
    if (v.startsWith('https://')) return v
    return GITHUB_PREFIX + v
  }

  async function handleSubmit() {
    const url = buildUrl(slug)
    if (!url) return
    setError('')
    setLoading(true)
    try {
      const data = await indexRepo(url)
      onIndexStarted(data)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to connect. Is the backend running?'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSubmit()
  }

  const isValid = slug.trim().length > 0

  return (
    <div className="repo-input-screen">
      <div className="repo-input-bg" aria-hidden="true">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="bg-line" style={{ animationDelay: `${i * 0.4}s` }} />
        ))}
      </div>

      <div className="repo-input-card fade-in">
        <div className="card-eyebrow">
          <span className="eyebrow-dot" />
          RAG-powered codebase intelligence
        </div>

        <h1 className="card-title">
          Ask anything about<br />
          <span className="title-accent">any GitHub repo</span>
        </h1>

        <p className="card-subtitle">
          Enter a GitHub repo as <code className="subtitle-code">owner/repo</code> or paste
          the full URL. CodeLens indexes the codebase with semantic search and answers
          your questions with source citations.
        </p>

        <div className="input-row">
          <div className={`url-input-wrap ${error ? 'has-error' : ''}`}>
            <span className="input-prefix">github.com /</span>
            <input
              type="text"
              className="url-input"
              placeholder="owner/repo"
              value={slug}
              onChange={e => setSlug(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              autoFocus
            />
          </div>
          <button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={loading || !isValid}
          >
            {loading ? (
              <span className="btn-loading">
                <span className="spinner" />
                Checking...
              </span>
            ) : 'Index repo →'}
          </button>
        </div>

        {error && (
          <div className="input-error fade-in">
            <span className="error-icon">⚠</span> {error}
          </div>
        )}

        <div className="examples-row">
          <span className="examples-label">Try:</span>
          {EXAMPLES.map(ex => (
            <button
              key={ex}
              className="example-chip"
              onClick={() => setSlug(ex)}
              disabled={loading}
            >
              {ex}
            </button>
          ))}
        </div>

        <div className="card-footer">
          <span className="footer-item">
            <span className="footer-dot accent" />
            Public repos only
          </span>
          <span className="footer-item">
            <span className="footer-dot accent" />
            No account required
          </span>
          <span className="footer-item">
            <span className="footer-dot accent" />
            Python · JS · TS · Java · C++ · C#
          </span>
        </div>
      </div>
    </div>
  )
}