// 端到端（元件層）：首頁 → 設定頁改輸出資料夾並儲存 → 回首頁，「下載到」要換成新根目錄。
// 單看 SelectedVideos 掛載不夠：要確認經過真的 router 切換時，下載面板確實會重新掛載、重新讀設定。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import SettingsView from '@/views/SettingsView.vue'

vi.mock('@/api', () => ({
  API_BASE: '',
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}))

import { apiGet, apiPut } from '@/api'

describe('改輸出資料夾後回到首頁', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-11-21T12:00:00'))
  })

  it('「下載到」換成新的輸出資料夾', async () => {
    let outputPath = String.raw`C:\Old\YT-MP3`
    vi.mocked(apiGet).mockImplementation(async (url: string) => {
      if (url === '/settings') return { output_path: outputPath, normalize_target_db: 89, download_concurrency: 2 } as any
      if (url.startsWith('/download/next-seq')) return { next_seq: '01', existing: [] } as any
      return {} as any
    })
    vi.mocked(apiPut).mockImplementation(async (_url: string, body: any) => {
      outputPath = body.output_path
      return body
    })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: HomeView },
        { path: '/settings', component: SettingsView },
      ],
    })
    router.push('/')
    await router.isReady()
    // setup.ts 全域把 RouterView 換成空殼；這裡要真的路由切換，所以取原版 RouterView。
    const { RouterView } = await vi.importActual<typeof import('vue-router')>('vue-router')
    const Root = defineComponent({ render: () => h(RouterView) })
    const wrapper = mount(Root, { global: { plugins: [router], stubs: { RouterView: false } } })
    await flushPromises()

    const targetInput = () => wrapper.find<HTMLInputElement>('[data-testid="download-target-dir"]').element
    expect(targetInput().value).toBe(String.raw`C:\Old\YT-MP3\20261121`)  // 錨點：初始值是舊根目錄

    await router.push('/settings')
    await flushPromises()
    await wrapper.findAll('.form input')[0]!.setValue(String.raw`D:\New\Music`)
    await wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()

    await router.push('/')
    await flushPromises()

    expect(targetInput().value).toBe(String.raw`D:\New\Music\20261121`)
  })
})
