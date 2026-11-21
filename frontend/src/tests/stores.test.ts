import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
import { useDownloadStore } from '@/stores/download'

vi.mock('@/api', () => ({
  API_BASE: '/api',
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}))

const FAKE_VIDEO = {
  video_id: 'v1',
  title: '測試影片',
  url: 'https://www.youtube.com/watch?v=v1',
  thumbnail: 'https://i.ytimg.com/vi/v1/mqdefault.jpg',
  published: '2024-01-15T10:00:00+00:00',
}

describe('downloadStore resilient resume persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('hydrates selected videos from localStorage', () => {
    localStorage.setItem('yt_mp3_selected', JSON.stringify([FAKE_VIDEO]))
    setActivePinia(createPinia())

    const store = useDownloadStore()

    expect(store.selected).toEqual([FAKE_VIDEO])
  })

  it('ignores invalid selected localStorage JSON', () => {
    localStorage.setItem('yt_mp3_selected', '{not json')
    setActivePinia(createPinia())

    const store = useDownloadStore()

    expect(store.selected).toEqual([])
  })

  it('persists selected videos and removes only completed downloads', async () => {
    const store = useDownloadStore()
    const failedVideo = { ...FAKE_VIDEO, video_id: 'v2', title: 'Failed video' }

    store.toggle(FAKE_VIDEO)
    store.toggle(failedVideo)
    await nextTick()
    expect(JSON.parse(localStorage.getItem('yt_mp3_selected') || '[]')).toHaveLength(2)

    store.markAsDownloaded('v1')
    await nextTick()

    expect(store.selected.map((v) => v.video_id)).toEqual(['v2'])
    expect(JSON.parse(localStorage.getItem('yt_mp3_selected') || '[]')).toEqual([failedVideo])
  })

  it('clearAll clears selected videos, persisted selection, and progress', async () => {
    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    store.progress = {
      v1: { title: 'Done video', percent: 100, status: 'done' },
      v2: { title: 'Failed video', percent: 0, status: 'error', error: 'boom' },
    }
    await nextTick()

    store.clearAll()
    await nextTick()

    expect(store.selected).toEqual([])
    expect(store.progress).toEqual({})
    expect(localStorage.getItem('yt_mp3_selected')).toBe('[]')
  })
})

describe('downloadStore target folders', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('autoPipeline defaults off and persists changes', () => {
    const store = useDownloadStore()
    expect(store.autoPipeline).toBe(false)

    store.autoPipeline = true

    expect(localStorage.getItem('yt_mp3_auto_pipeline')).toBe('true')
  })

  it('startDownload includes target_dir when provided', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't', directory: 'C:/out/20260601_sports' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload('mp3', 192, { targetDir: '20260601_sports' })

    expect(apiPost).toHaveBeenCalledWith('/download', expect.objectContaining({
      target_dir: '20260601_sports',
    }))
    expect(store.lastWorkDirName).toBe('20260601_sports')
    expect(store.lastDownloadDir).toBe('C:/out/20260601_sports')
    expect(store.lastFormat).toBe('mp3')
  })

  it('startDownload records mp4 as last format for pipeline routing', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't', directory: 'C:/out/videos' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload('mp4', 720)

    expect(store.lastFormat).toBe('mp4')
    expect(store.lastDownloadDir).toBe('C:/out/videos')
  })
})

// ── downloadStore ──────────────────────────────────────────────────────────────

/** 建立可作為 new EventSource() 使用的 constructor mock */
function makeEventSourceMock() {
  const instance = {
    onmessage: null as ((e: MessageEvent) => void) | null,
    onerror: null as ((e: Event) => void) | null,
    close: vi.fn(),
  }
  const Ctor = vi.fn(function (this: typeof instance) {
    Object.assign(this, instance)
    // 讓外部能存取 instance 設定的 handler
    Ctor.lastInstance = this
  }) as any
  Ctor.lastInstance = null
  return { Ctor, instance }
}

