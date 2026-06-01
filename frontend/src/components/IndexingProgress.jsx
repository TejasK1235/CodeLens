import { useEffect, useState } from 'react'
import { pollStatus } from '../api'
import './IndexingProgress.css'

const STAGES = [
  { key: 'queued',    label: 'Queued',                    order: 0 },
  { key: 'cloning',  label: 'Cloning repository',         order: 1 },
  { key: 'parsing',  label: 'Parsing files (tree-sitter)',order: 2 },
  { key: 'chunking', label: 'Validating chunks',          order: 3 },
  { key: 'embedding',label: 'Embedding chunks',           order: 4 },
  { key: 'storing',  label: 'Saving to ChromaDB',         order: 5 },
  { key: 'ready',    label: 'Complete',                   order: 6 },
]

function getStageOrder(status) {
  const s = STAGES.find(s => s.key === status)
  return s ? s.order : 0
}

export default function IndexingProgress({ indexingInfo, onComplete }) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!indexingInfo?.repo_id) return
    let cancelled = false

    async function poll() {
      while (!cancelled) {
        try {
          const data = await pollStatus(indexingInfo.repo_id)
          if (!cancelled) {
            setStatus(data)
            if (data.status === 'ready') {
              onComplete(data, indexingInfo)
              return
            }
            if (data.status === 'error') {
              setError(data.stage || 'Indexing failed.')
              return
            }
          }
        } catch (err) {
          if (!cancelled) {
            setError('Lost connection to backend.')
            return
          }
        }
        await new Promise(r => setTimeout(r, 2000))
      }
    }

    poll()
    return () => { cancelled = true }
  }, [indexingInfo?.repo_id])

  const currentOrder = getStageOrder(status?.status || 'queued')
  const progress = status?.chunks_total > 0
    ? Math.round((status.chunks_processed / status.chunks_total) * 100)
    : null

  return (
    <div className="indexing-screen">
      <div className="indexing-card fade-in">
        <div className="indexing-header">
          <div className="indexing-title-row">
            <span className="indexing-repo">{indexingInfo?.full_name}</span>
            <span className="indexing-badge">indexing</span>
          </div>
          <span className="indexing-commit">{indexingInfo?.commit_hash}</span>
        </div>

        <div className="stages-list">
          {STAGES.filter(s => s.key !== 'ready').map((stage) => {
            const stageOrder = stage.order
            const isDone    = currentOrder > stageOrder
            const isActive  = currentOrder === stageOrder
            const isPending = currentOrder < stageOrder

            return (
              <div
                key={stage.key}
                className={`stage-row ${isDone ? 'done' : isActive ? 'active' : 'pending'}`}
              >
                <div className="stage-indicator">
                  {isDone ? (
                    <span className="stage-check">✓</span>
                  ) : isActive ? (
                    <span className="stage-spinner" />
                  ) : (
                    <span className="stage-dot" />
                  )}
                </div>
                <span className="stage-label">{stage.label}</span>
                {isActive && status?.chunks_total > 0 && (
                  <span className="stage-count">
                    {status.chunks_processed} / {status.chunks_total}
                  </span>
                )}
              </div>
            )
          })}
        </div>

        {progress !== null && (
          <div className="progress-bar-wrap">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        {error && (
          <div className="indexing-error fade-in">
            <span>⚠</span> {error}
          </div>
        )}

        <p className="indexing-note">
          First-time indexing takes 1–3 minutes. Subsequent queries on this repo are instant.
        </p>
      </div>
    </div>
  )
}