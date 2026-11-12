import { useEffect, useRef, useState } from "react";
import {
  ArrowDown, ArrowRight, ArrowUp, BookOpen, CalendarDays,
  Check, CheckCircle2, ChevronRight, CircleAlert, Clock3,
  FileText, GraduationCap, Menu, MessageCircle, Plus,
  RotateCcw, ShieldCheck, Sparkles, X,
} from "lucide-react";
import "./App.css";

const API_BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const EXAMPLES = [
  { icon: CalendarDays, eyebrow: "Academic calendar", label: "When does Semester II begin for second-year students?" },
  { icon: FileText, eyebrow: "Examinations", label: "What are the rules for revaluation?" },
  { icon: GraduationCap, eyebrow: "Academic policies", label: "What are the ATKT and backlog rules?" },
];
const INITIAL_MESSAGE = {
  id: "intro",
  role: "assistant",
  intro: true,
};

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatSourceName(name) {
  return (name || "University document")
    .replace(/\.txt$/i, "")
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function verificationLabel(validation) {
  // IMPORTANT: backend 'verified' checks dates, not every factual claim.
  if (validation?.status === "verified") {
    return { label: "Dates checked against source", type: "verified" };
  }
  if (validation?.status === "unsupported") {
    return { label: "Date verification unsuccessful", type: "warning" };
  }
  return { label: "Date verification not performed", type: "neutral" };
}

function SourceList({ citations = [], sources = [] }) {
  const uniqueCitations = citations.filter((item, index, list) =>
    item && list.findIndex(other => other?.document === item.document && other?.page === item.page) === index
  );

  if (uniqueCitations.length > 0) {
    return (
      <div className="source-list" aria-label="Document references">
        {uniqueCitations.map((citation, index) => (
          <div className="source-item" key={`${citation.document}-${citation.page}-${index}`}>
            <FileText size={14} strokeWidth={1.8} aria-hidden="true" />
            <span>{formatSourceName(citation.document)}</span>
            {citation.page != null && <strong>p. {citation.page}</strong>}
          </div>
        ))}
      </div>
    );
  }
  if (!sources.length) return null;
  return (
    <div className="source-list" aria-label="Source documents">
      {sources.map((name, index) => (
        <div className="source-item" key={`${name}-${index}`}>
          <FileText size={14} strokeWidth={1.8} aria-hidden="true" />
          <span>{formatSourceName(name)}</span>
        </div>
      ))}
    </div>
  );
}

function AssistantMessage({ message }) {
  const [showSources, setShowSources] = useState(false);
  if (message.intro) return null;
  const verification = verificationLabel(message.validation);
  const hasSources = Boolean(message.citations?.length || message.sources?.length);

  return (
    <article className="message message--assistant">
      <div className="assistant-avatar" aria-hidden="true"><BookOpen size={17} strokeWidth={1.9} /></div>
      <div className="message-content">
        <div className="message-author">CampusIQ <span>Academic assistant</span></div>
        <div className="answer-text">{message.answer}</div>
        <div className="answer-meta">
          {hasSources && (
            <button
              className="meta-button"
              type="button"
              aria-expanded={showSources}
              onClick={() => setShowSources(value => !value)}
            >
              <FileText size={14} aria-hidden="true" />
              {showSources ? "Hide sources" : "View sources"}
              <ChevronRight size={13} className={showSources ? "chevron chevron--open" : "chevron"} aria-hidden="true" />
            </button>
          )}
          <span className={`verification verification--${verification.type}`}>
            {verification.type === "verified" ? <CheckCircle2 size={14} aria-hidden="true" /> : <CircleAlert size={14} aria-hidden="true" />}
            {verification.label}
          </span>
          {message.cached && <span className="cache-note">Reused answer</span>}
        </div>
        {showSources && <SourceList citations={message.citations} sources={message.sources} />}
      </div>
    </article>
  );
}

function UserMessage({ message }) {
  return (
    <article className="message message--user">
      <div className="user-bubble">{message.content}</div>
    </article>
  );
}

function Intro({ onSuggestion }) {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-overline"><span className="overline-rule" /> A MORE CONSIDERED WAY TO FIND ANSWERS</div>
      <h1 id="welcome-title">Your campus,<br /><em>made clear.</em></h1>
      <p>Academic dates, examination policies, and university information — with the source material alongside every answer.</p>
      <div className="suggestion-heading">A GOOD PLACE TO START <ArrowDown size={13} aria-hidden="true" /></div>
      <div className="suggestion-grid">
        {EXAMPLES.map(({ icon: Icon, eyebrow, label }) => (
          <button type="button" className="suggestion-card" key={label} onClick={() => onSuggestion(label)}>
            <div className="suggestion-icon"><Icon size={19} strokeWidth={1.6} aria-hidden="true" /></div>
            <span className="suggestion-eyebrow">{eyebrow}</span>
            <span className="suggestion-label">{label}</span>
            <ArrowRight className="suggestion-arrow" size={17} aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  );
}

function App() {
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [view, setView] = useState("chat");
  const [health, setHealth] = useState("checking");
  const endRef = useRef(null);
  const textareaRef = useRef(null);
  const abortRef = useRef(null);

  const conversationStarted = messages.some(message => message.role === "user");
  const referenced = messages.flatMap(message => message.citations || []);
  const allSources = Array.from(new Map(referenced.map(citation => [`${citation.document}-${citation.page}`, citation])).values());

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/health`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error("API unavailable"); return response.json(); })
      .then(() => setHealth("online"))
      .catch(() => { if (!controller.signal.aborted) setHealth("offline"); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (conversationStarted && view === "chat") endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy, conversationStarted, view]);

  useEffect(() => () => abortRef.current?.abort(), []);

  function resizeComposer(value) {
    setDraft(value);
    requestAnimationFrame(() => {
      const element = textareaRef.current;
      if (!element) return;
      element.style.height = "auto";
      element.style.height = `${Math.min(element.scrollHeight, 168)}px`;
    });
  }

  function startNewChat() {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([INITIAL_MESSAGE]);
    setError("");
    setBusy(false);
    resizeComposer("");
    setView("chat");
    setSidebarOpen(false);
    textareaRef.current?.focus();
  }

  async function sendMessage(customMessage) {
    const question = (typeof customMessage === "string" ? customMessage : draft).trim();
    if (!question || busy) return;
    if (question.length > 2000) {
      setError("Please keep your question under 2,000 characters.");
      return;
    }

    setError("");
    setView("chat");
    setSidebarOpen(false);
    setMessages(previous => [...previous, { id: makeId(), role: "user", content: question }]);
    resizeComposer("");
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 90000);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "Unable to complete this request.";
        if (response.status === 429) throw new Error("Too many requests. Please try again shortly.");
        throw new Error(detail);
      }
      setMessages(previous => [...previous, {
        id: makeId(), role: "assistant", answer: data.answer || "No answer was returned.",
        sources: Array.isArray(data.sources) ? data.sources : [],
        citations: Array.isArray(data.citations) ? data.citations : [],
        validation: data.validation || null,
        cached: Boolean(data.cached),
      }]);
      setHealth("online");
    } catch (exception) {
      if (controller.signal.aborted) {
        // A new conversation intentionally cancels an in-flight request.
        if (abortRef.current === controller) setError("The request timed out. Please try again.");
      } else {
        setError(exception.message || "CampusIQ is temporarily unavailable.");
        if (exception instanceof TypeError) setHealth("offline");
      }
    } finally {
      clearTimeout(timeout);
      if (abortRef.current === controller) {
        abortRef.current = null;
        setBusy(false);
      }
    }
  }

  function handleComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      sendMessage();
    }
  }

  function handleSuggestion(question) {
    if (!busy) sendMessage(question);
  }

  return (
    <div className="campusiq-app">
      {sidebarOpen && <button type="button" className="sidebar-overlay" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <div className="brand-mark"><BookOpen size={22} strokeWidth={1.8} aria-hidden="true" /></div>
          <div className="brand-copy"><strong>CampusIQ</strong><span>ACADEMIC INTELLIGENCE</span></div>
          <button type="button" className="mobile-close icon-button" aria-label="Close menu" onClick={() => setSidebarOpen(false)}><X size={20} /></button>
        </div>

        <button type="button" className="new-chat" onClick={startNewChat}><Plus size={18} aria-hidden="true" /> New conversation <span className="new-chat-shortcut">+</span></button>

        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="sidebar-navigation" aria-label="Workspace">
          <button type="button" className={`nav-item ${view === "chat" ? "nav-item--active" : ""}`} onClick={() => { setView("chat"); setSidebarOpen(false); }}>
            <MessageCircle size={18} strokeWidth={1.7} aria-hidden="true" /> Assistant
          </button>
          <button type="button" className={`nav-item ${view === "sources" ? "nav-item--active" : ""}`} onClick={() => { setView("sources"); setSidebarOpen(false); }}>
            <BookOpen size={18} strokeWidth={1.7} aria-hidden="true" /> Referenced sources
            {allSources.length > 0 && <span className="nav-count">{allSources.length}</span>}
          </button>
        </nav>

        <div className="sidebar-separator" />
        <div className="sidebar-section-label">THIS SESSION</div>
        <p className="session-copy">Your conversation stays on this page. Starting a new conversation clears it.</p>

        <div className="sidebar-bottom">
          <div className="status-card">
            <div className="status-heading"><span className={`status-dot status-dot--${health}`} /> {health === "online" ? "API connected" : health === "offline" ? "API unavailable" : "Checking connection"}</div>
            <div className="status-caption">MIT-WPU document knowledge base</div>
          </div>
          <div className="disclaimer">Independent student project.<br />Not an official MIT-WPU service.</div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button type="button" className="mobile-menu icon-button" aria-label="Open menu" onClick={() => setSidebarOpen(true)}><Menu size={22} /></button>
            <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>{view === "sources" ? "Referenced sources" : "Academic assistant"}</strong></div>
          </div>
          <div className="topbar-right"><span className="topbar-edition">MIT-WPU · 2026–27</span><span className="topbar-separator" /><span className="topbar-project">STUDENT PROJECT</span></div>
        </header>

        {view === "sources" ? (
          <main className="sources-page">
            <div className="sources-inner">
              <span className="section-kicker">REFERENCE LIBRARY</span>
              <h1>Referenced sources<span className="heading-period">.</span></h1>
              <p className="sources-intro">Documents cited in answers during this session. References identify source files and pages; they are not direct download links.</p>
              {allSources.length ? (
                <div className="source-cards">
                  {allSources.map((citation, index) => (
                    <div className="source-card" key={`${citation.document}-${citation.page}-${index}`}>
                      <div className="source-card-icon"><FileText size={21} strokeWidth={1.6} /></div>
                      <div className="source-card-main"><h2>{formatSourceName(citation.document)}</h2><span>University document · {citation.page != null ? `Page ${citation.page}` : "Page not specified"}</span></div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-sources"><BookOpen size={27} strokeWidth={1.5} /><h2>No referenced sources yet</h2><p>Ask a question in the assistant. When a document is cited, its reference will appear here.</p><button type="button" onClick={() => setView("chat")}>Go to assistant <ArrowRight size={16} /></button></div>
              )}
            </div>
          </main>
        ) : (
          <main className={`chat-scroll ${conversationStarted ? "chat-scroll--active" : ""}`}>
            <div className="chat-content">
              {!conversationStarted ? (
                <Intro onSuggestion={handleSuggestion} />
              ) : (
                <div className="conversation" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions">
                  <div className="conversation-date"><Clock3 size={13} aria-hidden="true" /> Current session</div>
                  {messages.map(message => message.role === "user" ? <UserMessage key={message.id} message={message} /> : <AssistantMessage key={message.id} message={message} />)}
                  {busy && <div className="message message--assistant" role="status"><div className="assistant-avatar"><BookOpen size={17} /></div><div className="message-content"><div className="message-author">CampusIQ <span>Academic assistant</span></div><div className="thinking"><span className="thinking-dot" /><span className="thinking-dot" /><span className="thinking-dot" /><span>Consulting university documents…</span></div></div></div>}
                  <div ref={endRef} />
                </div>
              )}
            </div>
          </main>
        )}

        <div className="composer-region">
          {error && <div className="error-banner" role="alert"><CircleAlert size={17} /><span>{error}</span><button type="button" aria-label="Dismiss error" onClick={() => setError("")}><X size={16} /></button></div>}
          <form className="composer" onSubmit={event => { event.preventDefault(); sendMessage(); }}>
            <label className="sr-only" htmlFor="campusiq-question">Ask CampusIQ a question</label>
            <textarea
              id="campusiq-question"
              ref={textareaRef}
              value={draft}
              rows={1}
              maxLength={2000}
              disabled={busy}
              placeholder="Ask a question about your academics…"
              onChange={event => resizeComposer(event.target.value)}
              onKeyDown={handleComposerKeyDown}
            />
            <div className="composer-actions">
              <span className="composer-hint">Enter to send <span>·</span> Shift + Enter for a new line</span>
              <div className="composer-right"><span className="character-counter">{draft.length > 1800 ? `${draft.length}/2000` : ""}</span><button type="submit" disabled={busy || !draft.trim()} className="send-button" aria-label="Send message">{busy ? <span className="spinner" /> : <ArrowUp size={20} strokeWidth={2.1} />}</button></div>
            </div>
          </form>
          <p className="composer-footnote">CampusIQ uses indexed university documents. Always verify important academic decisions with official notices.</p>
        </div>
      </div>
    </div>
  );
}

export default App;
