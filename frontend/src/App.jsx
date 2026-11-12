
import { useEffect, useRef, useState } from "react";

import {
  ArrowUp,
  BookOpen,
  ExternalLink,
  FileText,
  GraduationCap,
  Menu,
  MessageSquare,
  Plus,
  ShieldCheck,
} from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./App.css";

// --------------------------------------------------
// Configuration
// --------------------------------------------------

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const DOCUMENTS = {
  "Academic-Calendar-2026-27.txt": {
    pdf: "Academic-Calendar-2026-27.pdf",
    title: "Academic Calendar 2026–27",
  },

  "Examination-Ordinance-2022.txt": {
    pdf: "Examination-Ordinance-2022.pdf",
    title: "Examination Ordinance 2022",
  },

  "Examination_Ordinances_2020.txt": {
    pdf: "Examination_Ordinances_2020.pdf",
    title: "Examination Ordinance 2020",
  },
};

const SUGGESTIONS = [
  "When does Semester II begin for second-year students?",
  "What are the examination backlog rules?",
  "What does the 2022 ordinance say about revaluation?",
  "When are the Semester I examinations?",
];

// --------------------------------------------------
// Markdown Cleanup
// --------------------------------------------------


function cleanMarkdown(content) {
  if (typeof content !== "string") return "";

  let cleaned = content.replace(/\r\n?/g, "\n");

  // Remove standalone source references.
  // Handles both bold and plain-text source lines.
  cleaned = cleaned.replace(
    /^[ \t]*(?:\*\*)?Source:\s*[A-Za-z0-9_.-]+\.txt\s*,\s*Page\s*:?\s*\d+(?:\*\*)?[ \t]*$/gim,
    ""
  );

  // Remove source references enclosed in parentheses.
  cleaned = cleaned.replace(
    /^[ \t]*\(?\*{0,2}Source:\s*[A-Za-z0-9_.-]+\.txt\s*,\s*Page\s*:?\s*\d+\*{0,2}\)?[ \t]*$/gim,
    ""
  );

  // Remove empty Markdown bullets.
  cleaned = cleaned.replace(
    /^[ \t]*[-*+•][ \t]*$/gm,
    ""
  );

  // Remove empty numbered list items.
  cleaned = cleaned.replace(
    /^[ \t]*\d+[.)][ \t]*$/gm,
    ""
  );

  // Remove duplicate Sources headings.
  cleaned = cleaned.replace(
    /^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?Sources(?:\*\*)?:?[ \t]*$/gim,
    ""
  );

  // Normalize excessive whitespace.
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");

  return cleaned.trim();
}


// --------------------------------------------------
// PDF Source Citations
// --------------------------------------------------

