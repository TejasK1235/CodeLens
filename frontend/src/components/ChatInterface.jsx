import { useState, useRef, useEffect, useCallback } from 'react'
import { queryRepo } from '../api'
import SourcesPanel from './SourcesPanel'
import {
  saveMessage, createConversation, getConversationMessages,
  updateConversationTimestamp, updateRepoLastQueried,
} from '../supabase'
import './ChatInterface.css'

// ── Easter egg ────────────────────────────────────────────────────────────────
const GRIEVOUS_TRIGGER = "Hello there!"
const GRIEVOUS_OPENING = `General Kenobi! You are a bold one!`

// ── Sub-components ────────────────────────────────────────────────────────────

function MessageBubble({ message, onViewSources, isActive, grievousMode }) {
  const [hovered, setHovered] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="msg-row msg-user">
        <div className="msg-bubble user-bubble">{message.content}</div>
      </div>
    )
  }

  return (
    <div
      className={`msg-row msg-assistant fade-in ${grievousMode ? 'grievous-msg' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="msg-meta">
        <span className="msg-label">
          {grievousMode ? '⚔️ General Grievous' : 'CodeLens'}
        </span>
        {message.stats && !grievousMode && (
          <span className="msg-stats">
            {message.stats.retrieved_count} retrieved · {message.stats.expanded_count} expanded
          </span>
        )}
        {message.sources?.length > 0 && (hovered || isActive) && (
          <button
            className={`view-sources-btn ${isActive ? 'active' : ''}`}
            onClick={() => onViewSources(message.sources)}
          >
            {isActive ? '● sources' : '○ view sources'}
          </button>
        )}
      </div>
      <div className={`msg-bubble assistant-bubble ${grievousMode ? 'grievous-bubble' : ''}`}>
        <AnswerText text={message.content} />
      </div>
    </div>
  )
}

function AnswerText({ text }) {
  const parts = text.split(/(```[\s\S]*?```)/g)
  return (
    <div className="answer-text">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const lines = part.split('\n')
          const lang = lines[0].replace('```', '').trim()
          const code = lines.slice(1, -1).join('\n')
          return (
            <pre key={i} className="answer-code">
              {lang && <span className="code-lang">{lang}</span>}
              <code>{code}</code>
            </pre>
          )
        }
        return (
          <span key={i} className="answer-prose">
            {part.split('\n').map((line, j) => (
              <span key={j}>
                {line.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).map((seg, k) => {
                  if (seg.startsWith('**') && seg.endsWith('**'))
                    return <strong key={k}>{seg.slice(2, -2)}</strong>
                  if (seg.startsWith('*') && seg.endsWith('*') && seg.length > 2)
                    return <em key={k}>{seg.slice(1, -1)}</em>
                  if (seg.startsWith('`') && seg.endsWith('`'))
                    return <code key={k} className="inline-code">{seg.slice(1, -1)}</code>
                  return seg
                })}
                {j < part.split('\n').length - 1 && <br />}
              </span>
            ))}
          </span>
        )
      })}
    </div>
  )
}

function ThinkingBubble({ grievousMode }) {
  return (
    <div className="msg-row msg-assistant fade-in">
      <div className="msg-meta">
        <span className="msg-label">
          {grievousMode ? '⚔️ General Grievous' : 'CodeLens'}
        </span>
      </div>
      <div className={`msg-bubble assistant-bubble thinking-bubble ${grievousMode ? 'grievous-bubble' : ''}`}>
        <span className="thinking-dot" style={{ animationDelay: '0s' }} />
        <span className="thinking-dot" style={{ animationDelay: '0.2s' }} />
        <span className="thinking-dot" style={{ animationDelay: '0.4s' }} />
      </div>
    </div>
  )
}

