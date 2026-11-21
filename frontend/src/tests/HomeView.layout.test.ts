import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api', () => ({
  API_BASE: '',
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}))

import HomeView from '@/views/HomeView.vue'
import UrlDownloadFeed from '@/components/UrlDownloadFeed.vue'
import SearchVideosFeed from '@/components/SearchVideosFeed.vue'
import { apiGet } from '@/api'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.mocked(apiGet).mockReset()
  vi.mocked(apiGet).mockResolvedValue({} as any)
})

async function mountHome() {
  const wrapper = mount(HomeView, { shallow: true, global: { stubs: { KeepAlive: false } } })
  await flushPromises()
  return wrapper
}

describe('HomeView（Lite 版面）', () => {
  it('來源只有「貼網址」「搜尋」兩個分頁，預設貼網址', async () => {
    const wrapper = await mountHome()
    expect(wrapper.find('[data-testid="source-tab-url"]').classes()).toContain('active')
    expect(wrapper.find('[data-testid="source-tab-search"]').exists()).toBe(true)
    expect(wrapper.findComponent(UrlDownloadFeed).exists()).toBe(true)

    await wrapper.find('[data-testid="source-tab-search"]').trigger('click')
    expect(wrapper.findComponent(SearchVideosFeed).exists()).toBe(true)
    expect(wrapper.findComponent(UrlDownloadFeed).exists()).toBe(false)
  })

  it('工作區只有「下載」「音量正規化」兩個分頁', async () => {
    const wrapper = await mountHome()
    const tabs = wrapper.findAll('.right-pane-progress .tab').map((b) => b.text())
    expect(tabs).toEqual(['下載', '音量正規化'])
  })

  it('沒有登入、帳號、配額、訂閱左欄', async () => {
    const wrapper = await mountHome()
    expect(wrapper.find('.redownload-toggle').exists()).toBe(true)  // 錨點：header 有渲染
    expect(wrapper.find('.left-pane').exists()).toBe(false)
    expect(wrapper.find('.quota-badge').exists()).toBe(false)
    expect(wrapper.find('.account-switcher').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('登出')
  })

  it('掛載時不呼叫任何需要授權的 API', async () => {
    await mountHome()
    const paths = vi.mocked(apiGet).mock.calls.map((c) => String(c[0]))
    expect(paths.filter((p) => /^\/(auth|subscriptions|quota|drive)/.test(p))).toEqual([])
  })
})