function SourceCitation({ citations = [] }) {
  const seen = new Set();

  const unique = citations.filter((citation) => {
    if (!citation || !DOCUMENTS[citation.document] || !Number.isInteger(Number(citation.page)) || Number(citation.page) < 1) {
      return false;
    }

    const key = `${citation.document}:${citation.page}`;

    if (seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });

  if (!unique.length) {
    return null;
  }

  return (
    <div className="citations">
      <div className="citations-heading">
        Sources
      </div>

      <div className="citations-list">
        {unique.map((citation) => {
          const document =
            DOCUMENTS[citation.document];

          if (!document) {
            return null;
          }

          const page = Number(citation.page);

          const validPage =
            Number.isInteger(page) && page > 0;

          const highlightText =
            typeof citation.highlight_text === "string"
              ? citation.highlight_text.trim()
              : "";

          const pdfBase =
            `${API_URL}/api/documents/` +
            encodeURIComponent(document.pdf);

          const url =
            validPage && highlightText.length >= 3
              ? `${pdfBase}/highlight?page=${page}` +
                `&text=${encodeURIComponent(highlightText)}` +
                `#page=${page}`
              : pdfBase +
                (validPage ? `#page=${page}` : "");

          return (
            <a
              className="citation-link"
              key={`${citation.document}-${citation.page}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <FileText size={14} />

              <span>
                {document.title}
                {validPage
                  ? ` · Page ${page}`
                  : ""}
              </span>

              <ExternalLink size={13} />
            </a>
          );
        })}
      </div>
    </div>
  );
}

// --------------------------------------------------
// Chat Message Component
// --------------------------------------------------

function Message({ message, onRetry }) {
  const isAssistant =
    message.role === "assistant";

  return (
    <div
      className={
        isAssistant
          ? "chat-message assistant-message"
          : "chat-message user-message"
      }
    >
      {isAssistant && (
        <div className="assistant-avatar">
          <GraduationCap size={17} />
        </div>
      )}

      <div className="message-content">
        {isAssistant && (
          <div className="message-author">
            CampusIQ
          </div>
        )}

        <div className="message-text">
          {isAssistant ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}

            >
              {cleanMarkdown(message.content)}
            </ReactMarkdown>
          ) : (
            message.content
          )}
        </div>

        {message.isError && (
          <button className="retry-button" onClick={() => onRetry(message.retryQuestion, message.retryHistory)}>
            Try again
          </button>
        )}

        {isAssistant && (
          <SourceCitation
            citations={message.citations || []}
          />
        )}

        {isAssistant &&
          message.validation?.status ===
            "unsupported" && (
            <div className="message-warning">
              This answer could not be fully
              verified.
            </div>
          )}
      </div>
    </div>
  );
}

// --------------------------------------------------
// Main App
// --------------------------------------------------

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] =
    useState(false);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const hasMessages = messages.length > 0;

  // --------------------------------------------------
  // Auto-scroll
  // --------------------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // --------------------------------------------------
  // Send Message + Conversation Memory
  // --------------------------------------------------

  async function sendMessage(text = input, retryHistory = null) {
    const question =
      typeof text === "string"
        ? text.trim()
        : "";

    if (!question || loading) {
      return;
    }

    // Capture previous messages before adding
    // the current user question.
    const history = retryHistory || messages
      .filter(
        (message) =>
          (message.role === "user" ||
            message.role === "assistant") &&
          !message.isError &&
          typeof message.content === "string"
      )
      .slice(-10)
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));

    setInput("");
    setLoading(true);

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(
        `${API_URL}/api/chat`,
        {
          method: "POST",
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: question,
            history: history,
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "CampusIQ could not process your request."
        );
      }

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          data.answer ||
          "No answer was returned.",
        citations: Array.isArray(data.citations)
          ? data.citations
          : [],
        validation: data.validation || null,
        cached: Boolean(data.cached),
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);
    } catch (error) {
      const errorMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          error.name === "AbortError"
            ? "The request timed out. Please try again."
            : error.message || "Something went wrong. Please try again.",
        retryQuestion: question,
        retryHistory: history,
        citations: [],
        isError: true,
      };

      setMessages((previous) => [
        ...previous,
        errorMessage,
      ]);
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  // --------------------------------------------------
  // New Conversation
  // --------------------------------------------------

  function newChat() {
    if (loading) {
      return;
    }

    setMessages([]);
    setInput("");
    setSidebarOpen(false);
    textareaRef.current?.focus();
  }

  // --------------------------------------------------
  // Keyboard Handling
  // --------------------------------------------------

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  // --------------------------------------------------
  // JSX
  // --------------------------------------------------

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close sidebar"
        />
      )}

      {/* Sidebar */}

      <aside
        className={`sidebar ${
          sidebarOpen ? "open" : ""
        }`}
      >
        <div className="sidebar-brand">
          <div className="brand-mark">
            <GraduationCap size={20} />
          </div>

          <div>
            <div className="brand-name">
              CampusIQ
            </div>

            <div className="brand-caption">
              MIT-WPU
            </div>
          </div>
        </div>

        <button
          className="new-chat-button"
          onClick={newChat}
          disabled={loading}
        >
          <Plus size={17} />
          New conversation
        </button>

        <div className="sidebar-section-title">
          Workspace
        </div>

        <div className="sidebar-navigation">
          <div className="sidebar-nav-item active">
            <MessageSquare size={16} />
            Academic assistant
          </div>

          <div className="sidebar-nav-item">
            <BookOpen size={16} />
            University knowledge
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-info">
            <ShieldCheck size={16} />
            <span>
              Document-grounded answers
            </span>
          </div>

          <div className="sidebar-disclaimer">
            Independent student project.
            Not an official MIT-WPU service.
          </div>
        </div>
      </aside>

      {/* Main Panel */}

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu-button"
              onClick={() =>
                setSidebarOpen(true)
              }
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>

            <span className="topbar-section">
              Academic intelligence
            </span>
          </div>

          <div className="topbar-right">
            <span className="topbar-indicator" />
            <span>Knowledge assistant</span>
          </div>
        </header>

        {/* Conversation */}

        <div
          className={`conversation ${
            !hasMessages ? "empty" : ""
          }`}
        >
          {!hasMessages ? (
            <div className="welcome">
              <div className="welcome-eyebrow">
                YOUR CAMPUS, MADE CLEARER
              </div>

              <h1>
                Ask better questions.
                <br />
                <span>
                  Find clearer answers.
                </span>
              </h1>

              <p className="welcome-description">
                Academic calendars, examination
                regulations, and university
                information — grounded in available
                MIT-WPU documents.
              </p>

              <div className="suggestion-grid">
                {SUGGESTIONS.map(
                  (suggestion) => (
                    <button
                      key={suggestion}
                      className="suggestion-card"
                      onClick={() =>
                        sendMessage(suggestion)
                      }
                      disabled={loading}
                    >
                      <span>{suggestion}</span>
                      <ArrowUp size={16} />
                    </button>
                  )
                )}
              </div>
            </div>
          ) : (
            <div className="messages-container">
              {messages.map((message) => (
                <Message
                  key={message.id}
                  message={message}
                  onRetry={sendMessage}
                />
              ))}

              {loading && (
                <div className="chat-message assistant-message">
                  <div className="assistant-avatar">
                    <GraduationCap size={17} />
                  </div>

                  <div className="message-content">
                    <div className="message-author">
                      CampusIQ
                    </div>

                    <div className="typing-indicator" role="status" aria-label="Finding evidence and preparing an answer">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Composer */}

        <div className="composer-area">
          <div className="composer">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              aria-label="Your academic question"
              maxLength={2000}
              placeholder="Ask anything about your university..."
              rows={1}
              disabled={loading}
            />

            <button
              className="send-button"
              onClick={() => sendMessage()}
              disabled={
                !input.trim() || loading
              }
              aria-label="Send message"
            >
              <ArrowUp size={19} />
            </button>
          </div>

          <p className="composer-disclaimer">
            CampusIQ can make mistakes.
            Verify important academic decisions
            with official university notices.
          </p>
        </div>
      </main>
    </div>
  );
}
