import { useState } from 'react'
import { supabase } from '../supabase'
import './AuthPage.css'

export default function AuthPage({ onAuth, onGuestMode }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email.trim() || !password.trim()) return
    setError(''); setMessage(''); setLoading(true)
    try {
      if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({ email: email.trim(), password })
        if (error) throw error
        if (data.user && !data.session) {
          setMessage('Check your email to confirm your account, then log in.')
          setMode('login')
        } else if (data.session) {
          onAuth(data.session.user)
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim(), password,
        })
        if (error) throw error
        onAuth(data.user)
      }
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function handleForgotPassword() {
    if (!email.trim()) { setError('Enter your email first.'); return }
    setLoading(true); setError('')
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim())
      if (error) throw error
      setMessage('Password reset email sent.')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card fade-in">
        <div className="auth-logo">
          <span className="auth-logo-icon">⬡</span>
          <span className="auth-logo-text">CodeLens</span>
        </div>

        <h1 className="auth-title">
          {mode === 'login' ? 'Welcome back' : 'Create account'}
        </h1>
        <p className="auth-subtitle">
          {mode === 'login'
            ? 'Sign in to access your repos and conversation history.'
            : 'Start asking questions about any GitHub codebase.'}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-field">
            <label className="auth-label">Email</label>
            <input
              type="email" className="auth-input"
              placeholder="you@example.com"
              value={email} onChange={e => setEmail(e.target.value)}
              disabled={loading} autoFocus required
            />
          </div>
          <div className="auth-field">
            <label className="auth-label">Password</label>
            <input
              type="password" className="auth-input"
              placeholder={mode === 'signup' ? 'At least 6 characters' : '••••••••'}
              value={password} onChange={e => setPassword(e.target.value)}
              disabled={loading} required
            />
          </div>

          {error   && <div className="auth-error fade-in"><span>⚠</span> {error}</div>}
          {message && <div className="auth-message fade-in"><span>✓</span> {message}</div>}

          <button
            type="submit" className="auth-submit"
            disabled={loading || !email.trim() || !password.trim()}
          >
            {loading ? (
              <span className="auth-loading">
                <span className="auth-spinner" />
                {mode === 'login' ? 'Signing in...' : 'Creating account...'}
              </span>
            ) : (
              mode === 'login' ? 'Sign in →' : 'Create account →'
            )}
          </button>
        </form>

        {/* Guest mode — only rendered when a pre-indexed repo is configured */}
        {onGuestMode && (
          <div className="auth-guest-section">
            <div className="auth-guest-divider">
              <span>or</span>
            </div>
            <button className="auth-guest-btn" onClick={onGuestMode} disabled={loading}>
              Try without an account →
              <span className="auth-guest-note">
                Explore a pre-indexed repo · {3} free queries
              </span>
            </button>
          </div>
        )}

        <div className="auth-footer">
          {mode === 'login' ? (
            <>
              <button className="auth-link" onClick={handleForgotPassword} disabled={loading}>
                Forgot password?
              </button>
              <span className="auth-divider">·</span>
              <button className="auth-link" onClick={() => { setMode('signup'); setError(''); setMessage('') }}>
                Create account
              </button>
            </>
          ) : (
            <button className="auth-link" onClick={() => { setMode('login'); setError(''); setMessage('') }}>
              Already have an account? Sign in
            </button>
          )}
        </div>
      </div>
    </div>
  )
}