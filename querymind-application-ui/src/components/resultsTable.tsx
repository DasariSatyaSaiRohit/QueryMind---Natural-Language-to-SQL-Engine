import { useMemo } from 'react'
import { useReactTable, getCoreRowModel, flexRender, ColumnDef } from '@tanstack/react-table'
import { useStore } from '../store/usestore'
import { useQueryResults } from '../hooks/usequeryresults'

function isNumber(v: unknown): boolean {
  return typeof v === 'number' || (typeof v === 'string' && !isNaN(Number(v)) && v.trim() !== '')
}
function isDate(v: unknown): boolean {
  if (typeof v !== 'string') return false
  return /^\d{4}-\d{2}-\d{2}(T|\s)/.test(v)
}
function formatDate(v: string): string {
  try {
    return new Date(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch { return v }
}

function CellRenderer({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="cell-null">null</span>
  if (typeof value === 'boolean') {
    return <span className={value ? 'cell-bool-true' : 'cell-bool-false'}>{value ? 'true' : 'false'}</span>
  }
  if (isDate(String(value))) return <span className="cell-date">{formatDate(String(value))}</span>
  if (isNumber(value)) return <span className="cell-number">{String(value)}</span>
  return <span>{String(value)}</span>
}

function exportCSV(columns: { name: string }[], rows: unknown[][]): void {
  const header = columns.map((c) => `"${c.name}"`).join(',')
  const body = rows.map((row) =>
    row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')
  ).join('\n')
  const blob = new Blob([header + '\n' + body], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `querymind-export-${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function ResultsTable() {
  const { results } = useStore()
  const { fetchResults, loading } = useQueryResults()

  const columns = useMemo<ColumnDef<unknown[]>[]>(() => {
    if (!results?.columns) return []
    return results.columns.map((col, i) => ({
      id: col.name,
      header: col.name,
      cell: ({ row }) => <CellRenderer value={row.original[i]} />,
    }))
  }, [results?.columns])

  const table = useReactTable({
    data: results?.rows ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
  })

  if (!results) {
    return (
      <div className="results-empty">
        <div className="results-empty-icon">▤</div>
        <div className="results-empty-text">Results will appear here</div>
      </div>
    )
  }

  const { page, total_rows, total_pages, has_next, has_prev } = results.pagination
  const startRow = (page - 1) * results.pagination.page_size + 1
  const endRow = Math.min(page * results.pagination.page_size, total_rows)

  return (
    <div className="results-panel-inner">
      {results.truncated && results.truncation_warning && (
        <div className="truncation-warn">⚠ {results.truncation_warning}</div>
      )}

      <div className="results-header">
        <span className="results-count">
          {loading ? 'Loading...' : `Showing rows ${startRow}–${endRow} of ${total_rows}`}
        </span>
        <button
          className="btn-export"
          onClick={() => exportCSV(results.columns, results.rows)}
          disabled={results.rows.length === 0}
        >
          ↓ Export CSV
        </button>
      </div>

      <div className="table-wrap">
        <table className="results-table">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total_pages > 1 && (
        <div className="pagination">
          <button
            className="btn-page"
            disabled={!has_prev || loading}
            onClick={() => fetchResults(page - 1)}
          >
            ← Prev
          </button>
          <span className="page-info">Page {page} of {total_pages}</span>
          <button
            className="btn-page"
            disabled={!has_next || loading}
            onClick={() => fetchResults(page + 1)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}