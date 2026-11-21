<template>
  <div class="home">
    <header>
      <h1>YT → MP3 Lite</h1>
      <div class="header-actions">
        <label
          class="redownload-toggle"
          :class="{ on: downloadStore.allowRedownload }"
          title="開啟後，已下載過的影片可再次勾選下載。此開關不會被記住，重新整理後自動關閉。"
        >
          <input type="checkbox" v-model="downloadStore.allowRedownload" />
          <span>允許再次下載</span>
        </label>
        <router-link to="/settings">設定</router-link>
      </div>
    </header>

    <div class="layout">
      <!-- 來源：貼網址 / 搜尋 -->
      <main class="source-pane">
        <div class="tab-bar">
          <button
            class="tab"
            data-testid="source-tab-url"
            :class="{ active: activeSource === 'url' }"
            @click="activeSource = 'url'"
          >
            🔗 貼網址
          </button>
          <button
            class="tab"
            data-testid="source-tab-search"
            :class="{ active: activeSource === 'search' }"
            @click="activeSource = 'search'"
          >
            🔍 搜尋
          </button>
        </div>
        <div class="source-content">
          <KeepAlive>
            <UrlDownloadFeed v-if="activeSource === 'url'" />
            <SearchVideosFeed v-else />
          </KeepAlive>
        </div>
      </main>

      <!-- 工作區：下載 / 音量正規化 -->
      <aside class="right-pane-progress">
        <div class="tab-bar">
          <button
            class="tab"
            :class="{ active: activeRightTab === 'download' }"
            @click="activeRightTab = 'download'"
          >
            下載
            <span v-if="activeRightTab !== 'download' && downloadStore.downloading" class="dot" />
          </button>
          <button
            class="tab"
            :class="{ active: activeRightTab === 'normalize' }"
            @click="activeRightTab = 'normalize'"
          >
            音量正規化
            <span v-if="activeRightTab !== 'normalize' && normalizeStore.status === 'running'" class="dot" />
          </button>
        </div>
        <div class="tab-content">
          <KeepAlive>
            <SelectedVideos v-if="activeRightTab === 'download'" />
            <VolumeNormalizer v-else />
          </KeepAlive>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useDownloadStore } from '@/stores/download'
import { useNormalizeStore } from '@/stores/normalize'
import SearchVideosFeed from '@/components/SearchVideosFeed.vue'
import UrlDownloadFeed from '@/components/UrlDownloadFeed.vue'
import SelectedVideos from '@/components/SelectedVideos.vue'
import VolumeNormalizer from '@/components/VolumeNormalizer.vue'
import { useAutoPostDownloadPipeline, type RightTab } from '@/composables/useAutoPostDownloadPipeline'

const downloadStore = useDownloadStore()
const normalizeStore = useNormalizeStore()
const activeSource = ref<'url' | 'search'>('url')
const activeRightTab = ref<RightTab>('download')
useAutoPostDownloadPipeline(activeRightTab)
</script>

<style scoped>
.home { display: flex; flex-direction: column; height: 100vh; overflow: hidden; box-sizing: border-box; }

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #eee;
  background: white;
  z-index: 10;
  flex-shrink: 0;
}
h1 { margin: 0; font-size: 1.2rem; }
.header-actions { display: flex; gap: 0.75rem; align-items: center; }
.header-actions a { text-decoration: none; color: #333; font-size: 0.9rem; }

/* 全域「允許再次下載」開關：OFF 為安全預設故壓低視覺重量，
   ON 才需要被注意到（使用者可能在別頁忘了它還開著）。 */
.redownload-toggle {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  color: #555;
  cursor: pointer;
  user-select: none;
  padding: 0.2rem 0.5rem;
  border: 1px solid transparent;
  border-radius: 12px;
}
.redownload-toggle input { cursor: pointer; }
.redownload-toggle.on {
  background: #fff4e0;
  color: #b25e00;
  border-color: #ffd599;
  font-weight: 500;
}

.layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  flex: 1;
  overflow: hidden;
}

.source-pane {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.source-content { flex: 1; overflow-y: auto; min-height: 0; padding-right: 0.5rem; }

.right-pane-progress {
  border-left: 1px solid #eee;
  overflow: hidden;
  background: #fafafa;
  display: flex;
  flex-direction: column;
}
.tab-bar { display: flex; border-bottom: 1px solid #ddd; background: #fff; flex-shrink: 0; }
.tab {
  flex: 1; padding: 0.55rem 0.5rem; border: none; background: transparent;
  cursor: pointer; font-size: 0.85rem; color: #555; border-bottom: 2px solid transparent;
  display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem;
}
.tab:hover { background: #f5f5f5; }
.tab.active { color: #c00; border-bottom-color: #c00; font-weight: 600; }
.dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #ff9800; display: inline-block;
}
.tab-content { flex: 1; overflow: hidden; min-height: 0; }
.tab-content > * { height: 100%; overflow-y: auto; }

@media (max-width: 1024px) {
  .layout { grid-template-columns: 1fr 270px; }
}

@media (max-width: 768px) {
  .layout { grid-template-columns: 1fr; grid-template-rows: 1fr auto; }
  .right-pane-progress { border-left: none; border-top: 1px solid #eee; max-height: 40vh; }
}
</style>
