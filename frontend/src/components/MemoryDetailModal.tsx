import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, Copy, Check, Loader2, FileText } from 'lucide-react'
import { api } from '../lib/api'
import { titleCase, fmtDateTime, tidyNumbers } from '../lib/format'
import { Pill, ErrorState } from './ui'

/** Opens the full parent document for a memory id. Search only ever returns a
 *  matching chunk, so the detail view always re-fetches the whole document. */
export function MemoryDetailModal({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const doc = useQuery({ queryKey: ['document', documentId], queryFn: () => api.memoryDocument(documentId) })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const copy = () => {
    navigator.clipboard.writeText(documentId)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const meta = doc.data?.metadata ?? {}
  const entries = Object.entries(meta).filter(([k]) => k !== 'type')

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8"
      style={{ background: 'color-mix(in srgb, var(--bg) 72%, transparent)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="am-card w-full max-w-2xl my-auto"
        style={{ boxShadow: '0 24px 70px -20px rgba(0,0,0,0.6), 0 0 0 1px var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start gap-3 border-b border-border p-5">
          <span className="grid h-9 w-9 place-items-center rounded-lg shrink-0" style={{ background: 'color-mix(in srgb, var(--accent) 15%, transparent)' }}>
            <FileText size={17} className="text-accent" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {doc.data && <Pill tone="accent">{titleCase(doc.data.type)}</Pill>}
              {doc.data && (
                <span className={`flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider ${doc.data.status === 'done' ? 'text-gain' : 'text-warn'}`}>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: doc.data.status === 'done' ? 'var(--am-gain)' : 'var(--am-warn)' }} />
                  {doc.data.status}
                </span>
              )}
            </div>
            <button onClick={copy} className="mt-1.5 flex items-center gap-1.5 font-mono text-xs text-faint hover:text-accent transition-colors" title="Copy document id">
              {documentId} {copied ? <Check size={12} className="text-gain" /> : <Copy size={12} />}
            </button>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:text-text hover:bg-surface-2 transition-colors shrink-0" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {/* body */}
        <div className="p-5">
          {doc.isLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted">
              <Loader2 size={16} className="animate-spin" /> Loading memory…
            </div>
          ) : doc.isError ? (
            <ErrorState error={doc.error} />
          ) : (
            <>
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-faint mb-2">Memory content</div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text rounded-lg bg-surface-2 p-4">
                {tidyNumbers(doc.data?.content || doc.data?.title || 'This memory has no stored text.')}
              </p>

              {entries.length > 0 && (
                <>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-faint mt-5 mb-2">Metadata</div>
                  <div className="grid sm:grid-cols-2 gap-x-6">
                    {entries.map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3 border-b border-border/60 py-1.5 text-xs">
                        <span className="text-faint">{titleCase(k)}</span>
                        <span className="text-text font-medium text-right break-all">{tidyNumbers(String(v))}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {doc.data?.created_at && (
                <div className="mt-4 text-xs text-faint">Stored {fmtDateTime(doc.data.created_at)}</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
