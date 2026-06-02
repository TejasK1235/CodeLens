import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing Supabase environment variables. Check your .env file.')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// ── Indexed repos ──────────────────────────────────────────────

export async function saveIndexedRepo(userId, repoData) {
  const { data, error } = await supabase
    .from('indexed_repos')
    .upsert({
      user_id: userId,
      repo_id: repoData.repo_id,
      full_name: repoData.full_name,
      github_url: `https://github.com/${repoData.full_name}`,
      commit_hash: repoData.commit_hash || '',
      chunk_count: repoData.chunk_count || 0,
      last_queried_at: new Date().toISOString(),
    }, { onConflict: 'user_id,repo_id' })
    .select()
    .single()
  if (error) console.error('saveIndexedRepo error:', error)
  return data
}

export async function getUserRepos(userId) {
  const { data, error } = await supabase
    .from('indexed_repos')
    .select('*')
    .eq('user_id', userId)
    .order('last_queried_at', { ascending: false })
  if (error) console.error('getUserRepos error:', error)
  return data || []
}

export async function updateRepoLastQueried(userId, repoId) {
  await supabase
    .from('indexed_repos')
    .update({ last_queried_at: new Date().toISOString() })
    .eq('user_id', userId)
    .eq('repo_id', repoId)
}

// ── Conversations ──────────────────────────────────────────────

export async function createConversation(userId, repoId, repoFullName, firstQuery) {
  const title = firstQuery.length > 60
    ? firstQuery.slice(0, 60) + '...'
    : firstQuery
  const { data, error } = await supabase
    .from('conversations')
    .insert({
      user_id: userId,
      repo_id: repoId,
      repo_full_name: repoFullName,
      title,
    })
    .select()
    .single()
  if (error) console.error('createConversation error:', error)
  return data
}

export async function getUserConversations(userId, repoId = null) {
  let query = supabase
    .from('conversations')
    .select('*')
    .eq('user_id', userId)
    .order('updated_at', { ascending: false })
  if (repoId) {
    query = query.eq('repo_id', repoId)
  }
  const { data, error } = await query
  if (error) console.error('getUserConversations error:', error)
  return data || []
}

export async function updateConversationTimestamp(conversationId) {
  await supabase
    .from('conversations')
    .update({ updated_at: new Date().toISOString() })
    .eq('id', conversationId)
}

export async function deleteConversation(conversationId) {
  const { error } = await supabase
    .from('conversations')
    .delete()
    .eq('id', conversationId)
  if (error) console.error('deleteConversation error:', error)
}

// ── Messages ──────────────────────────────────────────────────

export async function saveMessage(conversationId, userId, role, content, sources = [], stats = null) {
  const { data, error } = await supabase
    .from('messages')
    .insert({
      conversation_id: conversationId,
      user_id: userId,
      role,
      content,
      sources,
      stats,
    })
    .select()
    .single()
  if (error) console.error('saveMessage error:', error)
  return data
}

export async function getConversationMessages(conversationId) {
  const { data, error } = await supabase
    .from('messages')
    .select('*')
    .eq('conversation_id', conversationId)
    .order('created_at', { ascending: true })
  if (error) console.error('getConversationMessages error:', error)
  return data || []
}