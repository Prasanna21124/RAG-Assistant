import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

const rawApiUrl = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').trim().replace(/\/+$/, '')
const API_URL = rawApiUrl
const API_KEY = (import.meta.env.VITE_API_KEY || 'my-super-secret-key-123').trim()

function getOrCreateUserId() {
  let id = localStorage.getItem('rag_user_id')
  if (!id) {
    id = 'u_' + Math.random().toString(36).substring(2, 9) + Date.now().toString(36)
    localStorage.setItem('rag_user_id', id)
  }
  return id
}
const USER_ID = getOrCreateUserId()

const HEADERS = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
  'X-User-Id': USER_ID,
}

/* ─── Typewriter ───────────────────────────── */
function useTypewriter(text, speed = 12) {
  const [out, setOut] = useState('')
  useEffect(() => {
    setOut('')
    if (!text) return
    let i = 0
    const id = setInterval(() => { i++; setOut(text.slice(0, i)); if (i >= text.length) clearInterval(id) }, speed)
    return () => clearInterval(id)
  }, [text])
  return out
}

/* ─── Toast ────────────────────────────────── */
function Toast({ toasts }) {
  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span>{t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : 'ℹ️'}</span>
          {t.msg}
        </div>
      ))}
    </div>
  )
}

function useToast() {
  const [toasts, setToasts] = useState([])
  const push = useCallback((msg, type = 'info') => {
    const id = Date.now()
    setToasts(p => [...p, { id, msg, type }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3000)
  }, [])
  return { toasts, push }
}

/* ─── Leaf logo ────────────────────────────── */
function LeafIcon({ size = 24 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <path d="M20 4C20 4 8 10 8 22C8 31 14 36 20 36C26 36 32 31 32 22C32 10 20 4 20 4Z" fill="currentColor" opacity=".9" />
      <path d="M14 28C14 28 20 20 28 16" stroke="white" strokeWidth="2" strokeLinecap="round" opacity=".6" />
    </svg>
  )
}

/* ─── Theme icons ──────────────────────────── */
const SunIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" /></svg>
const MoonIcon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" /></svg>

/* ─── Typing dots ──────────────────────────── */
const TypingDots = () => <span className="typing-dots"><span /><span /><span /></span>

/* ─── Format timestamp ─────────────────────── */
function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/* ─── Message ──────────────────────────────── */
function Message({ msg, isLatest, onCopy }) {
  const isUser = msg.role === 'user'
  const streamed = useTypewriter(!isUser && isLatest ? msg.content : null)
  const content = (!isUser && isLatest) ? streamed : msg.content
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(msg.content)
    setCopied(true)
    onCopy()
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`msg-row ${isUser ? 'msg-user' : 'msg-ai'}`}>
      {!isUser && <div className="ai-avatar"><LeafIcon size={16} /></div>}
      <div className={`msg-bubble ${isUser ? 'bubble-user' : 'bubble-ai'}`}>
        {isUser
          ? <p>{content}</p>
          : <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || '\u200b'}</ReactMarkdown>
        }
        <div className="msg-meta">
          <span className="msg-time">{formatTime(msg.ts)}</span>
          {!isUser && (
            <button className="copy-btn" onClick={copy} title="Copy">
              {copied ? '✓ Copied' : '⧉ Copy'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Sidebar Thread Item ──────────────────── */
function ThreadItem({ session, active, onClick, onRename, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(session)
  const inputRef = useRef(null)

  useEffect(() => { if (editing) inputRef.current?.focus() }, [editing])

  function commit() {
    setEditing(false)
    if (val.trim() && val !== session) onRename(session, val.trim())
    else setVal(session)
  }

  return (
    <div className={`thread-item ${active ? 'thread-active' : ''}`} onClick={onClick}>
      <svg className="thread-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {editing ? (
        <input
          ref={inputRef}
          className="thread-rename-input"
          value={val}
          onChange={e => setVal(e.target.value)}
          onBlur={commit}
          onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setEditing(false); setVal(session) } }}
          onClick={e => e.stopPropagation()}
        />
      ) : (
        <span className="thread-name">{session}</span>
      )}
      <div className="thread-actions" onClick={e => e.stopPropagation()}>
        <button title="Rename" onClick={() => setEditing(true)}>✎</button>
        <button title="Delete" className="del-btn" onClick={() => onDelete(session)}>×</button>
      </div>
    </div>
  )
}

