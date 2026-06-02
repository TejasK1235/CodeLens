import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function indexRepo(githubUrl) {
  const res = await axios.post(`${BASE}/index`, { github_url: githubUrl })
  return res.data
}

export async function pollStatus(repoId) {
  const res = await axios.get(`${BASE}/index/status/${repoId}`)
  return res.data
}

export async function queryRepo(repoId, query, conversationHistory = [], grievousMode = false) {
  const res = await axios.post(`${BASE}/query`, {
    repo_id: repoId,
    query,
    conversation_history: conversationHistory,
    grievous_mode: grievousMode,
  })
  return res.data
}

export async function healthCheck() {
  const res = await axios.get(`${BASE}/health`)
  return res.data
}

export async function deleteRepoFromBackend(repoId) {
  try {
    const res = await axios.delete(`${BASE}/repo/${repoId}`)
    return res.data
  } catch (err) {
    console.warn('Backend repo deletion failed (non-critical):', err)
    return null
  }
}