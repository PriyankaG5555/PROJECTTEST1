import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'
import { ApiError, api } from '../api/client'
import { keys } from '../api/queries'
import { Field, FormError, btn, inputCls } from '../components/ui'
import type { User } from '../types'

type Mode = 'login' | 'signup'

function validate(mode: Mode, username: string, password: string, confirm: string) {
  const e: Record<string, string> = {}
  if (mode === 'signup') {
    if (!/^[A-Za-z0-9_]{3,30}$/.test(username.trim()))
      e.username = 'Username must be 3–30 letters, numbers or underscores.'
    if (password.length < 8 || password.length > 128) e.password = 'Password must be 8–128 characters.'
    if (password !== confirm) e.confirm = "Passwords don't match."
  } else {
    if (!username.trim()) e.username = 'Enter your username.'
    if (!password) e.password = 'Enter your password.'
  }
  return e
}

export default function AuthPage({ mode }: { mode: Mode }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const notice = (useLocation().state as { notice?: string } | null)?.notice
  const isSignup = mode === 'signup'

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found = validate(mode, username, password, confirm)
    setErrors(found)
    setFormError(undefined)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      const { user } = await api<{ user: User }>(`/auth/${mode}`, 'POST', { username: username.trim(), password })
      qc.setQueryData(keys.me, user)
      const next = params.get('next')
      navigate(next?.startsWith('/') ? next : '/trips', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields)
      else setFormError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="px-4 py-10">
      <section className="mx-auto grid w-full max-w-md gap-5 rounded-3xl border border-brand-200 bg-white px-6 py-8 shadow-sm">
        <div className="grid justify-items-center gap-1 text-center">
          <img src="/favicon.svg" alt="" className="size-20" />
          <h1 className="text-2xl font-bold">{isSignup ? 'Create your account' : 'Welcome back'}</h1>
          <span className="text-xs font-semibold tracking-[0.18em] text-slate-600">PLAN · PACK · GO</span>
        </div>
        {notice && <p className="rounded-xl bg-brand-50 px-3 py-2 text-sm">{notice}</p>}
        <form className="grid gap-4" onSubmit={submit} noValidate>
          <Field id="username" label="Username" error={errors.username}
            hint={isSignup ? '3–30 characters: letters, numbers, underscore.' : undefined}>
            <input id="username" className={inputCls} autoComplete="username" value={username}
              onChange={(e) => setUsername(e.target.value)} autoFocus />
          </Field>
          <Field id="password" label="Password" error={errors.password}
            hint={isSignup ? 'At least 8 characters.' : undefined}>
            <input id="password" type="password" className={inputCls} value={password}
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {isSignup && (
            <Field id="confirm" label="Confirm password" error={errors.confirm}>
              <input id="confirm" type="password" className={inputCls} autoComplete="new-password"
                value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
          )}
          <FormError message={formError} />
          <button className={btn.primary} disabled={busy}>
            {busy ? 'Please wait…' : isSignup ? 'Create account' : 'Log in'}
          </button>
        </form>
        <p className="text-center text-sm text-slate-600">
          {isSignup ? 'Already have an account? ' : 'New here? '}
          <Link className="font-semibold text-brand-700" to={isSignup ? '/login' : '/signup'}>
            {isSignup ? 'Log in' : 'Create an account'}
          </Link>
        </p>
      </section>
    </main>
  )
}
