import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../api/client'
import { keys, useMe, useTrips } from '../api/queries'
import { Field, FormError, Modal, btn, card, inputCls } from '../components/ui'

export default function AccountPage() {
  const me = useMe()
  const trips = useTrips()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const count = trips.data?.length ?? 0

  async function remove(e: FormEvent) {
    e.preventDefault()
    if (!password) return setError('Enter your password to confirm.')
    setBusy(true)
    try {
      await api('/auth/me', 'DELETE', { password })
      qc.clear()
      qc.setQueryData(keys.me, null)
      navigate('/signup', { state: { notice: 'Your account has been deleted.' } })
    } catch (err) {
      setError(err instanceof Error ? `${err.message} Nothing was deleted.` : 'Something went wrong.')
      setBusy(false)
    }
  }

  return (
    <>
      <h1 className="text-2xl font-bold">My account</h1>
      <section className={`${card} grid max-w-xl gap-2 p-5`}>
        <h2 className="font-semibold">Profile</h2>
        <p>
          Username: <b>{me.data?.username}</b>
        </p>
        <p className="text-sm text-slate-600">{count} trips saved to this account.</p>
      </section>
      <section className="grid max-w-xl gap-3 rounded-2xl border border-red-300 bg-red-50 p-5">
        <h2 className="font-semibold text-red-800">Delete my account</h2>
        <p>
          This permanently deletes your account and all {count} trips, drafts and activities. It can't be
          undone.
        </p>
        <div>
          <button className={btn.danger} onClick={() => setOpen(true)}>
            Delete my account
          </button>
        </div>
      </section>
      {open && (
        <Modal title="Delete your account?" onClose={() => setOpen(false)}>
          <form className="grid gap-4" onSubmit={remove} noValidate>
            <p>All your trips, drafts and activities will be permanently deleted. Enter your password to confirm.</p>
            <Field id="delete-password" label="Password">
              <input id="delete-password" type="password" className={inputCls} autoFocus
                autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <FormError message={error} />
            <div className="flex justify-end gap-2">
              <button type="button" className={btn.ghost} onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button className={btn.danger} disabled={busy}>
                Delete account
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
