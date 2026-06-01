import { useState, useRef, useEffect, useCallback } from 'react'
import { queryRepo } from '../api'
import SourcesPanel from './SourcesPanel'
import './ChatInterface.css'

function MessageBubble({ message, onViewSources, isActive }) {
  const [hovered, setHovered] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="msg-row msg-user">
        <div className="msg-bubble user-bubble">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div
      className="msg-row msg-assistant fade-in"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="msg-meta">
        <span className="msg-label">CodeLens</span>
        {message.stats && (
          <span className="msg-stats">
            {message.stats.retrieved_count} retrieved · {message.stats.expanded_count} expanded
          </span>
        )}
        {message.sources && message.sources.length > 0 && (hovered || isActive) && (
          <button
            className={`view-sources-btn ${isActive ? 'active' : ''}`}
            onClick={() => onViewSources(message.sources)}
            title="View sources for this response"
          >
            {isActive ? '● sources' : '○ view sources'}
          </button>
        )}
      </div>
      <div className="msg-bubble assistant-bubble">
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
                {line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((seg, k) => {
                  if (seg.startsWith('**') && seg.endsWith('**')) {
                    return <strong key={k}>{seg.slice(2, -2)}</strong>
                  }
                  if (seg.startsWith('`') && seg.endsWith('`')) {
                    return <code key={k} className="inline-code">{seg.slice(1, -1)}</code>
                  }
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

function ThinkingBubble() {
  return (
    <div className="msg-row msg-assistant fade-in">
      <div className="msg-meta">
        <span className="msg-label">CodeLens</span>
      </div>
      <div className="msg-bubble assistant-bubble thinking-bubble">
        <span className="thinking-dot" style={{ animationDelay: '0s' }} />
        <span className="thinking-dot" style={{ animationDelay: '0.2s' }} />
        <span className="thinking-dot" style={{ animationDelay: '0.4s' }} />
      </div>
    </div>
  )
}

export default function ChatInterface({ repoData }) {
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeSources, setActiveSources] = useState([])
  const [activeSourcesMsgIndex, setActiveSourcesMsgIndex] = useState(null)
  const [sourcesPanelWidth, setSourcesPanelWidth] = useState(340)

  const isDragging = useRef(false)
  const dragStartX = useRef(0)
  const dragStartWidth = useRef(0)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Auto-grow textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      const scrollH = inputRef.current.scrollHeight
      inputRef.current.style.height = `${Math.min(scrollH, 160)}px`
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
      const newWidth = Math.min(Math.max(dragStartWidth.current + delta, 220), 560)
      setSourcesPanelWidth(newWidth)
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
      const userMsg = messages[i]
      const assistantMsg = messages[i + 1]
      if (userMsg && assistantMsg) {
        turns.push({ query: userMsg.content, answer: assistantMsg.content })
      }
    }
    return turns.slice(-2)
  }

  async function handleSend() {
    const q = query.trim()
    if (!q || loading) return
    setQuery('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)
    try {
      const history = buildHistory()
      const data = await queryRepo(repoData.repo_id, q, history)
      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        stats: {
          retrieved_count: data.retrieved_count,
          expanded_count: data.expanded_count,
        },
      }
      setMessages(prev => {
        const next = [...prev, assistantMsg]
        setActiveSourcesMsgIndex(next.length - 1)
        return next
      })
      setActiveSources(data.sources || [])
    } catch (err) {
      const msg = err.response?.data?.detail || 'Query failed. Please try again.'
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${msg}`,
        sources: [],
        stats: null,
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleViewSources(sources, msgIndex) {
    setActiveSources(sources)
    setActiveSourcesMsgIndex(msgIndex)
  }

  const isEmpty = messages.length === 0

  return (
    <div className="chat-layout">
      {/* LEFT: chat panel */}
      <div className="chat-panel">
        {isEmpty ? (
          <div className="chat-empty">
            <div className="empty-icon">⬡</div>
            <p className="empty-title">Ready to explore</p>
            <p className="empty-sub">
              Ask anything about <span className="empty-repo">{repoData.full_name}</span>
            </p>
            <div className="empty-suggestions">
              {[
                'How does request routing work?',
                'What is the main entry point?',
                'How is error handling implemented?',
                'What design patterns are used?',
              ].map(s => (
                <button key={s} className="suggestion-chip" onClick={() => setQuery(s)}>
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
                onViewSources={(sources) => handleViewSources(sources, i)}
                isActive={activeSourcesMsgIndex === i}
              />
            ))}
            {loading && <ThinkingBubble />}
            <div ref={bottomRef} />
          </div>
        )}

        <div className="chat-input-bar">
          <div className="chat-input-wrap">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder={`Ask about ${repoData.full_name}...`}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              rows={1}
            />
            <button
              className="btn-icon"
              onClick={handleSend}
              disabled={loading || !query.trim()}
              aria-label="Send"
            >
              ↑
            </button>
          </div>
          <p className="input-hint">Enter to send · Shift+Enter for newline</p>
        </div>
      </div>

      {/* RESIZE HANDLE — sits between chat and sources as a flex child */}
      <div
        className="panel-resize-handle"
        onMouseDown={onDragStart}
        title="Drag to resize"
      />

      {/* RIGHT: sources panel — width controlled by state */}
      <div className="sources-panel-wrapper" style={{ width: `${sourcesPanelWidth}px` }}>
        <SourcesPanel
          sources={activeSources}
          repoData={repoData}
        />
      </div>
    </div>
  )
}