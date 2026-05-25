import { useState, useEffect, useRef } from 'react'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { sql as sqlLang } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { useStore } from '../store/usestore'

/* ── CodeMirror SQL Viewer ───────────────────────────────────────────── */
function SQLViewer({ code }: { code: string }) {
  const editorRef = useRef<HTMLDivElement>(null)
  const viewRef = useRef<EditorView | null>(null)

  useEffect(() => {
    if (!editorRef.current) return
    if (viewRef.current) viewRef.current.destroy()

    const state = EditorState.create({
      doc: code,
      extensions: [
        sqlLang(),
        oneDark,
        EditorView.editable.of(false),
        EditorView.lineWrapping,
        EditorView.theme({
          '&': { background: 'transparent', fontSize: '12px' },
          '.cm-scroller': { fontFamily: "'Space Mono', monospace" },
          '.cm-content': { padding: '14px 16px' },
        }),
      ],
    })
    viewRef.current = new EditorView({ state, parent: editorRef.current })
    return () => viewRef.current?.destroy()
  }, [code])

  return <div ref={editorRef} />
}

/* ── RAG Context Bar ─────────────────────────────────────────────────── */
function RAGBar() {
  const [open, setOpen] = useState(false)
  const { rag_context } = useStore()
  if (!rag_context) return null
  return (
    <div className="rag-bar">
      <div className="rag-bar-header" onClick={() => setOpen(!open)}>
        <span className="rag-bar-title">
          ◈ Analysing {rag_context.tables_injected ?? rag_context.selected_tables.length} of {rag_context.total_tables} tables
        </span>
        <span style={{ color: 'var(--cyan)', fontSize: 11 }}>{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="rag-tables">
          {rag_context.selected_tables.map((t) => (
            <span key={t} className="rag-table-badge">{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Rationale Collapsible ───────────────────────────────────────────── */
function RationaleBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  if (!text) return null
  return (
    <div className="rationale-block">
      <div className="rationale-header" onClick={() => setOpen(!open)}>
        <span className="rationale-label">◎ How this query was built</span>
        <span className={`rationale-chevron${open ? ' open' : ''}`}>▾</span>
      </div>
      {open && <div className="rationale-body">{text}</div>}
    </div>
  )
}

/* ── Copy Button ─────────────────────────────────────────────────────── */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className={`btn-copy${copied ? ' copied' : ''}`} onClick={handleCopy}>
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

/* ── Main StreamingPanel ─────────────────────────────────────────────── */
export function StreamingPanel() {
  const {
    query_status, streaming_text, rag_context,
    sql, rationale, explanation, tables_used,
    validation, generation_time_ms, cache_hit,
    query_error, error_type,
  } = useStore()

  if (query_status === 'idle') {
    return (
      <div className="stream-area idle-placeholder">
        <div className="idle-icon">◈</div>
        <div className="idle-text">Ask a question to generate SQL</div>
      </div>
    )
  }

  return (
    <div className="stream-area">
      {/* RAG context bar */}
      {rag_context && <RAGBar />}

      {/* Cache hit badge */}
      {cache_hit && query_status === 'complete' && (
        <div className="cache-badge">⚡ Answered from cache</div>
      )}

      {/* Streaming indicator + token stream */}
      {query_status === 'streaming' && (
        <>
          <div className="stream-indicator">
            <span className="stream-dot" />
            Generating SQL...
          </div>
          {streaming_text && (
            <div className="stream-tokens">{streaming_text}</div>
          )}
        </>
      )}

      {/* Error */}
      {query_status === 'error' && (
        <div className="error-block">
          <div className="error-title">
            {error_type === 'schema_mismatch' ? 'Schema Mismatch' : 'Error'}
          </div>
          <div className="error-msg">{query_error}</div>
          {error_type === 'schema_mismatch' && validation?.invalid_references && (
            <div className="error-refs">
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
                The AI referenced columns that don't exist:
              </div>
              {validation.invalid_references.map((r) => (
                <div key={r} className="error-ref">• {r}</div>
              ))}
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 6 }}>
                Try rephrasing your question.
              </div>
            </div>
          )}
        </div>
      )}

      {/* Complete result */}
      {query_status === 'complete' && sql && (
        <>
          {/* Rationale */}
          {rationale && <RationaleBlock text={rationale} />}

          {/* SQL Block */}
          <div className="sql-block">
            <div className="sql-header">
              <span className="sql-lang">PostgreSQL</span>
              <CopyButton text={sql} />
            </div>
            <SQLViewer code={sql} />
          </div>

          {/* Explanation */}
          {explanation && (
            <div className="explanation-block">{explanation}</div>
          )}

          {/* Tables used */}
          {tables_used.length > 0 && (
            <div className="tables-used">
              {tables_used.map((t) => (
                <span key={t} className="table-badge">{t}</span>
              ))}
            </div>
          )}

          {/* Validation */}
          {validation && (
            <div className={`validation-row ${validation.passed ? 'passed' : 'failed'}`}>
              <span>{validation.passed ? '✓' : '✕'}</span>
              <span>
                {validation.passed
                  ? 'Passed 3 validation checks'
                  : `Validation failed (pass ${validation.failed_pass})`}
              </span>
            </div>
          )}

          {/* Meta */}
          <div className="meta-row">
            {generation_time_ms !== null && generation_time_ms > 0 && (
              <span>Generated in {generation_time_ms}ms</span>
            )}
            {cache_hit && <span>⚡ cache hit</span>}
          </div>
        </>
      )}
    </div>
  )
}