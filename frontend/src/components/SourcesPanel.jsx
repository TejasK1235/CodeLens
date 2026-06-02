import './SourcesPanel.css'

function SourceCard({ source, index }) {
  const isExpanded = source.is_expanded
  const similarity = source.similarity

  function handleCardClick(e) {
    // Don't double-trigger if clicking the link itself
    if (e.target.tagName === 'A') return
    window.open(source.github_url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      className={`source-card fade-in ${isExpanded ? 'source-expanded' : 'source-retrieved'}`}
      style={{ animationDelay: `${index * 0.05}s` }}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && handleCardClick(e)}
      title="Open in GitHub"
    >
      <div className="source-card-header">
        <div className="source-name-row">
          <span className="source-index">{index + 1}</span>
          <span className="source-name">{source.name}</span>
          {isExpanded && <span className="source-tag expanded-tag">expanded</span>}
        </div>
        {similarity !== null && similarity !== undefined && (
          <div className="source-score-bar">
            <div
              className="source-score-fill"
              style={{ width: `${Math.round(similarity * 100)}%` }}
            />
            <span className="source-score-val">{similarity.toFixed(2)}</span>
          </div>
        )}
      </div>

      <div className="source-file">
        <span className="source-file-path">{source.file_path}</span>
        <span className="source-lines">L{source.start_line}–{source.end_line}</span>
      </div>

      <a
        href={source.github_url}
        target="_blank"
        rel="noopener noreferrer"
        className="source-link"
        onClick={e => e.stopPropagation()}
      >
        View on GitHub ↗
      </a>
    </div>
  )
}

export default function SourcesPanel({ sources, repoData }) {
  const retrieved = sources.filter(s => !s.is_expanded)
  const expanded  = sources.filter(s => s.is_expanded)

  return (
    <div className="sources-panel">
      <div className="sources-header">
        <span className="sources-title">Sources</span>
        {sources.length > 0 && (
          <span className="sources-count">{sources.length} chunks</span>
        )}
      </div>

      <div className="sources-scroll">
        {sources.length === 0 ? (
          <div className="sources-empty">
            <p>Sources will appear here after your first query.</p>
            <p className="sources-empty-hint">Hover over any response to revisit its sources.</p>
          </div>
        ) : (
          <>
            {retrieved.length > 0 && (
              <div className="sources-group">
                <div className="sources-group-label">
                  <span className="group-dot retrieved-dot" />
                  Retrieved ({retrieved.length})
                </div>
                {retrieved.map((s, i) => (
                  <SourceCard key={s.chunk_id || i} source={s} index={i} />
                ))}
              </div>
            )}
            {expanded.length > 0 && (
              <div className="sources-group">
                <div className="sources-group-label">
                  <span className="group-dot expanded-dot" />
                  Dependency expanded ({expanded.length})
                </div>
                {expanded.map((s, i) => (
                  <SourceCard key={s.chunk_id || i} source={s} index={retrieved.length + i} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}