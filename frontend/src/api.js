import axios from 'axios'

const BASE = 'http://localhost:8000'

export async function indexRepo(githubUrl) {
  const res = await axios.post(`${BASE}/index`, { github_url: githubUrl })
  return res.data
}

export async function pollStatus(repoId) {
  const res = await axios.get(`${BASE}/index/status/${repoId}`)
  return res.data
}

export async function queryRepo(repoId, query, conversationHistory = []) {
  const res = await axios.post(`${BASE}/query`, {
    repo_id: repoId,
    query,
    conversation_history: conversationHistory,
  })
  return res.data
}

export async function healthCheck() {
  const res = await axios.get(`${BASE}/health`)
  return res.data
}