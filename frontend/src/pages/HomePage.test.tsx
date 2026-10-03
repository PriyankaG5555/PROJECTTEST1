import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import HomePage from './HomePage.tsx'

afterEach(() => vi.unstubAllGlobals())

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HomePage />
    </QueryClientProvider>,
  )
}

test('shows the brand and API status ok when the API responds', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ status: 'ok' }))))
  renderPage()

  expect(screen.getByAltText('GhumakkadYatri')).toBeInTheDocument()
  expect(await screen.findByText('ok')).toBeInTheDocument()
})

test('shows "not reachable" when the API is down', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))
  renderPage()

  expect(await screen.findByText('not reachable')).toBeInTheDocument()
})
