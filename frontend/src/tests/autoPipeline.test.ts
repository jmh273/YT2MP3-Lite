import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick, ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useAutoPostDownloadPipeline, type RightTab } from '@/composables/useAutoPostDownloadPipeline'
import { useDownloadStore } from '@/stores/download'
import { useNormalizeStore } from '@/stores/normalize'

vi.mock('@/api', () => ({
  API_BASE: '/api',
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}))

describe('useAutoPostDownloadPipeline（Lite：下載 → 正規化，沒有上傳）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('mp3 下載完成後切到正規化分頁並跑正規化，完成後回到 idle', async () => {
    const activeRightTab = ref<RightTab>('download')
    const download = useDownloadStore()
    const normalize = useNormalizeStore()
    const loadDirectory = vi.spyOn(normalize, 'loadDirectory').mockResolvedValue(undefined)
    const startBatch = vi.spyOn(normalize, 'startBatch').mockResolvedValue(undefined)
    normalize.files = [{ filename: 'a.mp3', size_bytes: 1, needs_rename: false, suggested_name: 'a.mp3' }]

    download.autoPipeline = true
    download.lastDownloadDir = 'C:/out/20260601'
    download.lastFormat = 'mp3'
    download.downloading = true
    const pipeline = useAutoPostDownloadPipeline(activeRightTab)

    download.downloading = false
    await nextTick()
    await Promise.resolve()

    expect(pipeline.pipelineStage.value).toBe('normalizing')
    expect(activeRightTab.value).toBe('normalize')
    expect(loadDirectory).toHaveBeenCalledWith('C:/out/20260601')
    expect(startBatch).toHaveBeenCalled()

    normalize.status = 'done'
    await nextTick()

    expect(pipeline.pipelineStage.value).toBe('idle')
    expect(activeRightTab.value).toBe('normalize')
  })

  it('mp3 目錄裡沒有可正規化的檔：不呼叫 startBatch，直接回到 idle', async () => {
    const activeRightTab = ref<RightTab>('download')
    const download = useDownloadStore()
    const normalize = useNormalizeStore()
    const loadDirectory = vi.spyOn(normalize, 'loadDirectory').mockResolvedValue(undefined)
    const startBatch = vi.spyOn(normalize, 'startBatch').mockResolvedValue(undefined)
    normalize.files = []

    download.autoPipeline = true
    download.lastDownloadDir = 'C:/out/empty'
    download.lastFormat = 'mp3'
    download.downloading = true
    const pipeline = useAutoPostDownloadPipeline(activeRightTab)

    download.downloading = false
    await nextTick()
    await Promise.resolve()

    expect(loadDirectory).toHaveBeenCalledWith('C:/out/empty')
    expect(startBatch).not.toHaveBeenCalled()
    expect(pipeline.pipelineStage.value).toBe('idle')
  })

  it('mp4 下載不做正規化，也不切換分頁', async () => {
    const activeRightTab = ref<RightTab>('download')
    const download = useDownloadStore()
    const normalize = useNormalizeStore()
    const loadDirectory = vi.spyOn(normalize, 'loadDirectory').mockResolvedValue(undefined)
    const startBatch = vi.spyOn(normalize, 'startBatch').mockResolvedValue(undefined)

    download.autoPipeline = true
    download.lastDownloadDir = 'C:/out/videos'
    download.lastFormat = 'mp4'
    download.downloading = true
    const pipeline = useAutoPostDownloadPipeline(activeRightTab)

    download.downloading = false
    await nextTick()

    expect(activeRightTab.value).toBe('download')
    expect(loadDirectory).not.toHaveBeenCalled()
    expect(startBatch).not.toHaveBeenCalled()
    expect(pipeline.pipelineStage.value).toBe('idle')
  })

  it('沒開自動接續或沒有目錄時什麼都不做', async () => {
    const activeRightTab = ref<RightTab>('download')
    const download = useDownloadStore()
    const normalize = useNormalizeStore()
    const loadDirectory = vi.spyOn(normalize, 'loadDirectory').mockResolvedValue(undefined)

    download.autoPipeline = false
    download.lastDownloadDir = ''
    download.downloading = true
    useAutoPostDownloadPipeline(activeRightTab)

    download.downloading = false
    await nextTick()

    expect(loadDirectory).not.toHaveBeenCalled()
    expect(activeRightTab.value).toBe('download')
  })
})
