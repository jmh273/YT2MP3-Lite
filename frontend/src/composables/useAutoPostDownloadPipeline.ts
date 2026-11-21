import { ref, watch, type Ref } from 'vue'
import { useDownloadStore } from '@/stores/download'
import { useNormalizeStore } from '@/stores/normalize'

export type RightTab = 'download' | 'normalize'
type PipelineStage = 'idle' | 'normalizing'

/**
 * 下載完成後自動接續音量正規化（只對 mp3 批次）。
 * 完整版在正規化之後還會接「上傳 Google Drive」；Lite 不需要授權，所以沒有這一段。
 */
export function useAutoPostDownloadPipeline(activeRightTab: Ref<RightTab>) {
  const downloadStore = useDownloadStore()
  const normalizeStore = useNormalizeStore()
  const pipelineStage = ref<PipelineStage>('idle')
  const pipelineDir = ref('')

  watch(() => downloadStore.downloading, async (now, prev) => {
    if (!(prev === true && now === false)) return
    if (!downloadStore.autoPipeline) return
    const dir = downloadStore.lastDownloadDir
    if (!dir) return
    if (downloadStore.lastFormat !== 'mp3') return

    pipelineDir.value = dir
    pipelineStage.value = 'normalizing'
    activeRightTab.value = 'normalize'
    try {
      await normalizeStore.loadDirectory(dir)
    } catch {
      // loadDirectory 內部已吞錯；無論成敗都往下判斷有無檔可正規化
    }
    // 沒有可正規化的檔就直接結束，避免 startBatch 因 files=0 提早 return、
    // status 永不為 done 而卡在 normalizing。
    if (normalizeStore.files.length === 0) {
      pipelineStage.value = 'idle'
      return
    }
    normalizeStore.startBatch().catch(() => {
      pipelineStage.value = 'idle'
    })
  })

  watch(() => normalizeStore.status, (status) => {
    if (pipelineStage.value === 'normalizing' && status === 'done') {
      pipelineStage.value = 'idle'
    }
  })

  return { pipelineStage, pipelineDir }
}
