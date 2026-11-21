import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useDownloadStore } from '@/stores/download'

vi.mock('@/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}))

import HomeView from '@/views/HomeView.vue'
import { apiGet } from '@/api'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.mocked(apiGet).mockImplementation((path: string) => {
    return Promise.resolve({} as any)
  })
})

async function mountHome() {
  const wrapper = mount(HomeView, { shallow: true })
  await flushPromises()
  return wrapper
}

describe('HomeView 全域「允許再次下載」開關', () => {
  it('header 渲染出開關且預設未勾選', async () => {
    const wrapper = await mountHome()

    const toggle = wrapper.find('.redownload-toggle input[type="checkbox"]')
    expect(toggle.exists()).toBe(true)
    expect((toggle.element as HTMLInputElement).checked).toBe(false)
  })

  it('點擊開關後 store 的 allowRedownload 變為 true', async () => {
    const wrapper = await mountHome()
    const download = useDownloadStore()
    expect(download.allowRedownload).toBe(false)

    await wrapper.find('.redownload-toggle input[type="checkbox"]').setValue(true)

    expect(download.allowRedownload).toBe(true)
  })

  it('開關為 ON 時套用強調樣式，OFF 時不套用', async () => {
    const wrapper = await mountHome()
    const download = useDownloadStore()

    expect(wrapper.find('.redownload-toggle').classes()).not.toContain('on')

    download.allowRedownload = true
    await flushPromises()

    expect(wrapper.find('.redownload-toggle').classes()).toContain('on')
  })

  it('切換開關不寫入 localStorage', async () => {
    const wrapper = await mountHome()
    const before = { ...localStorage }

    await wrapper.find('.redownload-toggle input[type="checkbox"]').setValue(true)

    expect({ ...localStorage }).toEqual(before)
  })
})
