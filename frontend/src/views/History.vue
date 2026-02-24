<template>
  <div class="min-h-screen">
    <!-- Navbar -->
    <NavBar />

    <main class="w-full px-6 space-y-6">
      <!-- Filters -->
      <div class="glass-card rounded-2xl p-5">
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex flex-col">
            <label class="text-xs text-gray-400 mb-1">时间范围</label>
            <a-range-picker 
              v-model:value="dateRange" 
              class="bg-dark-card border border-dark-border"
              format="YYYY-MM-DD"
            />
          </div>
          <div class="w-40 sm:flex-1 sm:min-w-[200px]">
            <label class="text-xs text-gray-400">关键词</label>
            <a-input 
              v-model:value="filters.keyword" 
              placeholder="标题/摘要关键词" 
              class="mt-1 bg-dark-card border border-dark-border"
              @change="handleSearch"
            />
          </div>
          <div class="w-40">
            <label class="text-xs text-gray-400">分类</label>
            <a-select 
              v-model:value="filters.category" 
              placeholder="全部"
              class="w-full mt-1"
              :options="categoryOptions"
              @change="handleSearch"
            />
          </div>
          <div class="w-44">
            <label class="text-xs text-gray-400">网站</label>
            <a-select 
              v-model:value="filters.sourceName" 
              placeholder="全部"
              class="w-full mt-1"
              :options="sourceOptions"
              @change="handleSearch"
            />
          </div>
          <div class="w-32">
            <label class="text-xs text-gray-400">来源类型</label>
            <a-select 
              v-model:value="filters.sourceType" 
              placeholder="全部"
              class="w-full mt-1"
              :options="sourceTypeOptions"
              @change="handleSearch"
            />
          </div>
          <a-button class="ml-auto" @click="resetFilters">
            重置
          </a-button>
        </div>
      </div>

      <!-- List -->
      <div class="space-y-4">
        <div 
          v-for="item in articleList" 
          :key="item.id"
          class="glass-card rounded-2xl p-5 cursor-pointer hover:border-brand-500/20 transition-colors"
          @click="openDetail(item)"
        >
          <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div class="space-y-2">
              <h3 class="text-lg font-semibold text-brand-300">{{ item.title_cn || item.title || '未命名' }}</h3>
              <div class="flex flex-wrap gap-2">
                <span 
                  v-for="cat in item.categories" 
                  :key="cat"
                  class="px-2 py-1 rounded-full text-xs bg-brand-500/10 text-brand-300 border border-brand-500/30"
                >
                  {{ getCategoryLabel(cat) }}
                </span>
                <span v-if="item.source_name" class="px-2 py-1 rounded-full text-xs bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                  {{ item.source_name.slice(0, 5) }}
                </span>
                <span class="px-2 py-1 rounded-full text-xs bg-purple-500/10 text-purple-300 border border-purple-500/30">
                  {{ (item.source_type || '').toLowerCase() === 'rss' ? 'RSS' : 'Origin' }}
                </span>
              </div>
              <p class="text-sm text-gray-300 leading-relaxed">{{ item.summary_cn || '暂无摘要' }}</p>
              <div class="text-xs text-gray-500">发布时间：{{ item.pub_date || '未知' }} · 入库时间：{{ formatDate(item.created_at) }}</div>
            </div>
            <div class="flex-shrink-0">
              <a :href="item.url || '#'" target="_blank" class="stop-prop text-sm text-blue-400 hover:text-blue-300 transition-colors" @click.stop>
                原文链接
              </a>
            </div>
          </div>
        </div>
        <div v-if="articleList.length === 0 && !loading" class="glass-card rounded-2xl p-6 text-center text-gray-400">
          暂无匹配的历史新闻
        </div>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between text-sm text-gray-400">
        <span>共 {{ total }} 条 · 第 {{ filters.page }} 页</span>
        <div class="flex items-center gap-2">
          <a-button :disabled="filters.page <= 1" @click="changePage(filters.page - 1)">上一页</a-button>
          <a-button :disabled="filters.page >= maxPage" @click="changePage(filters.page + 1)">下一页</a-button>
        </div>
      </div>
    </main>

    <!-- Detail Modal -->
    <a-modal
      v-model:open="modalVisible"
      :title="currentArticle?.title_cn || currentArticle?.title"
      :footer="null"
      :width="800"
      centered
    >
      <div class="max-h-[70vh] overflow-y-auto custom-scrollbar">
        <!-- Tags -->
        <div class="flex flex-wrap gap-2 mb-4">
          <span 
            v-for="cat in currentCategories" 
            :key="cat"
            class="px-2 py-1 rounded-full text-xs bg-brand-500/10 text-brand-300 border border-brand-500/30"
          >
            {{ getCategoryLabel(cat) }}
          </span>
          <span v-if="currentArticle?.source_name" class="px-2 py-1 rounded-full text-xs bg-white/5 text-gray-300 border border-white/10">
            {{ currentArticle.source_name.slice(0, 5) }}
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
            <i class="fa-solid fa-robot"></i> AI 智能分析
          </h4>
          <div class="mb-4">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-1">Qwen2.5 纯文字解析：</span>
            <p class="text-gray-200 text-sm leading-relaxed">{{ currentArticle?.summary_cn || '暂无摘要' }}</p>
          </div>
          <div class="mb-4">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-1">Qwen3-VL多模态识别</span>
            <p class="text-gray-300 text-sm leading-relaxed italic">{{ currentArticle?.vl_desc || '暂无描述' }}</p>
          </div>
          <div v-if="currentArticle?.events && currentArticle.events.length > 0" class="pt-3 border-t border-white/10">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-2">关键字段提取：</span>
            <div v-for="(evt, idx) in currentArticle.events" :key="idx" class="mb-3 pb-2 border-b border-white/5 last:border-0 last:pb-0 last:mb-0">
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div v-if="evt.project_name" class="flex gap-2">
                  <span class="text-gray-500">项目名称:</span>
                  <span class="text-gray-300">{{ evt.project_name }}</span>
                </div>
                <div v-if="evt.location" class="flex gap-2">
                  <span class="text-gray-500">位置:</span>
                  <span class="text-gray-300">{{ evt.location }}</span>
                </div>
                <div v-if="evt.contractor" class="flex gap-2">
                  <span class="text-gray-500">承包商:</span>
                  <span class="text-gray-300">{{ evt.contractor }}</span>
                </div>
                <div v-if="evt.client" class="flex gap-2">
                  <span class="text-gray-500">客户:</span>
                  <span class="text-gray-300">{{ evt.client }}</span>
                </div>
                <div v-if="evt.amount" class="flex gap-2">
                  <span class="text-gray-500">金额:</span>
                  <span class="text-gray-300">{{ evt.amount }} {{ evt.currency || '' }}</span>
                </div>
                <div v-if="evt.time" class="flex gap-2">
                  <span class="text-gray-500">时间:</span>
                  <span class="text-gray-300">{{ evt.time }}</span>
                </div>
                <div v-if="evt.content" class="flex gap-2 col-span-2">
                  <span class="text-gray-500">内容:</span>
                  <span class="text-gray-300">{{ evt.content }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="pt-3 border-t border-white/10">
            <span class="text-xs text-gray-500 uppercase font-bold tracking-wider block mb-2">关键字段提取：</span>
            <div class="text-gray-500 text-sm">暂无关键字段信息</div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="mt-4 flex justify-end gap-3">
        <a :href="currentArticle?.url || '#'" target="_blank" class="inline-flex h-9 justify-center rounded-lg bg-brand-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-500 transition-colors items-center gap-2">
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
import { ref, reactive, computed, onMounted, watch } from 'vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { NewsItem } from '@/stores'
import NavBar from '@/components/NavBar.vue'

const loading = ref(false)
const articleList = ref<NewsItem[]>([])
const total = ref(0)
const sources = ref<{ name: string; url?: string }[]>([])

const filters = reactive({
  page: 1,
  pageSize: 20,
  keyword: '',
  category: '',
  sourceType: '',
  sourceName: ''
})

const dateRange = ref<[Dayjs, Dayjs]>([
  dayjs().subtract(29, 'day'),
  dayjs()
])

const categoryOptions = [
  { value: '', label: '全部' },
  { value: 'Market', label: '市场动态' },
  { value: 'Bid', label: '中标信息' },
  { value: 'Project', label: '项目信息' },
  { value: 'Equipment', label: '设备修造' },
  { value: 'R&D', label: '科技研发' },
  { value: 'Regulation', label: '技术法规' }
]

const sourceTypeOptions = [
  { value: '', label: '全部' },
  { value: 'rss', label: 'RSS' },
  { value: 'web', label: 'Origin' }
]

const sourceOptions = computed(() => {
  return [{ value: '', label: '全部' }, ...sources.value.map(s => ({ value: s.name, label: s.name }))]
})

const maxPage = computed(() => Math.ceil(total.value / filters.pageSize) || 1)

const modalVisible = ref(false)
const currentArticle = ref<NewsItem | null>(null)
const currentCategories = ref<string[]>([])

function getCategoryLabel(cat: string) {
  const labels: Record<string, string> = {
    Market: '市场动态',
    Bid: '中标信息',
    Project: '项目信息',
    Equipment: '设备修造',
    'R&D': '科技研发',
    Regulation: '技术法规'
  }
  return labels[cat] || cat
}

function formatDate(value: string | undefined) {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 16)
}

