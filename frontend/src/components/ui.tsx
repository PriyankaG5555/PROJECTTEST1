// Shared building blocks (frontend-spec.md §4, §8).
import { useEffect, type ReactNode } from 'react'
import type { TripStatus } from '../types'

export const btn = {
  primary:
    'inline-flex items-center justify-center gap-1.5 rounded-xl bg-brand-700 px-4 py-2 font-display text-sm font-semibold text-white hover:bg-brand-900 disabled:opacity-50',
  ghost:
    'inline-flex items-center justify-center gap-1.5 rounded-xl border border-brand-400 bg-white px-4 py-2 font-display text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50',
  danger:
    'inline-flex items-center justify-center gap-1.5 rounded-xl bg-red-700 px-4 py-2 font-display text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-50',
  text: 'rounded-lg px-2 py-1 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-40',
}
export const inputCls =
  'w-full min-w-0 rounded-xl border border-brand-400 bg-white px-3 py-2 text-brand-900 focus:outline-2 focus:outline-brand-400'
export const card = 'rounded-2xl border border-brand-200 bg-white'

export function Field(props: { id: string; label: ReactNode; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-1">
      <label htmlFor={props.id} className="text-sm font-medium">
        {props.label}
      </label>
      {props.children}
      {props.hint && !props.error && <span className="text-xs text-slate-600">{props.hint}</span>}
      {props.error && (
        <span className="text-sm font-medium text-red-700" role="alert">
          {props.error}
        </span>
      )}
    </div>
  )
}

export function FormError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <p className="rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-700" role="alert">
      {message}
    </p>
  )
}

export function StatusBadge({ status }: { status: TripStatus }) {
  const cls = status === 'finalized' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {status === 'finalized' ? 'Finalized' : 'Draft'}
    </span>
  )
}


export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-slate-600" role="status">
      <span className="size-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-700" />
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className={`${card} grid justify-items-start gap-3 p-6`} role="alert">
      <p className="font-medium text-red-700">{message}</p>
      {onRetry && (
        <button className={btn.ghost} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="grid justify-items-center gap-3 rounded-2xl border-2 border-dashed border-brand-400 px-4 py-10 text-center text-slate-600">
      <h2 className="text-lg font-semibold text-brand-900">{title}</h2>
      {children}
    </div>
  )
}

export function Modal(props: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const { onClose } = props
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-brand-900/40 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={props.title}
        className={`grid max-h-[calc(100%-2rem)] w-full gap-4 overflow-auto rounded-2xl bg-white p-6 shadow-xl ${props.wide ? 'max-w-2xl' : 'max-w-md'}`}
      >
        <h2 className="text-lg font-semibold">{props.title}</h2>
        {props.children}
      </div>
    </div>
  )
}

export function ConfirmDialog(props: {
  title: string
  message: ReactNode
  confirmLabel: string
  danger?: boolean
  busy?: boolean
  error?: string
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Modal title={props.title} onClose={props.onClose}>
      <div className="text-slate-700">{props.message}</div>
      <FormError message={props.error} />
      <div className="flex flex-wrap justify-end gap-2">
        <button className={btn.ghost} onClick={props.onClose}>
          Cancel
        </button>
        <button
          autoFocus
          className={props.danger ? btn.danger : btn.primary}
          disabled={props.busy}
          onClick={props.onConfirm}
        >
          {props.confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
