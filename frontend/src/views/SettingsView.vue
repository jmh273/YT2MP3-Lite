<template>
  <div class="settings-page">
    <header>
      <router-link to="/" class="back">← 返回</router-link>
      <h1>設定</h1>
    </header>

    <div class="tab-bar">
      <button
        class="tab"
        :class="{ active: activeTab === 'settings' }"
        data-testid="tab-settings"
        @click="activeTab = 'settings'"
      >
        設定
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'ytdlp' }"
        data-testid="tab-ytdlp"
        @click="activeTab = 'ytdlp'"
      >
        下載元件
      </button>
    </div>

    <div v-if="activeTab === 'settings'" class="form">
      <label>
        MP3 輸出資料夾
        <input v-model="outputPath" type="text" placeholder="例：C:\Users\你的名字\Music\YT-MP3" />
      </label>
      <label>
        目標響度（dB SPL）
        <input
          v-model.number="normalizeTargetDb"
          type="number"
          step="0.5"
          min="80"
          max="100"
          @input="validateNormalizeTargetDb"
        />
        <small class="hint">89 = mp3gain 預設；接近 YouTube 響度建議 92–93</small>
        <span v-if="normalizeTargetDbError" class="field-error">{{ normalizeTargetDbError }}</span>
      </label>
      <label>
        同時處理數量
        <input data-testid="download-concurrency" v-model.number="concurrency" type="number" min="1" max="8" />
        <small class="hint">套用於下載與音量正規化；預設 2。同時下載太多容易被 YouTube 限速。</small>
      </label>
      <button data-testid="save-settings" @click="save" :disabled="saving || !!normalizeTargetDbError">
        {{ saving ? '儲存中...' : '儲存' }}
      </button>
      <p v-if="saved" class="ok">已儲存！</p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>


    <section v-if="activeTab === 'ytdlp'" class="ytdlp-panel">
      <p class="hint">
        yt-dlp 依賴 YouTube 的內部實作，YouTube 一改動就可能導致下載失敗。
        這裡可以在不等新版程式的情況下自行更新下載元件。
      </p>

      <dl class="ytdlp-versions" data-testid="ytdlp-versions">
        <div><dt>yt-dlp</dt><dd>{{ ytdlpInfo?.yt_dlp ?? '—' }}</dd></div>
        <div>
          <dt>EJS solver</dt>
          <dd :class="{ missing: ytdlpInfo && ytdlpInfo.yt_dlp_ejs_usable === false }">
            <template v-if="ytdlpInfo && ytdlpInfo.yt_dlp_ejs_usable === false">
              無法載入 — 下載很可能失敗
            </template>
            <template v-else>{{ ytdlpInfo?.yt_dlp_ejs ?? '—' }}</template>
          </dd>
        </div>
        <div>
          <dt>目前來源</dt>
          <dd>
            <span class="src" :class="ytdlpInfo?.source">
              {{ ytdlpInfo?.source === 'managed' ? '受管版本（可回退）' : '內建版本' }}
            </span>
          </dd>
        </div>
        <div>
          <dt>JS runtime</dt>
          <dd :class="{ missing: !ytdlpInfo?.js_runtime }">
            {{ ytdlpInfo?.js_runtime ?? '未偵測到 — 下載很可能失敗' }}
          </dd>
        </div>
      </dl>

      <div class="ytdlp-actions">
        <button class="check-btn" data-testid="ytdlp-check" @click="checkLatest" :disabled="ytdlpBusy">
          {{ ytdlpBusy ? '處理中…' : '查詢最新版' }}
        </button>
        <button
          v-if="ytdlpInfo?.source === 'managed'"
          class="revert-btn"
          data-testid="ytdlp-revert"
          @click="revertYtdlp"
          :disabled="ytdlpBusy"
        >
          回退為內建版本
        </button>
      </div>

      <p v-if="latestInfo && !latestInfo.available" class="error" data-testid="ytdlp-offline">
        {{ latestInfo.error }}
      </p>
      <template v-else-if="latestInfo?.available">
        <p class="latest-line" data-testid="ytdlp-latest">
          上游最新：yt-dlp {{ latestInfo.versions?.yt_dlp }} · EJS {{ latestInfo.versions?.yt_dlp_ejs }}
        </p>
        <button class="check-btn" data-testid="ytdlp-update" @click="updateYtdlp" :disabled="ytdlpBusy">
          {{ ytdlpBusy ? '更新中…' : '更新下載元件' }}
        </button>
      </template>

      <p v-if="ytdlpError" class="error" data-testid="ytdlp-error">{{ ytdlpError }}</p>
      <p v-if="ytdlpNotice" class="ok" data-testid="ytdlp-notice">{{ ytdlpNotice }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiGet, apiPost, apiPut } from '@/api'

const activeTab = ref<'settings' | 'ytdlp'>('settings')

// ── 下載元件（yt-dlp）版本管理 ────────────────────────────────────────────────
interface YtdlpInfo {
  yt_dlp: string
  yt_dlp_ejs: string | null
  yt_dlp_ejs_usable?: boolean
  source: 'managed' | 'bundled'
  js_runtime: string | null
}
interface LatestInfo {
  available: boolean
  error?: string
  versions?: { yt_dlp: string; yt_dlp_ejs: string }
}

