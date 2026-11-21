// 設定頁改了輸出資料夾後回到首頁：「下載到」的根目錄要跟著換成新的 output_path。
// 後端下載時只取這個路徑的最後一段資料夾名、接在「目前的」output_path 後面，
// 所以畫面上的根目錄若停在舊值，顯示的位置就和檔案實際存放的位置不一致。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SelectedVideos from '@/components/SelectedVideos.vue'
import { useDownloadStore } from '@/stores/download'

vi.mock('@/api', () => ({
  API_BASE: '/api',
  apiPost: vi.fn(),
  apiGet: vi.fn(),
}))

async function mountWithOutputPath(outputPath: string) {
  const { apiGet } = await import('@/api')
  vi.mocked(apiGet).mockImplementation(async (url: string) => {
    if (url === '/settings') return { output_path: outputPath } as any
    return { next_seq: '01', existing: [] } as any
  })
  const wrapper = mount(SelectedVideos)
  await flushPromises()
  return wrapper.find<HTMLInputElement>('[data-testid="download-target-dir"]').element
}

describe('SelectedVideos 輸出資料夾變更後的下載目錄', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-21T12:00:00'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('沿用的預設目錄：根目錄換成新的 output_path', async () => {
    const download = useDownloadStore()
    download.targetDirPath = String.raw`C:\Old\YT-MP3\20261121`  // 上次在首頁時算好的（舊根目錄）

    const input = await mountWithOutputPath(String.raw`D:\New\Music`)

    expect(input.value).toBe(String.raw`D:\New\Music\20261121`)
    expect(download.targetDirPath).toBe(String.raw`D:\New\Music\20261121`)
  })

  it('自訂的資料夾名保留，只換根目錄', async () => {
    const download = useDownloadStore()
    download.targetDirPath = String.raw`C:\Old\YT-MP3\20261121_晚上`

    const input = await mountWithOutputPath(String.raw`D:\New\Music`)

    expect(input.value).toBe(String.raw`D:\New\Music\20261121_晚上`)
  })

  it('根目錄沒變時維持原值', async () => {
    const download = useDownloadStore()
    download.targetDirPath = String.raw`D:\Music\20261121_晚上`

    const input = await mountWithOutputPath(String.raw`D:\Music`)

    expect(input.value).toBe(String.raw`D:\Music\20261121_晚上`)
  })
})
