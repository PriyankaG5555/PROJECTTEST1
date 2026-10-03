import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, api } from './client'

afterEach(() => vi.unstubAllGlobals())

const reply = (status: number, body?: unknown) =>
  vi.fn(async () =>
    body === undefined
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }),
  )

test('returns JSON and sends JSON with cookies on mutations', async () => {
  const fetchMock = reply(201, { trip: { id: 't1' } })
  vi.stubGlobal('fetch', fetchMock)

  const data = await api<{ trip: { id: string } }>('/trips', 'POST', { destination: 'Goa' })

  expect(data.trip.id).toBe('t1')
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/api/v1/trips')
  expect(init.credentials).toBe('include')
  expect(init.body).toBe('{"destination":"Goa"}')
})

test('turns contract errors into ApiError with field messages', async () => {
  const error = { code: 'VALIDATION_ERROR', message: 'Bad', details: { fields: { endDate: 'Too late' } } }
  vi.stubGlobal('fetch', reply(400, { error }))

  const caught = await api('/trips', 'POST', {}).catch((e: unknown) => e)

  expect(caught).toBeInstanceOf(ApiError)
  expect((caught as ApiError).code).toBe('VALIDATION_ERROR')
  expect((caught as ApiError).fields).toEqual({ endDate: 'Too late' })
})

test('204 resolves to undefined', async () => {
  vi.stubGlobal('fetch', reply(204))
  expect(await api('/auth/logout', 'POST')).toBeUndefined()
})

test('network failure becomes NETWORK_ERROR', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
  const caught = (await api('/trips').catch((e: unknown) => e)) as ApiError
  expect(caught.code).toBe('NETWORK_ERROR')
})