function buildQuery() {
  const params = new URLSearchParams()
  if (dateRange.value[0] && dateRange.value[1]) {
    params.set('start', dateRange.value[0].format('YYYY-MM-DD'))
    params.set('end', dateRange.value[1].format('YYYY-MM-DD'))
  }
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.category) params.set('category', filters.category)
  if (filters.sourceType) params.set('source_type', filters.sourceType)
  if (filters.sourceName) params.set('source_name', filters.sourceName)
  params.set('page', String(filters.page))
  params.set('page_size', String(filters.pageSize))
  return params.toString()
}

async function fetchArticles() {
  loading.value = true
  try {
    const query = buildQuery()
    const res = await fetch(`/api/articles?${query}`)
    if (!res.ok) {
      console.error('Failed to fetch articles:', res.status, res.statusText)
      articleList.value = []
      total.value = 0
      return
    }
    const data = await res.json()
    articleList.value = data.items || []
    total.value = data.total || 0
  } catch (error) {
    console.error('Failed to fetch articles:', error)
  } finally {
    loading.value = false
  }
}

async function fetchSources() {
  try {
    const res = await fetch('/api/sources')
    if (!res.ok) {
      console.error('Failed to fetch sources:', res.status, res.statusText)
      return
    }
    const data = await res.json()
    sources.value = data.sources || []
  } catch (error) {
    console.error('Failed to fetch sources:', error)
  }
}

