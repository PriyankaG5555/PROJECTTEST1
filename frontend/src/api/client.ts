// fetch wrapper for /api/v1 (frontend-spec.md §6). Errors follow api-contract-spec.md §2.

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown> | undefined

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }

  /** Field errors from VALIDATION_ERROR, keyed by camelCase field name. */
  get fields(): Record<string, string> {
    return (this.details?.fields as Record<string, string> | undefined) ?? {}
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

export async function api<T>(path: string, method: Method = 'GET', body?: unknown): Promise<T> {
  // Mutating requests always send JSON (part of the CSRF protection in the contract).
  const sendsBody = method !== 'GET'
  let res: Response
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      credentials: 'include',
      headers: sendsBody ? { 'Content-Type': 'application/json' } : undefined,
      body: sendsBody ? JSON.stringify(body ?? {}) : undefined,
    })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', "Can't reach the server. Check your connection and try again.")
  }
  if (res.status === 204) return undefined as T
  const isJson = res.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await res.json() : null
  if (!res.ok) {
    const err = data?.error
    throw new ApiError(
      res.status,
      err?.code ?? 'HTTP_ERROR',
      err?.message ?? `Something went wrong (${res.status}). Please try again.`,
      err?.details,
    )
  }
  return data as T
}

export const exportPdfUrl = (tripId: string) => `/api/v1/trips/${tripId}/export.pdf`
