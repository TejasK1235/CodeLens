import { useState } from 'react'
import RepoInput from './components/RepoInput'
import IndexingProgress from './components/IndexingProgress'
import ChatInterface from './components/ChatInterface'
import './App.css'

export default function App() {
  const [phase, setPhase] = useState('input')
  const [repoData, setRepoData] = useState(null)
  const [indexingInfo, setIndexingInfo] = useState(null)

  function handleIndexStarted(data) {
    if (data.status === 'cached') {
      setRepoData(data)
      setPhase('chat')
    } else {
      setIndexingInfo(data)
      setPhase('indexing')
    }
  }

  function handleIndexComplete(statusData, originalData) {
    setRepoData({ ...originalData, ...statusData })
    setPhase('chat')
  }

  function handleNewRepo() {
    setPhase('input')
    setRepoData(null)
    setIndexingInfo(null)
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-logo">
          <span className="logo-icon">⬡</span>
          <span className="logo-text">CodeLens</span>
        </div>
        {repoData && (
          <div className="header-repo">
            {/* repo name only — no commit hash exposed in UI */}
            <span className="repo-name">{repoData.full_name}</span>
          </div>
        )}
        {(phase === 'chat' || phase === 'indexing') && (
          <button className="btn-ghost btn-sm" onClick={handleNewRepo}>
            + New repo
          </button>
        )}
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
          <ChatInterface repoData={repoData} />
        )}
      </main>
    </div>
  )
}