import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SearchVideosFeed from '@/components/SearchVideosFeed.vue'
import { useDownloadStore } from '@/stores/download'
import { usePlayerStore } from '@/stores/player'
import { snap, extractCss } from './snap'

vi.mock('@/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}))

const CSS = extractCss('src/components/SearchVideosFeed.vue')

function makeVideo(id: string) {
  return {
    video_id: id,
    title: `搜尋結果 ${id}`,
    url: `https://www.youtube.com/watch?v=${id}`,
    thumbnail: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`,
    published: new Date().toISOString(),
    duration_seconds: 400,
    channel_id: 'UC_search',
    channel_title: '搜尋頻道',
  }
}

describe('SearchVideosFeed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始狀態顯示提示', async () => {
    const wrapper = mount(SearchVideosFeed)
    snap('SearchVideosFeed|1. 初始提示搜尋', wrapper.html(), CSS)
    expect(wrapper.text()).toContain('請輸入關鍵字開始搜尋')
  })

  it('搜尋載入中', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockImplementation(() => new Promise(() => {}))

    const wrapper = mount(SearchVideosFeed)
    await wrapper.find('input').setValue('lofi')
    await wrapper.find('button').trigger('click')

    snap('SearchVideosFeed|2. 搜尋載入中', wrapper.html(), CSS)
    expect(wrapper.text()).toContain('載入中')
  })

  it('搜尋成功顯示結果', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValueOnce({
      videos: [makeVideo('s1'), makeVideo('s2')]
    })

    const wrapper = mount(SearchVideosFeed)
    await wrapper.find('input').setValue('lofi')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    snap('SearchVideosFeed|3. 成功顯示搜尋結果', wrapper.html(), CSS)
    const items = wrapper.findAll('.video-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('搜尋結果 s1')
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith('/search-channels?q=lofi')
  })

  it('點縮圖呼叫 player.open(video_id)', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValueOnce({ videos: [makeVideo('s1')] })

    const wrapper = mount(SearchVideosFeed)
    await wrapper.find('input').setValue('lofi')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const player = usePlayerStore()
    await wrapper.find('.thumb').trigger('click')
    expect(player.currentVideoId).toBe('s1')
    expect(player.isOpen).toBe(true)
  })

  it('Lite 沒有頻道搜尋、觀察名單、訂閱按鈕', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValueOnce({ videos: [makeVideo('s1')] })

    const wrapper = mount(SearchVideosFeed)
    await wrapper.find('input').setValue('lofi')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.video-item')).toHaveLength(1)  // 錨點：結果有渲染
    expect(wrapper.find('.scope-row').exists()).toBe(false)
    expect(wrapper.find('.watch-btn').exists()).toBe(false)
    expect(wrapper.find('.subscribe-btn').exists()).toBe(false)
    expect(vi.mocked(apiGet).mock.calls.map((c) => c[0])).toEqual(['/search-videos?q=lofi'])
  })

  it('查無結果時顯示提示', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValueOnce({ videos: [] })

    const wrapper = mount(SearchVideosFeed)
    await wrapper.find('input').setValue('no-match-keyword')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    snap('SearchVideosFeed|4. 查無符合條件的影片', wrapper.html(), CSS)
    expect(wrapper.text()).toContain('查無符合條件的影片')
  })
})

// ── 全域「允許再次下載」覆寫開關 ────────────────────────────────────────────────
describe('SearchVideosFeed 全域「允許再次下載」', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    localStorage.clear()
  })

  async function mountWithDownloaded() {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValueOnce({ videos: [makeVideo('s1'), makeVideo('s2')] })
    const download = useDownloadStore()
    download.markAsDownloaded('s1')

    const wrapper = mount(SearchVideosFeed)
    await wrapper.find('input').setValue('lofi')
    await wrapper.find('button').trigger('click')
    await flushPromises()
    return { wrapper, download }
  }

  it('開關 OFF：已下載影片 disabled 且呈現已勾選', async () => {
    const { wrapper } = await mountWithDownloaded()

    const cb = wrapper.findAll('.video-checkbox')[0].element as HTMLInputElement
    expect(cb.disabled).toBe(true)
    expect(cb.checked).toBe(true)
    expect(wrapper.find('.dl-badge').exists()).toBe(true)
  })

  it('開關 ON：已下載影片可操作且呈現未勾選，徽章仍在', async () => {
    const { wrapper, download } = await mountWithDownloaded()
    download.allowRedownload = true
    await flushPromises()

    const cb = wrapper.findAll('.video-checkbox')[0].element as HTMLInputElement
    expect(cb.disabled).toBe(false)
    expect(cb.checked).toBe(false)
    expect(wrapper.find('.dl-badge').exists()).toBe(true)
  })

  it('開關 ON：點擊已下載影片加入 selected 並轉為已勾選', async () => {
    const { wrapper, download } = await mountWithDownloaded()
    download.allowRedownload = true
    await flushPromises()

    await wrapper.findAll('.video-checkbox')[0].trigger('change')

    expect(download.selected.map((v) => v.video_id)).toEqual(['s1'])
    expect((wrapper.findAll('.video-checkbox')[0].element as HTMLInputElement).checked).toBe(true)
  })

  it('關閉開關後 selected 內容不變', async () => {
    const { wrapper, download } = await mountWithDownloaded()
    download.allowRedownload = true
    await flushPromises()
    await wrapper.findAll('.video-checkbox')[0].trigger('change')
    expect(download.selected).toHaveLength(1)

    download.allowRedownload = false
    await flushPromises()

    expect(download.selected).toHaveLength(1)
    expect((wrapper.findAll('.video-checkbox')[0].element as HTMLInputElement).disabled).toBe(true)
  })
})
