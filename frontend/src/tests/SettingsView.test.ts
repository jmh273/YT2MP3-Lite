import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SettingsView from '@/views/SettingsView.vue'
import { snap, extractCss } from './snap'

vi.mock('@/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}))

const CSS = extractCss('src/views/SettingsView.vue')

const FAKE_SETTINGS = {
  output_path: 'C:\\Users\\Test\\Music\\YT-MP3',
  normalize_target_db: 92,
  download_concurrency: 4,
}

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('載入時呼叫 GET /settings 並填入欄位', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)

    const wrapper = mount(SettingsView)
    await flushPromises()
    snap('SettingsView|載入時呼叫 GET /settings 並填入欄位', wrapper.html(), CSS)

    const inputs = wrapper.findAll('input')
    expect((inputs[0].element as HTMLInputElement).value).toBe(FAKE_SETTINGS.output_path)
    expect((inputs[1].element as HTMLInputElement).value).toBe('92')
    expect((inputs[2].element as HTMLInputElement).value).toBe('4')
  })

  it('修改輸出路徑後點擊儲存呼叫 PUT /settings', async () => {
    const { apiGet, apiPut } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    vi.mocked(apiPut).mockResolvedValue({ ...FAKE_SETTINGS, output_path: 'D:\\NewPath' })

    const wrapper = mount(SettingsView)
    await flushPromises()

    const pathInput = wrapper.findAll('input')[0]
    await pathInput.setValue('D:\\NewPath')
    await wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()

    expect(apiPut).toHaveBeenCalledWith('/settings', expect.objectContaining({
      output_path: 'D:\\NewPath',
    }))
  })

  it('儲存成功顯示「已儲存！」', async () => {
    const { apiGet, apiPut } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    vi.mocked(apiPut).mockResolvedValue(FAKE_SETTINGS)

    const wrapper = mount(SettingsView)
    await flushPromises()
    await wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()
    snap('SettingsView|儲存成功顯示「已儲存！」', wrapper.html(), CSS)

    expect(wrapper.find('.ok').text()).toContain('已儲存')
  })

  it('儲存失敗顯示錯誤訊息', async () => {
    const { apiGet, apiPut } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    vi.mocked(apiPut).mockRejectedValue(new Error('伺服器錯誤'))

    const wrapper = mount(SettingsView)
    await flushPromises()
    await wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()
    snap('SettingsView|儲存失敗顯示錯誤訊息', wrapper.html(), CSS)

    expect(wrapper.find('.error').text()).toContain('伺服器錯誤')
  })

  it('normalize_target_db 超出範圍（79）顯示驗證錯誤且儲存按鈕 disabled', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)

    const wrapper = mount(SettingsView)
    await flushPromises()

    const dbInput = wrapper.findAll('input')[1]
    await dbInput.setValue('79')
    await dbInput.trigger('input')
    snap('SettingsView|normalize_target_db 超出範圍（79）顯示驗證錯誤且儲存按鈕 disabled', wrapper.html(), CSS)

    expect(wrapper.find('.field-error').exists()).toBe(true)
    expect(wrapper.find('[data-testid="save-settings"]').attributes('disabled')).toBeDefined()
  })

  it('normalize_target_db 超出範圍（101）顯示驗證錯誤', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)

    const wrapper = mount(SettingsView)
    await flushPromises()

    const dbInput = wrapper.findAll('input')[1]
    await dbInput.setValue('101')
    await dbInput.trigger('input')

    expect(wrapper.find('.field-error').exists()).toBe(true)
  })

  it('normalize_target_db 邊界值 80 和 100 通過驗證', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)

    const wrapper = mount(SettingsView)
    await flushPromises()

    const dbInput = wrapper.findAll('input')[1]

    await dbInput.setValue('80')
    await dbInput.trigger('input')
    expect(wrapper.find('.field-error').exists()).toBe(false)

    await dbInput.setValue('100')
    await dbInput.trigger('input')
    expect(wrapper.find('.field-error').exists()).toBe(false)
  })

  it('儲存中按鈕顯示「儲存中...」並 disabled', async () => {
    const { apiGet, apiPut } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    vi.mocked(apiPut).mockImplementation(() => new Promise(() => {}))

    const wrapper = mount(SettingsView)
    await flushPromises()
    wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()
    snap('SettingsView|儲存中按鈕顯示「儲存中...」並 disabled', wrapper.html(), CSS)

    expect(wrapper.find('[data-testid="save-settings"]').text()).toContain('儲存中')
    expect(wrapper.find('[data-testid="save-settings"]').attributes('disabled')).toBeDefined()
  })

  it('shows and saves download concurrency', async () => {
    const { apiGet, apiPut } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    vi.mocked(apiPut).mockResolvedValue({ ...FAKE_SETTINGS, download_concurrency: 6 })

    const wrapper = mount(SettingsView)
    await flushPromises()

    const concurrencyInput = wrapper.find('[data-testid="download-concurrency"]')
    expect((concurrencyInput.element as HTMLInputElement).value).toBe('4')
    await concurrencyInput.setValue('6')
    await wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()

    expect(apiPut).toHaveBeenCalledWith('/settings', expect.objectContaining({
      download_concurrency: 6,
    }))
  })

})