function GuestBanner({ queriesUsed, queryLimit, onSignup }) {
  const remaining = queryLimit - queriesUsed
  return (
    <div className="guest-banner">
      <span className="guest-banner-text">
        {remaining > 0
          ? `Exploring as guest — ${remaining} free quer${remaining === 1 ? 'y' : 'ies'} remaining`
          : 'You have used all your guest queries'}
      </span>
      <button className="guest-banner-cta" onClick={onSignup}>
        Sign up free for unlimited access →
      </button>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ChatInterface({
  repoData,
  user,
  existingConversation = null,
  isGuest = false,
  guestQueryLimit = 3,
  guestQueriesUsed: initialGuestQueriesUsed = 0,
  onGuestLimitReached,
  onIncrementGuestQuery,
}) {
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeSources, setActiveSources] = useState([])
  const [activeSourcesMsgIndex, setActiveSourcesMsgIndex] = useState(null)
  const [sourcesPanelWidth, setSourcesPanelWidth] = useState(340)
  const [conversationId, setConversationId] = useState(existingConversation?.id || null)
  const [loadingHistory, setLoadingHistory] = useState(!!existingConversation)
  const [guestQueriesUsed, setGuestQueriesUsed] = useState(initialGuestQueriesUsed)
  const [grievousMode, setGrievousMode] = useState(false)

  const isDragging = useRef(false)
  const dragStartX = useRef(0)
  const dragStartWidth = useRef(0)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!existingConversation) { setLoadingHistory(false); return }
    getConversationMessages(existingConversation.id).then(msgs => {
      const formatted = msgs.map(m => ({
        role: m.role, content: m.content,
        sources: m.sources || [], stats: m.stats || null,
      }))
      setMessages(formatted)
      const lastAssistant = [...formatted].reverse().find(m => m.role === 'assistant')
      if (lastAssistant?.sources?.length) {
        setActiveSources(lastAssistant.sources)
        setActiveSourcesMsgIndex(formatted.lastIndexOf(lastAssistant))
      }
      setLoadingHistory(false)
    })
  }, [existingConversation?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    if (!loadingHistory) inputRef.current?.focus()
  }, [loadingHistory])

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height =
        `${Math.min(inputRef.current.scrollHeight, 160)}px`
    }
  }, [query])

  const onDragStart = useCallback((e) => {
    isDragging.current = true
    dragStartX.current = e.clientX
    dragStartWidth.current = sourcesPanelWidth
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [sourcesPanelWidth])

  useEffect(() => {
    function onMouseMove(e) {
      if (!isDragging.current) return
      const delta = dragStartX.current - e.clientX
      setSourcesPanelWidth(Math.min(Math.max(dragStartWidth.current + delta, 220), 560))
    }
    function onMouseUp() {
      if (!isDragging.current) return
      isDragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  function buildHistory() {
    const turns = []
    for (let i = 0; i < messages.length - 1; i += 2) {
      const u = messages[i], a = messages[i + 1]
      if (u && a) turns.push({ query: u.content, answer: a.content })
    }
    return turns.slice(-2)
  }

  async function handleSend() {
    const q = query.trim()
    if (!q || loading) return

    if (isGuest && guestQueriesUsed >= guestQueryLimit) {
      onGuestLimitReached?.()
      return
    }

    setQuery('')

    // ── Easter egg detection ─────────────────────────────────────────────────
    // Only triggers on the very first message in a fresh conversation
    if (q === GRIEVOUS_TRIGGER && !grievousMode) {
      setGrievousMode(true)
      setMessages([
        { role: 'user', content: q },
        { role: 'assistant', content: GRIEVOUS_OPENING, sources: [], stats: null },
      ])
      // Save to Supabase if authenticated
      if (user && !isGuest) {
        const convo = await createConversation(
          user.id, repoData.repo_id, repoData.full_name, q
        )
        if (convo) {
          setConversationId(convo.id)
          await saveMessage(convo.id, user.id, 'user', q)
          await saveMessage(convo.id, user.id, 'assistant', GRIEVOUS_OPENING, [], null)
        }
      }
      if (isGuest) {
        const newCount = onIncrementGuestQuery?.() ?? guestQueriesUsed + 1
        setGuestQueriesUsed(newCount)
      }
      return
    }
    // ── End easter egg ───────────────────────────────────────────────────────

    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)

    try {
      let convId = conversationId
      if (!convId && user && !isGuest) {
        const convo = await createConversation(user.id, repoData.repo_id, repoData.full_name, q)
        if (convo) { convId = convo.id; setConversationId(convId) }
      }
      if (convId && user && !isGuest) {
        await saveMessage(convId, user.id, 'user', q)
      }

      const data = await queryRepo(
        repoData.repo_id, q, buildHistory(), grievousMode
      )

      const visibleSources = (data.sources || []).filter(
        s => !s.name?.startsWith('__file__')
      )

      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sources: visibleSources,
        stats: {
          retrieved_count: data.retrieved_count,
          expanded_count: data.expanded_count,
        },
      }

      if (convId && user && !isGuest) {
        await saveMessage(convId, user.id, 'assistant', data.answer, visibleSources, {
          retrieved_count: data.retrieved_count,
          expanded_count: data.expanded_count,
        })
        await updateConversationTimestamp(convId)
        await updateRepoLastQueried(user.id, repoData.repo_id)
      }

      if (isGuest) {
        const newCount = onIncrementGuestQuery?.() ?? guestQueriesUsed + 1
        setGuestQueriesUsed(newCount)
        if (newCount >= guestQueryLimit) {
          setTimeout(() => onGuestLimitReached?.(), 3500)
        }
      }

      setMessages(prev => {
        const next = [...prev, assistantMsg]
        setActiveSourcesMsgIndex(next.length - 1)
        return next
      })
      setActiveSources(visibleSources)

    } catch (err) {
      const msg = err.response?.data?.detail || 'Query failed. Please try again.'
      setMessages(prev => [...prev, {
        role: 'assistant', content: `Error: ${msg}`, sources: [], stats: null,
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  function handleViewSources(sources, msgIndex) {
    setActiveSources(sources)
    setActiveSourcesMsgIndex(msgIndex)
  }

  const isEmpty = messages.length === 0
  const guestLimitReached = isGuest && guestQueriesUsed >= guestQueryLimit
  const isMobile = window.innerWidth <= 768

  if (loadingHistory) {
    return (
      <div className="chat-layout">
        <div className="chat-panel" style={{ alignItems: 'center', justifyContent: 'center' }}>
          <span className="loading-spinner" style={{ width: 20, height: 20 }} />
        </div>
      </div>
    )
  }

  return (
    <div className={`chat-layout ${grievousMode ? 'grievous-theme' : ''}`}
         style={{ flexDirection: 'column' }}>
      {isGuest && (
        <GuestBanner
          queriesUsed={guestQueriesUsed}
          queryLimit={guestQueryLimit}
          onSignup={() => onGuestLimitReached?.()}
        />
      )}

      <div className="chat-layout-inner">
        <div className="chat-panel">
          {isEmpty ? (
            <div className="chat-empty">
              <div className="empty-icon">⬡</div>
              <p className="empty-title">Ready to explore</p>
              <p className="empty-sub">
                Ask anything about{' '}
                <span className="empty-repo">{repoData.full_name}</span>
              </p>
              {isGuest && (
                <p className="empty-guest-note">
                  {guestQueryLimit} free queries · No signup required
                </p>
              )}
              <div className="empty-suggestions">
                {[
                  'How does request routing work?',
                  'What is the main entry point?',
                  'How is error handling implemented?',
                  'What design patterns are used?',
                ].map(s => (
                  <button
                    key={s}
                    className="suggestion-chip"
                    onClick={() => setQuery(s)}
                    disabled={guestLimitReached}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages-list">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  message={msg}
                  onViewSources={sources => handleViewSources(sources, i)}
                  isActive={activeSourcesMsgIndex === i}
                  grievousMode={grievousMode}
                />
              ))}
              {loading && <ThinkingBubble grievousMode={grievousMode} />}
              <div ref={bottomRef} />
            </div>
          )}

          <div className="chat-input-bar">
            <div className={`chat-input-wrap ${guestLimitReached ? 'disabled' : ''} ${grievousMode ? 'grievous-input' : ''}`}>
              <textarea
                ref={inputRef}
                className="chat-input"
                placeholder={
                  guestLimitReached
                    ? 'Sign up for unlimited queries →'
                    : grievousMode
                    ? 'Your query, Jedi...'
                    : `Ask about ${repoData.full_name}...`
                }
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading || guestLimitReached}
                rows={1}
              />
              <button
                className="btn-icon"
                onClick={guestLimitReached ? () => onGuestLimitReached?.() : handleSend}
                disabled={loading || (!guestLimitReached && !query.trim())}
                aria-label={guestLimitReached ? 'Sign up' : 'Send'}
              >
                {guestLimitReached ? '→' : grievousMode ? '⚔️' : '↑'}
              </button>
            </div>
            {!guestLimitReached && (
              <p className="input-hint">Enter to send · Shift+Enter for newline</p>
            )}
          </div>
        </div>

        {!isMobile && (
          <div
            className="panel-resize-handle"
            onMouseDown={onDragStart}
            title="Drag to resize"
          />
        )}

        <div
          className="sources-panel-wrapper"
          style={{ width: isMobile ? '100%' : `${sourcesPanelWidth}px` }}
        >
          <SourcesPanel sources={activeSources} repoData={repoData} />
        </div>
      </div>
    </div>
  )
}