<template>
  <div class="min-h-screen">
    <!-- Navbar -->
    <NavBar />
    
    <main class="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
      <!-- Report Selector -->
      <div class="flex items-center justify-between bg-white/5 p-4 rounded-2xl border border-white/10">
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-3">
            <a-date-picker 
              v-model:value="selectedDate" 
              :allow-clear="false"
              class="bg-dark-card border-white/10 w-40"
            />
          </div>
          <div class="text-[10px] text-gray-500 flex items-center gap-1 px-1">
            <i class="fa-solid fa-clock text-[9px]"></i>
             {{ reportTimeRange }}
          </div>
        </div>
        
        <div class="flex bg-black/20 p-1 rounded-xl border border-white/5">
          <button 
            @click="reportType = 'morning'"
            :class="[
              'px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2',
              reportType === 'morning' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20' : 'text-gray-400 hover:text-gray-200'
            ]"
          >
            <i class="fa-solid fa-sun text-xs"></i> 早报
          </button>
          <button 
            @click="reportType = 'evening'"
            :class="[
              'px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2',
              reportType === 'evening' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20' : 'text-gray-400 hover:text-gray-200'
            ]"
          >
            <i class="fa-solid fa-moon text-xs"></i> 晚报
          </button>
        </div>
      </div>

      <!-- Stats Overview -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="glass-card rounded-2xl p-5 flex items-center justify-between group">
          <div>
            <p class="text-sm font-medium text-gray-400">本次新闻</p>
            <div class="flex items-end gap-2 mt-1">
              <span class="text-3xl font-bold text-white group-hover:text-brand-400 transition-colors">{{ filteredNews.length }}</span>
              <span class="text-xs text-gray-500">/{{ newsStore.historyTotal }}</span>
            </div>
          </div>
          <div class="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center">
            <i class="fa-solid fa-bolt text-blue-400 text-xl"></i>
          </div>
        </div>
        <router-link to="/vessel-map" target="_blank" class="glass-card rounded-2xl p-5 flex items-center justify-between group hover:border-white/20 transition-colors">
          <div>
            <p class="text-sm font-medium text-gray-400">跟踪船舶</p>
            <div class="flex items-end gap-2 mt-1">
              <span class="text-3xl font-bold text-white group-hover:text-green-400 transition-colors">{{ vesselStore.trackedCount }}</span>
              <span class="text-xs text-gray-500">/{{ vesselStore.totalCount }}</span>
            </div>
          </div>
          <div class="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center">
            <i class="fa-solid fa-ship text-green-400 text-xl"></i>
          </div>
        </router-link>
      </div>

      <!-- Main Content Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- Left Column: Quick Summary -->
        <div v-show="false" class="lg:col-span-1 space-y-6">
          <div class="glass-card rounded-2xl p-6 h-full">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <i class="fa-solid fa-bolt text-yellow-400"></i> 今日速览
            </h3>
            <div class="space-y-3">
              <div v-if="loading" class="animate-pulse flex space-x-4">
                <div class="flex-1 space-y-4 py-1">
                  <div class="h-4 bg-slate-700 rounded w-3/4"></div>
                  <div class="h-4 bg-slate-700 rounded"></div>
                </div>
              </div>
              <div 
                v-else 
                v-for="item in quickSummary" 
                :key="item.id"
                @click="openDetail(item)"
                class="bg-white/5 rounded-lg p-3 border border-white/5 hover:border-brand-500/20 transition-colors cursor-pointer"
              >
                <div class="flex items-start gap-2">
                  <div :class="['w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5', getCategoryMeta(item.category).bg]">
                    <i :class="['fa-solid', getCategoryMeta(item.category).icon, getCategoryMeta(item.category).color, 'text-xs']"></i>
                  </div>
                  <div class="flex-1">
                    <h4 class="text-sm font-medium text-gray-200 line-clamp-1">{{ item.title_cn || item.article_title }}</h4>
                    <p class="text-xs text-gray-400 mt-1 line-clamp-1">{{ item.summary_cn || '暂无摘要' }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: Categories Grid -->
        <div class="lg:col-span-4">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div 
              v-for="(meta, key) in categories" 
              :key="key"
              :class="['glass-card rounded-xl flex flex-col md:h-[400px] min-h-[120px] overflow-hidden transition-all duration-300 hover:shadow-lg border-t-2', getCategoryMeta(key).border.replace('border-', 'border-t-')]"
            >
              <!-- Card Header -->
              <div class="p-4 border-b border-white/5 flex justify-between items-center bg-white/5">
                <div class="flex items-center gap-2">
                  <div :class="['w-8 h-8 rounded-lg', getCategoryMeta(key).bg, 'flex items-center justify-center']">
                    <i :class="['fa-solid', getCategoryMeta(key).icon, getCategoryMeta(key).color]"></i>
                  </div>
                  <h3 class="font-bold text-gray-200">{{ meta.name }}</h3>
                </div>
                <span class="text-xs font-mono bg-slate-800 px-2 py-1 rounded text-gray-400">{{ getGroupedArticles(key).length }}</span>
              </div>

              <!-- Card Body -->
              <div v-if="getGroupedArticles(key).length === 0" class="flex-1 flex items-center justify-center text-gray-500 text-sm">
                暂无数据
              </div>
              <div v-else class="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                <div 
                  v-for="group in getGroupedArticles(key)" 
                  :key="group.article_id || group.article_url"
                  @click="openDetail(group)"
                  class="p-3 rounded-lg hover:bg-white/5 cursor-pointer transition-colors group border border-transparent hover:border-white/5"
                >
                  <div class="flex justify-between items-start">
                    <h4 class="text-sm font-medium text-gray-300 group-hover:text-white line-clamp-2 leading-snug">
                      {{ formatTitle(group, key) }}
                    </h4>
                    <span class="text-[10px] text-gray-500 whitespace-nowrap ml-2 mt-0.5">{{ formatTime(group.pub_date, group.created_at) }}</span>
                  </div>
                  <p class="text-xs text-gray-500 mt-1 line-clamp-1 group-hover:text-gray-400">
                    {{ group.summary_cn || group.article_title }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Detail Modal -->
    <a-modal
      v-model:open="modalVisible"
      :title="currentArticle?.title_cn || currentArticle?.article_title"
      :footer="null"
      :width="800"
      class="detail-modal"
      centered
    >
      <div class="max-h-[70vh] overflow-y-auto custom-scrollbar">
        <!-- Tags -->
        <div class="flex flex-wrap gap-2 mb-4">
          <span :class="['px-2 py-1 rounded-full text-xs', getCategoryMeta(currentArticle?.category).bg, getCategoryMeta(currentArticle?.category).color, 'border', getCategoryMeta(currentArticle?.category).border]">
            {{ getCategoryMeta(currentArticle?.category).name }}
          </span>
          <span v-if="currentArticle?.source_name" class="px-2 py-1 rounded-full text-xs bg-white/5 text-gray-300 border border-white/10">
            {{ currentArticle.source_name.length > 5 ? currentArticle.source_name.slice(0, 5) : currentArticle.source_name }}
          </span>
          <span class="px-2 py-1 rounded-full text-xs bg-white/5 text-gray-400 border border-white/10 flex items-center gap-1">
            <i class="fa-solid fa-clock"></i>
            发布时间: {{ currentArticle?.pub_date || '未知' }}
          </span>
        </div>

        <!-- Content -->
        <div class="prose prose-invert prose-sm max-w-none text-gray-300">
          <div v-if="currentArticle?.summary_cn" class="mb-4 font-medium text-gray-300">
            {{ currentArticle.summary_cn }}
          </div>
        </div>

        <!-- Image -->
        <div v-if="currentArticle?.screenshot_path" class="mt-6 group relative cursor-pointer">
          <img :src="currentArticle.screenshot_path" alt="Screenshot" class="w-full rounded-lg border border-slate-700 shadow-lg">
        </div>

        <!-- Translation -->
        <div class="mt-6 bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
          <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">原文翻译</h4>
          <div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {{ currentArticle?.full_text_cn || '暂无全文翻译' }}
          </div>
        </div>

        <!-- AI Analysis -->
        <div class="mt-6 bg-slate-800/50 rounded-xl p-4 border border-brand-500/20">
          <h4 class="text-sm font-bold text-brand-400 mb-3 flex items-center gap-2">
            <i class="fa-solid fa-robot"></i> AI 分析过程
          </h4>
          <div class="mb-4">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-1">Qwen2.5 纯文字解析：</span>
            <p class="text-gray-200 text-sm leading-relaxed">{{ currentArticle?.summary_cn || '暂无摘要' }}</p>
          </div>
          <div class="mb-4">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-1">Qwen3-VL多模态识别</span>
            <p class="text-gray-300 text-sm leading-relaxed italic">{{ currentArticle?.vl_desc || '暂无描述' }}</p>
          </div>
          <div v-if="currentArticle?.details" class="pt-3 border-t border-white/10">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-2">关键字段提取：</span>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div v-if="currentArticle.details.project_name" class="flex gap-2">
                <span class="text-gray-500">项目名称:</span>
                <span class="text-gray-300">{{ currentArticle.details.project_name }}</span>
              </div>
              <div v-if="currentArticle.details.location" class="flex gap-2">
                <span class="text-gray-500">位置:</span>
                <span class="text-gray-300">{{ currentArticle.details.location }}</span>
              </div>
              <div v-if="currentArticle.details.contractor" class="flex gap-2">
                <span class="text-gray-500">承包商:</span>
                <span class="text-gray-300">{{ currentArticle.details.contractor }}</span>
              </div>
              <div v-if="currentArticle.details.client" class="flex gap-2">
                <span class="text-gray-500">客户:</span>
                <span class="text-gray-300">{{ currentArticle.details.client }}</span>
              </div>
              <div v-if="currentArticle.details.amount" class="flex gap-2">
                <span class="text-gray-500">金额:</span>
                <span class="text-gray-300">{{ currentArticle.details.amount }} {{ currentArticle.details.currency || '' }}</span>
              </div>
              <div v-if="currentArticle.details.event_type" class="flex gap-2">
                <span class="text-gray-500">事件类型:</span>
                <span class="text-gray-300">{{ currentArticle.details.event_type }}</span>
              </div>
              <div v-if="currentArticle.details.type" class="flex gap-2">
                <span class="text-gray-500">类型:</span>
                <span class="text-gray-300">{{ currentArticle.details.type }}</span>
              </div>
              <div v-if="currentArticle.details.vessel_name" class="flex gap-2">
                <span class="text-gray-500">船舶名称:</span>
                <span class="text-gray-300">{{ currentArticle.details.vessel_name }}</span>
              </div>
              <div v-if="currentArticle.details.company" class="flex gap-2">
                <span class="text-gray-500">公司:</span>
                <span class="text-gray-300">{{ currentArticle.details.company }}</span>
              </div>
              <div v-if="currentArticle.details.institution" class="flex gap-2">
                <span class="text-gray-500">机构:</span>
                <span class="text-gray-300">{{ currentArticle.details.institution }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="mt-4 flex justify-end gap-3">
        <a :href="currentArticle?.article_url || currentArticle?.url || '#'" target="_blank" class="inline-flex h-9 justify-center rounded-lg bg-brand-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-500 transition-colors items-center gap-2">
          <i class="fa-solid fa-external-link-alt"></i> 原文链接
        </a>
        <a-button @click="modalVisible = false" class="h-9">
          <i class="fa-solid fa-xmark mr-1"></i> 关闭
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useNewsStore, useVesselStore, type NewsItem } from '@/stores'
import NavBar from '@/components/NavBar.vue'
import dayjs, { Dayjs } from 'dayjs'

const newsStore = useNewsStore()
const vesselStore = useVesselStore()

const loading = ref(true)
const modalVisible = ref(false)
const currentArticle = ref<NewsItem | null>(null)
const lastOpenedId = ref<string | null>(null)
const scrollPositions = ref<Record<string, number>>({})

// Report filtering state
const reportType = ref<'morning' | 'evening'>(dayjs().hour() < 14 ? 'morning' : 'evening')
const selectedDate = ref<Dayjs>(dayjs())

const reportTimeRange = computed(() => {
  if (reportType.value === 'morning') {
    return `${selectedDate.value.subtract(1, 'day').format('MM-DD')} 18:00 至 ${selectedDate.value.format('MM-DD')} 08:00`
  }
  return `${selectedDate.value.subtract(1, 'day').format('MM-DD')} 18:00 至 ${selectedDate.value.format('MM-DD')} 18:00`
})

const filteredNews = computed(() => {
  const start = reportType.value === 'morning' 
    ? selectedDate.value.subtract(1, 'day').hour(18).minute(0).second(0)
    : selectedDate.value.subtract(1, 'day').hour(18).minute(0).second(0) // Evening now covers full 24h cycle from previous evening
    
  const end = reportType.value === 'morning'
    ? selectedDate.value.hour(8).minute(0).second(0)
    : selectedDate.value.hour(18).minute(0).second(0)

  return newsStore.newsList.filter(item => {
    const pubTime = dayjs(item.pub_date || item.created_at)
    return pubTime.isAfter(start) && pubTime.isBefore(end)
  })
})

const categories = {
  Market: { name: '市场动态', icon: 'fa-chart-line', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  Bid: { name: '中标信息', icon: 'fa-gavel', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  Project: { name: '项目信息', icon: 'fa-building', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20' },
  Equipment: { name: '设备修造', icon: 'fa-gears', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  'R&D': { name: '科技研发', icon: 'fa-flask', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  Regulation: { name: '技术法规', icon: 'fa-scale-balanced', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  Other: { name: '其他信息', icon: 'fa-circle-info', color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20' }
}

const quickSummary = computed(() => {
  const seenTitles = new Set()
  const unique: NewsItem[] = []
  for (const e of filteredNews.value) {
    const title = e.title_cn || e.article_title
    if (!seenTitles.has(title)) {
      seenTitles.add(title)
      unique.push(e)
    }
  }
  return unique.slice(0, 5)
})

function getCategoryMeta(category: string | undefined) {
  const cat = category || 'Project'
  return categories[cat as keyof typeof categories] || categories.Project
}

function getGroupedArticles(category: string) {
  const seen = new Set<string>()
  const unique: NewsItem[] = []
  for (const item of filteredNews.value) {
    if (item.category !== category) continue
    const key = item.article_id || item.article_url || item.title_cn || item.article_title || item.id
    if (!key) {
      unique.push(item)
      continue
    }
    if (seen.has(key)) continue
    seen.add(key)
    unique.push(item)
  }
  return unique.slice(0, 10)
}

function formatTitle(item: NewsItem, category: string) {
  let title = item.title_cn || item.summary_cn || item.article_title || ''
  if (title.length > 50) title = title.substring(0, 50) + '...'
  
  if (category === 'Bid' && item.contractor) {
    title = `[中标: ${item.contractor}] ${title}`
  } else if (category === 'Project' && item.location) {
    let locationDisplay = item.location
    if (item.location.includes(',')) {
      const parts = item.location.split(',').map(p => p.trim())
      locationDisplay = parts[parts.length - 1]
    }
    title = `[${locationDisplay}] ${title}`
  }
  return title
}

function formatTime(pubDate: string | undefined, createdAt: string | undefined) {
  if (pubDate) {
    const date = new Date(pubDate)
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleDateString('zh-CN')
    }
  }
  if (!createdAt) return ''
  const date = new Date(createdAt)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function openDetail(item: NewsItem) {
  const prevId = lastOpenedId.value
  const currentId = item.id || null
  
  if (prevId && currentId && prevId !== currentId) {
    const modalBody = document.querySelector('.ant-modal-body')
    if (modalBody) {
      scrollPositions.value[prevId] = modalBody.scrollTop
    }
  }
  
  lastOpenedId.value = currentId
  currentArticle.value = item
  modalVisible.value = true
  
  setTimeout(() => {
    const modalBody = document.querySelector('.ant-modal-body')
    if (modalBody && currentId) {
      if (prevId === currentId && scrollPositions.value[currentId]) {
        modalBody.scrollTop = scrollPositions.value[currentId]
      } else {
        modalBody.scrollTop = 0
      }
    }
  }, 100)
}

onMounted(async () => {
  await Promise.all([
    newsStore.fetchNews(),
    vesselStore.fetchVessels()
  ])
  loading.value = false
})

watch(modalVisible, (isOpen) => {
  if (isOpen) {
    setTimeout(() => {
      const modalBody = document.querySelector('.ant-modal-body')
      if (modalBody) {
        const isSame = currentArticle.value?.id === lastOpenedId.value
        if (!isSame) {
          modalBody.scrollTop = 0
        }
      }
    }, 100)
  }
})
</script>

<style scoped>
:deep(.glass-card) {
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

:deep(.ant-modal-content) {
  background: rgba(30, 41, 59, 0.95) !important;
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.ant-modal-header) {
  background: transparent !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.ant-modal-title) {
  color: #fff !important;
}

:deep(.ant-modal-close-x) {
  color: #9ca3af !important;
}

:deep(.ant-modal-body) {
  color: #e2e8f0;
}
</style>