/* ─── Main App ─────────────────────────────── */
export default function App() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('theme')
    if (saved !== null) return saved === 'dark'
    return true // Default to dark mode
  })
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('sidebarOpen')
    return saved !== null ? saved === 'true' : true
  })
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('currentSession') || 'default'
  })
  const [sessions, setSessions] = useState([])
  const [sessionTitles, setSessionTitles] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sessionTitles')) || {} }
    catch { return {} }
  })
  const [sessionsLoaded, setSessionsLoaded] = useState(false)
  const [docs, setDocs] = useState(() => {
    try {
      const cached = JSON.parse(localStorage.getItem('rag_cached_docs'))
      if (Array.isArray(cached) && cached.length > 0) return cached
    } catch { }
    return ['amazon.csv']
  })
  const [sidebarSearch, setSidebarSearch] = useState('')
  const [apiStatus, setApiStatus] = useState('checking')
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const { toasts, push: pushToast } = useToast()

  const updateDocs = useCallback((newDocs) => {
    if (Array.isArray(newDocs)) {
      setDocs(newDocs)
      try {
        localStorage.setItem('rag_cached_docs', JSON.stringify(newDocs))
      } catch { }
    }
  }, [])

  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const chatViewRef = useRef(null)

  /* Theme */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  /* Health check every 5s and sync indexed documents */
  useEffect(() => {
    async function check() {
      try {
        const r = await fetch(`${API_URL}/health`, { headers: HEADERS })
        if (r.ok) {
          const d = await r.json()
          setApiStatus('online')
          if (Array.isArray(d.documents)) {
            updateDocs(d.documents)
          }
        } else {
          setApiStatus('offline')
        }
      } catch {
        setApiStatus('offline')
      }
    }
    check()
    const id = setInterval(check, 5000)
    return () => clearInterval(id)
  }, [updateDocs])

  /* Re-fetch docs & sessions whenever the API comes online (catches delayed startup) */
  useEffect(() => {
    if (apiStatus === 'online') fetchDocs()
  }, [apiStatus])

  /* Scroll-to-bottom button visibility */
  useEffect(() => {
    const el = chatViewRef.current
    if (!el) return
    const onScroll = () => {
      setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200)
    }
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  /* Keyboard shortcuts */
  useEffect(() => {
    function onKey(e) {
      if (e.altKey && e.key.toLowerCase() === 'n') { e.preventDefault(); newChat() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  /* Persist Session ID */
  useEffect(() => {
    localStorage.setItem('currentSession', sessionId)
  }, [sessionId])

  /* Persist Sidebar State */
  useEffect(() => {
    localStorage.setItem('sidebarOpen', sidebarOpen)
  }, [sidebarOpen])

  /* Focus textarea on mount (refresh) */
  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [])

  /* Focus textarea whenever session changes (chat switch) */
  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 50)
  }, [sessionId])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])
  useEffect(() => { loadHistory(); fetchSessions(); fetchDocs() }, [sessionId])


  /* ── API ── */
  async function loadHistory() {
    try {
      const r = await fetch(`${API_URL}/history/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(USER_ID)}`, { headers: HEADERS })
      if (r.ok) {
        const d = await r.json()
        setMessages(d.history.map(h => ({ role: h.role, content: h.content, ts: new Date().toISOString(), isHistory: true })))
      }
    } catch { }
  }

  async function fetchSessions() {
    try {
      const r = await fetch(`${API_URL}/sessions?user_id=${encodeURIComponent(USER_ID)}`, { headers: HEADERS })
      if (r.ok) { const d = await r.json(); setSessions(d.sessions || []) }
    } catch { }
    finally { setSessionsLoaded(true) }
  }

  async function fetchDocs() {
    try {
      const r = await fetch(`${API_URL}/documents`, { headers: HEADERS })
      if (r.ok) { const d = await r.json(); updateDocs(d.documents || []) }
    } catch { }
  }

  async function clearHistory() {
    await fetch(`${API_URL}/history/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(USER_ID)}`, { method: 'DELETE', headers: HEADERS })
    setMessages([])
    pushToast('Chat history cleared', 'success')
  }

  async function deleteSession(sid) {
    await fetch(`${API_URL}/history/${encodeURIComponent(sid)}?user_id=${encodeURIComponent(USER_ID)}`, { method: 'DELETE', headers: HEADERS })
    pushToast(`Session "${sid}" deleted`, 'success')
    if (sid === sessionId) { setSessionId('default'); setMessages([]) }
    fetchSessions()
  }

  function renameSession(id, newTitle) {
    setSessionTitles(prev => {
      const updated = { ...prev, [id]: newTitle }
      localStorage.setItem('sessionTitles', JSON.stringify(updated))
      return updated
    })
    pushToast('Chat renamed', 'success')
  }


  /* Export chat */
  function exportChat() {
    if (!messages.length) { pushToast('Nothing to export yet', 'info'); return }
    const lines = messages.map(m => `[${formatTime(m.ts)}] ${m.role.toUpperCase()}: ${m.content}`)
    const blob = new Blob([lines.join('\n\n')], { type: 'text/plain' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `chat-${sessionId}-${Date.now()}.txt`; a.click()
    pushToast('Chat exported!', 'success')
  }

  /* Send */
  async function sendMessage(directQuery) {
    const query = (directQuery || input).trim(); if (!query || loading) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    // Automatically name the chat if this is the very first message
    if (messages.length === 0) {
      const title = query.slice(0, 35) + (query.length > 35 ? '...' : '')
      setSessionTitles(prev => {
        const updated = { ...prev, [sessionId]: title }
        localStorage.setItem('sessionTitles', JSON.stringify(updated))
        return updated
      })
    }

    const ts = new Date().toISOString()
    setMessages(prev => [...prev, { role: 'user', content: query, ts }])
    setLoading(true)
    try {
      const r = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: HEADERS,
        body: JSON.stringify({ query, session_id: sessionId, user_id: USER_ID }),
      })
      const d = await r.json()
      setMessages(prev => [...prev, { role: 'assistant', content: r.ok ? d.answer : `⚠ ${d.detail || 'Error'}`, ts: new Date().toISOString() }])
      if (!r.ok) pushToast('API returned an error', 'error')
    } catch (err) {
      console.error('API request failed:', err)
      setMessages(prev => [...prev, { role: 'assistant', content: `⚠ Cannot connect to the API (${err.message || 'Network error'}). Make sure the server is online.`, ts: new Date().toISOString() }])
      pushToast('Cannot reach the API server', 'error')
    }
    setLoading(false)
    fetchSessions()
  }

  function onKeyDown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }

  function autoResize(e) {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px'
  }

  function newChat() {
    const id = `chat-${Date.now()}`
    setSessionId(id)
    setMessages([])
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      // Use setTimeout to ensure focus runs after React re-renders
      setTimeout(() => textareaRef.current?.focus(), 0)
    }
  }

  function scrollToBottom() { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }

  const filtered = sessions.filter(s => {
    const title = sessionTitles[s] || s
    return title.toLowerCase().includes(sidebarSearch.toLowerCase())
  })

  return (
    <div className="app">
      {/* Sidebar */}
      <div className={`sidebar-overlay ${sidebarOpen ? 'overlay-open' : 'overlay-closed'}`} onClick={() => setSidebarOpen(false)} />
      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
        <div className="sidebar-top">
          <button className="menu-btn" onClick={() => setSidebarOpen(o => !o)} title="Toggle sidebar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          {sidebarOpen && <span className="sidebar-label">THREADS</span>}
        </div>

        {sidebarOpen && (
          <div className="sidebar-search-wrap">
            <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" strokeLinecap="round" />
            </svg>
            <input className="sidebar-search" placeholder="Search threads..." value={sidebarSearch} onChange={e => setSidebarSearch(e.target.value)} />
            {sidebarSearch && (
              <button className="clear-search-btn" onClick={() => setSidebarSearch('')} title="Clear search">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
        )}

        <div className="thread-list">
          {sidebarOpen && sessionsLoaded && filtered.length === 0 && (
            <div className="no-threads">
              <p>No conversations yet</p>
              <span>Start chatting to see threads here!</span>
            </div>
          )}
          {filtered.map(s => (
            <ThreadItem
              key={s}
              session={sessionTitles[s] || s}
              active={s === sessionId}
              onClick={() => setSessionId(s)}
              onRename={(oldTitle, newTitle) => renameSession(s, newTitle)}
              onDelete={() => deleteSession(s)}
            />
          ))}
        </div>

        {sidebarOpen && (
          <div className="sidebar-footer">
            <button className="footer-link" onClick={exportChat}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
              <span>Download Chat</span>
            </button>
            <button className="footer-link danger" onClick={clearHistory}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M9 6V4h6v2" /></svg>
              <span>Clear Chat</span>
            </button>
          </div>
        )}
      </aside>


      {/* Main */}
      <main className="main">
        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-logo">
            {!sidebarOpen && (
              <button className="menu-btn" onClick={() => setSidebarOpen(true)} title="Open sidebar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            )}
            <LeafIcon size={26} />
            <span>AI Assistant</span>
          </div>
          <div className="topbar-right">
            <button className="theme-toggle" onClick={() => setDark(d => !d)} title="Toggle theme">
              {dark ? <SunIcon /> : <MoonIcon />}
            </button>
            <button className="new-chat-btn" onClick={newChat} title="Alt+N">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
              New Chat
            </button>
          </div>
        </header>

        {/* Chat viewport */}
        <div className="chat-view" ref={chatViewRef}>
          {messages.length === 0 && !loading ? (
            <div className="greeting">
              <div className="greeting-logo"><LeafIcon size={52} /></div>
              <h1 className="greeting-heading">What can I help with?</h1>
              <p className="greeting-sub">I'm your AI assistant trained on your business documents.</p>
              <div className="suggestion-row">
                {(docs.length > 0 ? [
                  'Give me a comprehensive summary of the uploaded documents.',
                  'What are the main topics discussed in these files?',
                  'Can you extract the key insights and takeaways from my data?'
                ] : [
                  'What kind of documents can I upload?',
                  'How does this AI work?',
                  'What are the capabilities of this AI?'
                ]).map((s, i) => (
                  <button key={i} className="suggestion-pill" onClick={() => sendMessage(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((m, i) => (
                <Message key={i} msg={m}
                  isLatest={!m.isHistory && i === messages.length - 1 && m.role === 'assistant'}
                  onCopy={() => pushToast('Copied to clipboard!', 'success')}
                />
              ))}
              {loading && (
                <div className="msg-row msg-ai">
                  <div className="ai-avatar"><LeafIcon size={16} /></div>
                  <div className="msg-bubble bubble-ai"><TypingDots /></div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}


        </div>

        {/* Scroll-to-bottom button — anchored above the input bar */}
        {showScrollBtn && messages.length > 0 && (
          <div className="scroll-btn-wrap">
            <button className="scroll-down-btn" onClick={scrollToBottom} title="Scroll to bottom">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          </div>
        )}

        {/* Input area */}
        <div className="input-area">
          <div className="input-box">

            <textarea
              ref={textareaRef}
              className="chat-textarea"
              placeholder="Type your question..."
              value={input}
              onChange={autoResize}
              onKeyDown={onKeyDown}
              rows={1}
              disabled={loading}
            />
            <div className="input-right">
              <button className={`send-btn ${input.trim() && !loading ? 'send-active' : ''}`}
                onClick={sendMessage} disabled={!input.trim() || loading}>
                <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" stroke="currentColor">
                  <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
