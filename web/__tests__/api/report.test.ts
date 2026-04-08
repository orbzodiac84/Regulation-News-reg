import { describe, it, expect, vi, beforeEach } from 'vitest'

const supabaseState: {
  fetchSingle: { data: any; error: any }
  updateResult: { error: any }
} = {
  fetchSingle: { data: null, error: null },
  updateResult: { error: null },
}

const generateContentMock = vi.fn()
const updateMock = vi.fn()

vi.mock('@supabase/supabase-js', () => {
  const createClient = vi.fn(() => {
    const chain: any = {}
    chain.from = vi.fn(() => chain)
    chain.select = vi.fn(() => chain)
    chain.eq = vi.fn(() => chain)
    chain.single = vi.fn(() => Promise.resolve(supabaseState.fetchSingle))
    chain.update = vi.fn((...args: any[]) => {
      updateMock(...args)
      return chain
    })
    // Make chain awaitable for the `update().eq()` path.
    chain.then = (resolve: (v: any) => any) => resolve(supabaseState.updateResult)
    return chain
  })
  return { createClient }
})

vi.mock('@google/generative-ai', () => ({
  GoogleGenerativeAI: vi.fn().mockImplementation(() => ({
    getGenerativeModel: vi.fn().mockReturnValue({
      generateContent: generateContentMock,
    }),
  })),
}))

beforeEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL_V2 = 'https://test.supabase.co'
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-key'
  process.env.GEMINI_API_KEY = 'test-gemini-key'
  generateContentMock.mockReset()
  updateMock.mockReset()
  generateContentMock.mockResolvedValue({
    response: { text: () => 'GENERATED_REPORT_MARKDOWN' },
  })
})

function makeRequest(body: Record<string, unknown>): Request {
  return new Request('http://localhost/api/report', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  })
}

describe('/api/report', () => {
  it('returns cached report when detailed_report exists', async () => {
    supabaseState.fetchSingle = {
      data: { analysis_result: { detailed_report: 'CACHED_REPORT_MARKDOWN' } },
      error: null,
    }
    supabaseState.updateResult = { error: null }

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(
      makeRequest({ articleId: 'a1', title: 't', content: 'c', agency: 'g' }),
    )
    const json = await res.json()

    expect(json.report).toBe('CACHED_REPORT_MARKDOWN')
    expect(generateContentMock).not.toHaveBeenCalled()
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('generates and stores a new report on cache miss', async () => {
    supabaseState.fetchSingle = {
      data: { analysis_result: {} },
      error: null,
    }
    supabaseState.updateResult = { error: null }

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(
      makeRequest({ articleId: 'a2', title: 't', content: 'c', agency: 'g' }),
    )
    const json = await res.json()

    expect(generateContentMock).toHaveBeenCalledTimes(1)
    expect(updateMock).toHaveBeenCalledTimes(1)
    expect(json.report).toBe('GENERATED_REPORT_MARKDOWN')
  })
})