describe('downloadStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始狀態：selected 為空、downloading 為 false', () => {
    const store = useDownloadStore()
    expect(store.selected).toHaveLength(0)
    expect(store.downloading).toBe(false)
  })

  it('toggle：第一次加入影片', () => {
    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    expect(store.selected).toHaveLength(1)
    expect(store.selected[0].video_id).toBe('v1')
  })

  it('toggle：第二次移除影片', () => {
    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    store.toggle(FAKE_VIDEO)
    expect(store.selected).toHaveLength(0)
  })

  it('isSelected：已選取回傳 true，未選取回傳 false', () => {
    const store = useDownloadStore()
    expect(store.isSelected('v1')).toBe(false)
    store.toggle(FAKE_VIDEO)
    expect(store.isSelected('v1')).toBe(true)
  })

  it('clearAll：清空所有選取', () => {
    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    store.toggle({ ...FAKE_VIDEO, video_id: 'v2', title: 'Video 2' })
    expect(store.selected).toHaveLength(2)

    store.clearAll()
    expect(store.selected).toHaveLength(0)
  })

  it('startDownload：無選取時不呼叫 API', async () => {
    const { apiPost } = await import('@/api')
    const store = useDownloadStore()
    await store.startDownload()
    expect(apiPost).not.toHaveBeenCalled()
  })

  it('startDownload：呼叫 POST /download 並取得 task_id', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 'task-xyz' })

    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload()

    expect(apiPost).toHaveBeenCalledWith('/download', { videos: [FAKE_VIDEO], format: 'mp3', quality: 192 })
    expect(store.taskId).toBe('task-xyz')
    expect(store.downloading).toBe(true)
  })

  it('startDownload：未傳參數時預設送出 mp3 / 192', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload()

    expect(apiPost).toHaveBeenCalledWith('/download', expect.objectContaining({
      format: 'mp3',
      quality: 192,
    }))
  })

  it('startDownload：自訂 format/quality 帶入 payload', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload('mp4', 1080)

    expect(apiPost).toHaveBeenCalledWith('/download', expect.objectContaining({
      format: 'mp4',
      quality: 1080,
    }))
  })

  it('startDownload：未帶 opts 時 payload 不含 seq 欄位', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload()

    const payload = vi.mocked(apiPost).mock.calls[0][1] as Record<string, unknown>
    expect(payload).not.toHaveProperty('seq_enabled')
    expect(payload).not.toHaveProperty('start_seq')
  })

  it('startDownload：seqEnabled=false → payload 含 seq_enabled:false 且無 start_seq', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload('mp3', 192, { seqEnabled: false, startSeq: '05' })

    const payload = vi.mocked(apiPost).mock.calls[0][1] as Record<string, unknown>
    expect(payload.seq_enabled).toBe(false)
    expect(payload).not.toHaveProperty('start_seq')
  })

  it('startDownload：seqEnabled=true + startSeq 帶入兩個欄位', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload('mp3', 192, { seqEnabled: true, startSeq: '05' })

    expect(apiPost).toHaveBeenCalledWith('/download', expect.objectContaining({
      seq_enabled: true,
      start_seq: '05',
    }))
  })

  it('startDownload：seqEnabled=true 但 startSeq 為空字串時不帶 start_seq', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 't' })
    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload('mp3', 192, { seqEnabled: true, startSeq: '' })

    const payload = vi.mocked(apiPost).mock.calls[0][1] as Record<string, unknown>
    expect(payload.seq_enabled).toBe(true)
    expect(payload).not.toHaveProperty('start_seq')
  })

  it('startDownload：SSE done 事件結束下載狀態', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 'task-xyz' })

    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload()

    expect(store.downloading).toBe(true)

    // 取得 store 內的 EventSource 實例並觸發 onmessage
    const esInstance = Ctor.mock.instances[0]
    esInstance.onmessage({ data: JSON.stringify({ status: 'done', items: {} }) })

    expect(store.downloading).toBe(false)
    expect(esInstance.close).toHaveBeenCalled()
  })

  it('startDownload：SSE 更新 progress items', async () => {
    const { apiPost } = await import('@/api')
    vi.mocked(apiPost).mockResolvedValue({ task_id: 'task-xyz' })

    const { Ctor } = makeEventSourceMock()
    vi.stubGlobal('EventSource', Ctor)

    const store = useDownloadStore()
    store.toggle(FAKE_VIDEO)
    await store.startDownload()

    const esInstance = Ctor.mock.instances[0]
    esInstance.onmessage({
      data: JSON.stringify({
        status: 'running',
        items: { v1: { title: '測試影片', percent: 60, status: 'downloading' } },
      }),
    })

    expect(store.progress['v1'].percent).toBe(60)
    expect(store.progress['v1'].status).toBe('downloading')
  })
})

// ── 全域「允許再次下載」覆寫開關 ────────────────────────────────────────────────
describe('downloadStore allowRedownload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('預設為 false', () => {
    const store = useDownloadStore()
    expect(store.allowRedownload).toBe(false)
  })

  it('切換後不寫入 localStorage（刻意不持久化）', async () => {
    const store = useDownloadStore()
    const before = { ...localStorage }

    store.allowRedownload = true
    await nextTick()

    expect(store.allowRedownload).toBe(true)
    expect({ ...localStorage }).toEqual(before)
  })

  it('重建 store 後回到 false（重新整理即恢復保護）', () => {
    const store = useDownloadStore()
    store.allowRedownload = true

    setActivePinia(createPinia())
    const fresh = useDownloadStore()

    expect(fresh.allowRedownload).toBe(false)
  })

  it('由 true 切回 false 時不移除 selected 中的已下載影片', async () => {
    const store = useDownloadStore()
    store.markAsDownloaded('v1')

    store.allowRedownload = true
    store.toggle(FAKE_VIDEO)
    expect(store.selected).toHaveLength(1)

    store.allowRedownload = false
    await nextTick()

    expect(store.selected).toHaveLength(1)
    expect(store.selected[0].video_id).toBe('v1')
  })
})