const ytdlpInfo = ref<YtdlpInfo | null>(null)
const latestInfo = ref<LatestInfo | null>(null)
const ytdlpBusy = ref(false)
const ytdlpError = ref('')
const ytdlpNotice = ref('')

async function loadYtdlpInfo() {
  try {
    ytdlpInfo.value = await apiGet<YtdlpInfo>('/ytdlp/version')
  } catch {
    ytdlpInfo.value = null
  }
}

async function checkLatest() {
  ytdlpBusy.value = true
  ytdlpError.value = ''
  ytdlpNotice.value = ''
  try {
    latestInfo.value = await apiGet<LatestInfo>('/ytdlp/latest')
  } catch (e: any) {
    // 離線時降級為「無法查詢」，維持目前版本可用
    latestInfo.value = { available: false, error: '無法查詢上游版本，維持目前版本。' }
  } finally {
    ytdlpBusy.value = false
  }
}

async function updateYtdlp() {
  ytdlpBusy.value = true
  ytdlpError.value = ''
  ytdlpNotice.value = ''
  try {
    const r = await apiPost<{ installed: Record<string, string>; message: string }>(
      '/ytdlp/update', {},
    )
    ytdlpNotice.value = r.message
    await loadYtdlpInfo()
  } catch (e: any) {
    ytdlpError.value = e?.message || '更新失敗，維持目前版本。'
  } finally {
    ytdlpBusy.value = false
  }
}

async function revertYtdlp() {
  ytdlpBusy.value = true
  ytdlpError.value = ''
  ytdlpNotice.value = ''
  try {
    const r = await apiPost<{ message: string }>('/ytdlp/revert', {})
    ytdlpNotice.value = r.message
    await loadYtdlpInfo()
  } catch (e: any) {
    ytdlpError.value = e?.message || '回退失敗。'
  } finally {
    ytdlpBusy.value = false
  }
}


const outputPath = ref('')
const normalizeTargetDb = ref(89)
const concurrency = ref(2)
const normalizeTargetDbError = ref('')
const saving = ref(false)
const saved = ref(false)
const error = ref('')

onMounted(async () => {
  loadYtdlpInfo()
  const data = await apiGet<{
    output_path: string
    normalize_target_db: number
    download_concurrency: number
  }>('/settings')
  outputPath.value = data.output_path
  normalizeTargetDb.value = data.normalize_target_db ?? 89
  concurrency.value = data.download_concurrency ?? 2
})


function validateNormalizeTargetDb() {
  const v = normalizeTargetDb.value
  if (typeof v !== 'number' || Number.isNaN(v) || v < 80 || v > 100) {
    normalizeTargetDbError.value = '請輸入 80 到 100 之間的數值'
  } else {
    normalizeTargetDbError.value = ''
  }
}

async function save() {
  validateNormalizeTargetDb()
  if (normalizeTargetDbError.value) return
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    await apiPut('/settings', {
      output_path: outputPath.value,
      normalize_target_db: normalizeTargetDb.value,
      download_concurrency: concurrency.value,
    })
    saved.value = true
  } catch (e: any) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-page { max-width: 600px; margin: 0 auto; padding: 1.5rem; }
header { display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; }
h1 { margin: 0; }
.back { text-decoration: none; color: #555; }
.form { display: flex; flex-direction: column; gap: 1.2rem; }
label { display: flex; flex-direction: column; gap: 0.3rem; font-weight: 500; }
input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; }
button { padding: 0.6rem 1.5rem; background: #ff0000; color: white; border: none; border-radius: 4px; cursor: pointer; align-self: flex-start; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.ok { color: green; }
.error { color: red; }
.field-error { color: red; font-size: 0.82rem; font-weight: normal; }
.hint { color: #888; font-size: 0.75rem; font-weight: normal; }

.tab-bar { display: flex; border-bottom: 1px solid #ddd; margin-bottom: 1.5rem; }
.tab {
  flex: 1;
  padding: 0.6rem 0.4rem;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 0.95rem;
  color: #555;
  border-bottom: 2px solid transparent;
  align-self: stretch;
  border-radius: 0;
}
.tab:hover { background: #f5f5f5; }
.tab.active { color: #c00; border-bottom-color: #c00; font-weight: 600; }

.ytdlp-panel { margin-top: 0; }
.ytdlp-versions { margin: 0.8rem 0; display: flex; flex-direction: column; gap: 0.35rem; }
.ytdlp-versions > div { display: flex; gap: 0.6rem; font-size: 0.85rem; }
.ytdlp-versions dt { color: #666; min-width: 7rem; margin: 0; }
.ytdlp-versions dd { margin: 0; font-variant-numeric: tabular-nums; word-break: break-all; }
.ytdlp-versions dd.missing { color: #c00; }
.src.managed { color: #1565c0; }
.src.bundled { color: #666; }
.ytdlp-actions { display: flex; gap: 0.6rem; flex-wrap: wrap; }
.revert-btn { padding: 0.4rem 1rem; background: #fff; color: #b25e00; border: 1px solid #ffd599; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }
.latest-line { font-size: 0.85rem; color: #333; margin: 0.6rem 0 0.4rem; }
.check-btn { padding: 0.6rem 1.5rem; background: #ff0000; color: white; border: none; border-radius: 4px; cursor: pointer; }
.check-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