function handleSearch() {
  filters.page = 1
  fetchArticles()
}

function changePage(page: number) {
  filters.page = page
  fetchArticles()
}

function resetFilters() {
  filters.keyword = ''
  filters.category = ''
  filters.sourceType = ''
  filters.sourceName = ''
  filters.page = 1
  dateRange.value = [dayjs().subtract(29, 'day'), dayjs()]
  fetchArticles()
}

async function openDetail(item: NewsItem) {
  try {
    const res = await fetch(`/api/article/${item.id}`)
    const data = await res.json()
    currentArticle.value = data.article || item
    const categorySet = new Set<string>()
    ;(data.categories || []).forEach((c: string) => categorySet.add(c))
    if (data.events) {
      data.events.forEach((e: NewsItem) => {
        if (e.category) categorySet.add(e.category)
      })
    }
    currentCategories.value = Array.from(categorySet)
    modalVisible.value = true
  } catch (error) {
    console.error('Failed to fetch article detail:', error)
    currentArticle.value = item
    modalVisible.value = true
  }
}

watch(dateRange, () => {
  handleSearch()
}, { deep: true })

onMounted(async () => {
  await Promise.all([fetchSources(), fetchArticles()])
})
</script>

<style scoped>
:deep(.ant-picker) {
  background: transparent;
  border: none;
}

:deep(.ant-picker-input > input) {
  color: #fff;
}

:deep(.ant-picker-suffix) {
  color: #9ca3af;
}

:deep(.glass-card) {
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

:deep(.ant-select-selector) {
  background: var(--color-dark-card) !important;
  border-color: var(--color-dark-border) !important;
}

:deep(.ant-select-selection-item) {
  color: #e2e8f0;
}

:deep(.ant-input) {
  background: var(--color-dark-card);
  border-color: var(--color-dark-border);
  color: #e2e8f0;
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

:deep(.ant-modal-body) {
  color: #e2e8f0;
}
</style>