describe('SettingsView 不含需要 Google 授權的欄位', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('沒有訂閱健檢頁籤，也沒有 Drive / 最新影片相關欄位', async () => {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.find('[data-testid="tab-settings"]').exists()).toBe(true)  // 錨點
    expect(wrapper.find('[data-testid="tab-health"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="drive-root-folder"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="drive-upload-concurrency"]').exists()).toBe(false)
    expect(wrapper.findAll('.form input')).toHaveLength(3)
  })

  it('儲存只送出 Lite 有的三個欄位', async () => {
    const { apiGet, apiPut } = await import('@/api')
    vi.mocked(apiGet).mockResolvedValue(FAKE_SETTINGS)
    vi.mocked(apiPut).mockResolvedValue(FAKE_SETTINGS)
    const wrapper = mount(SettingsView)
    await flushPromises()
    await wrapper.find('[data-testid="save-settings"]').trigger('click')
    await flushPromises()

    expect(vi.mocked(apiPut).mock.lastCall).toEqual(['/settings', {
      output_path: FAKE_SETTINGS.output_path,
      normalize_target_db: 92,
      download_concurrency: 4,
    }])
  })
})

describe('SettingsView 下載元件分頁', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  async function mountPanel(info: any) {
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path === '/settings') return FAKE_SETTINGS as any
      if (path === '/ytdlp/version') return info as any
      return {} as any
    })
    const wrapper = mount(SettingsView)
    await flushPromises()
    await wrapper.find('[data-testid="tab-ytdlp"]').trigger('click')
    return wrapper
  }

  it('顯示生效版本與來源', async () => {
    const wrapper = await mountPanel({
      yt_dlp: '2026.07.04', yt_dlp_ejs: '0.8.0',
      source: 'managed', js_runtime: 'C:\app\deno.exe',
    })
    const text = wrapper.find('[data-testid="ytdlp-versions"]').text()
    expect(text).toContain('2026.07.04')
    expect(text).toContain('0.8.0')
    expect(text).toContain('受管版本')
  })

  it('內建版本時不顯示回退按鈕', async () => {
    const wrapper = await mountPanel({
      yt_dlp: '2026.07.04', yt_dlp_ejs: '0.8.0',
      source: 'bundled', js_runtime: 'C:\app\deno.exe',
    })
    expect(wrapper.find('[data-testid="ytdlp-revert"]').exists()).toBe(false)
  })

  it('缺 JS runtime 時明確標示會失敗', async () => {
    const wrapper = await mountPanel({
      yt_dlp: '2026.07.04', yt_dlp_ejs: null, source: 'bundled', js_runtime: null,
    })
    expect(wrapper.find('[data-testid="ytdlp-versions"]').text()).toContain('下載很可能失敗')
  })

  it('離線查詢時降級顯示訊息而非壞掉', async () => {
    const wrapper = await mountPanel({
      yt_dlp: '2026.07.04', yt_dlp_ejs: '0.8.0', source: 'bundled', js_runtime: 'x',
    })
    const { apiGet } = await import('@/api')
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path === '/ytdlp/latest') return { available: false, error: '無法查詢上游版本' } as any
      return {} as any
    })

    await wrapper.find('[data-testid="ytdlp-check"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="ytdlp-offline"]').text()).toContain('無法查詢')
    expect(wrapper.find('[data-testid="ytdlp-update"]').exists()).toBe(false)
  })
})
