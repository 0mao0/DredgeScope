<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Top Filter Area -->
    <header class="mx-4 p-4 flex items-center justify-between glass-card rounded-2xl flex-shrink-0 min-h-[64px]">
      <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 bg-black/20 px-3 py-1.5 rounded-lg border border-white/5 flex items-center">
          共 <span class="text-white font-bold mx-1">{{ total }}</span> 条记录
        </div>
      </div>
      
      <div class="flex items-center gap-3 flex-wrap">
        <!-- 搜索 -->
        <div class="relative w-64">
          <input 
            v-model="filters.keyword" 
            type="text" 
            placeholder="搜索标题/摘要..." 
            class="w-full bg-slate-800/50 border border-white/10 rounded-lg py-1.5 px-3 text-sm focus:outline-none focus:border-blue-500 transition-colors text-white placeholder-gray-500"
            @keyup.enter="handleSearch"
          />
          <i 
            class="fa-solid fa-magnifying-glass absolute right-3 top-2.5 text-gray-500 text-xs cursor-pointer hover:text-blue-400 transition-colors"
            @click="handleSearch"
          ></i>
        </div>
        
        <!-- 有效/失效筛选 -->
        <a-select 
          v-model:value="filters.valid" 
          placeholder="数据状态"
          class="w-32 custom-select"
          @change="handleSearch"
        >
          <a-select-option :value="null">全部有效性</a-select-option>
          <a-select-option :value="1">有效数据</a-select-option>
          <a-select-option :value="0">失效数据</a-select-option>
        </a-select>

        <!-- 保留/全部筛选 -->
        <a-select 
          v-model:value="filters.is_retained" 
          placeholder="保留状态"
          class="w-32 custom-select"
          @change="handleSearch"
        >
          <a-select-option :value="null">全部文章</a-select-option>
          <a-select-option :value="1">保留文章</a-select-option>
          <a-select-option :value="0">未保留文章</a-select-option>
        </a-select>
        
        <!-- 时间维度 -->
        <a-range-picker 
          v-model:value="dateRange" 
          class="w-64 custom-picker"
          format="YYYY-MM-DD"
          @change="handleSearch"
        />

        <button 
          @click="resetFilters" 
          class="h-9 px-4 rounded-lg bg-white/5 border border-white/10 text-sm text-gray-300 hover:bg-white/10 hover:text-white transition-colors flex items-center gap-2"
        >
          <i class="fa-solid fa-rotate-right"></i> 重置
        </button>
      </div>
    </header>

    <main class="flex-1 flex flex-col overflow-hidden px-4 py-4 gap-4">
      <!-- News List Container -->
      <div class="flex-1 flex flex-col overflow-hidden">
        
        <div class="flex-1 overflow-y-auto custom-scrollbar p-2">
            <div v-if="loading" class="flex items-center justify-center h-full">
                <a-spin />
            </div>
            <div v-else-if="articleList.length === 0" class="flex flex-col items-center justify-center h-full text-gray-500">
                <i class="fa-solid fa-inbox text-4xl opacity-20 mb-2"></i>
                <span class="text-sm">暂无数据</span>
            </div>
            <div v-else class="flex flex-col gap-2">
                <div 
                    v-for="article in articleList" 
                    :key="article.id"
                    class="bg-white/5 hover:bg-white/10 border border-white/5 rounded-lg p-3 cursor-pointer transition-colors flex flex-col gap-2 group"
                    @click="openDetail(article)"
                >
                    <!-- Top Row: Title & Valid Status -->
                    <div class="flex justify-between items-start gap-2">
                        <h3 class="text-sm font-medium text-gray-200 group-hover:text-brand-400 transition-colors line-clamp-2 leading-snug">
                            {{ article.title_cn || article.title }}
                        </h3>
                         <span :class="['px-1.5 py-0.5 rounded text-[10px] whitespace-nowrap border', article.valid !== 0 ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20']">
                            {{ article.valid !== 0 ? '有效' : '失效' }}
                        </span>
                    </div>

                    <!-- Middle Row: Summary -->
                    <p class="text-xs text-gray-500 line-clamp-2">
                        {{ article.summary_cn || '暂无摘要' }}
                    </p>

                    <!-- Bottom Row: Meta Info -->
                    <div class="flex items-center justify-between text-[10px] text-gray-500 mt-1">
                        <div class="flex items-center gap-2 flex-wrap">
                            <!-- Category -->
                            <span 
                                :class="['px-1.5 py-0.5 rounded', getCategoryMeta(article.category).bg, getCategoryMeta(article.category).color]"
                            >
                                {{ getCategoryMeta(article.category).name }}
                            </span>

                            <!-- Source -->
                            <span class="text-gray-400 flex items-center gap-1">
                                <i class="fa-solid fa-globe text-[9px]"></i>
                                {{ article.source_name || '未知来源' }}
                            </span>

                            <!-- Date -->
                            <span class="text-gray-400 flex items-center gap-1">
                                <i class="fa-regular fa-clock text-[9px]"></i>
                                {{ formatDateShort(article.pub_date) }}
                            </span>
                        </div>
                        
                        <!-- Actions -->
                        <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                             <a 
                                v-if="article.url" 
                                :href="article.url" 
                                target="_blank" 
                                class="p-1.5 rounded hover:bg-blue-500/20 text-gray-400 hover:text-blue-400 transition-colors"
                                title="查看源网页"
                                @click.stop
                            >
                                <i class="fa-solid fa-external-link-alt"></i>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Pagination -->
        <div class="p-3 border-t border-white/5 flex items-center justify-between bg-white/5">
           <button 
            :disabled="filters.page <= 1" 
            @click="changePage(filters.page - 1)"
            class="px-3 py-1.5 rounded bg-white/5 hover:bg-white/10 text-xs text-gray-300 disabled:opacity-30 disabled:hover:bg-white/5 transition-colors flex items-center gap-1"
          >
            <i class="fa-solid fa-chevron-left"></i> 上一页
          </button>
          <span class="text-xs text-gray-400">第 <span class="text-white font-mono">{{ filters.page }}</span> / {{ maxPage }} 页</span>
          <button 
            :disabled="filters.page >= maxPage" 
            @click="changePage(filters.page + 1)"
            class="px-3 py-1.5 rounded bg-white/5 hover:bg-white/10 text-xs text-gray-300 disabled:opacity-30 disabled:hover:bg-white/5 transition-colors flex items-center gap-1"
          >
            下一页 <i class="fa-solid fa-chevron-right"></i>
          </button>
        </div>
      </div>
    </main>

    <!-- Detail Modal (Synced with Dashboard.vue) -->
    <a-modal
      v-model:open="detailVisible"
      :title="currentArticle?.title_cn || currentArticle?.title"
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
        <a :href="currentArticle?.url || '#'" target="_blank" class="inline-flex h-9 justify-center rounded-lg bg-brand-600 px-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-500 transition-colors items-center gap-2">
          <i class="fa-solid fa-external-link-alt"></i> 原文链接
        </a>
        <a-button @click="detailVisible = false" class="h-9">
          <i class="fa-solid fa-xmark mr-1"></i> 关闭
        </a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { NewsItem } from '@/stores'
import axios from 'axios'

// --- 状态定义 ---
const loading = ref(false)
const articleList = ref<NewsItem[]>([])
const total = ref(0)
const filters = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  date: null as string | null,
  valid: 1, // 默认只看有效
  is_retained: 1, // 默认只看保留
  category: null as string | null,
  start: '',
  end: ''
})

const dateRange = ref<[Dayjs, Dayjs]>()

// 详情弹框
const detailVisible = ref(false)
const currentArticle = ref<NewsItem | null>(null)

// --- 计算属性 ---
const maxPage = computed(() => Math.ceil(total.value / filters.page_size))

const openDetail = (article: NewsItem) => {
  currentArticle.value = article
  detailVisible.value = true
  // 强制滚动到顶部
  setTimeout(() => {
    const modalBody = document.querySelector('.detail-modal .ant-modal-body > div')
    if (modalBody) {
      modalBody.scrollTop = 0
    }
    // 兼容 dashboard 样式的类名
    const customScroll = document.querySelector('.detail-modal .custom-scrollbar')
    if (customScroll) {
        customScroll.scrollTop = 0
    }
  }, 100)
}


// --- 辅助函数 ---
const formatDateShort = (dateStr: string | undefined) => {
  if (!dateStr) return '-'
  return dayjs(dateStr).format('YYYY-MM-DD')
}

const categories = {
  Market: { name: '市场动态', icon: 'fa-chart-line', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  Bid: { name: '中标信息', icon: 'fa-gavel', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  Project: { name: '项目信息', icon: 'fa-building', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20' },
  Equipment: { name: '设备修造', icon: 'fa-gears', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  'R&D': { name: '科技研发', icon: 'fa-flask', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  Regulation: { name: '技术法规', icon: 'fa-scale-balanced', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  Other: { name: '其他信息', icon: 'fa-circle-info', color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20' }
}

const getCategoryMeta = (category: string | undefined) => {
  const cat = category || 'Other'
  // @ts-ignore
  return categories[cat] || categories.Other
}

// --- API 调用 ---
const fetchArticles = async () => {
  loading.value = true
  try {
    const params: any = {
      page: filters.page,
      page_size: filters.page_size,
      keyword: filters.keyword,
      start: filters.start,
      end: filters.end
    }

    // 如果 valid 不为 null (全部)，则传递 valid 参数
    if (filters.valid !== null) {
      params.valid = filters.valid
    }

    // 如果 is_retained 不为 null (全部)，则传递 is_retained 参数
    if (filters.is_retained !== null) {
      params.is_retained = filters.is_retained
    }

    const res = await axios.get('/api/articles', { params })
    articleList.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// --- 事件处理 ---
const handleSearch = () => {
  filters.page = 1
  if (dateRange.value) {
    filters.start = dateRange.value[0].format('YYYY-MM-DD')
    filters.end = dateRange.value[1].format('YYYY-MM-DD')
  } else {
    filters.start = ''
    filters.end = ''
  }
  fetchArticles()
}

const changePage = (page: number) => {
  filters.page = page
  fetchArticles()
}

const resetFilters = () => {
  filters.keyword = ''
  filters.valid = 1
  filters.is_retained = 1
  filters.start = ''
  filters.end = ''
  dateRange.value = undefined
  filters.page = 1
  fetchArticles()
}

// --- 生命周期 ---
onMounted(() => {
  fetchArticles()
})
</script>

<style scoped>
.glass-card {
  background: rgba(17, 24, 39, 0.7);
  backdrop-filter: blur(20px);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* Custom Ant Design Overrides for dark theme consistency */
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
  border-bottom: none !important;
}

:deep(.ant-modal-close-x) {
  color: #9ca3af !important;
}

:deep(.ant-modal-body) {
  color: #e2e8f0;
}

:deep(.ant-select-selector),
:deep(.ant-picker) {
  background-color: rgba(30, 41, 59, 0.5) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
  color: #e2e8f0 !important;
  border-radius: 0.5rem !important;
  padding-top: 4px !important;
  padding-bottom: 4px !important;
  height: 38px !important;
}

:deep(.ant-select-arrow),
:deep(.ant-picker-suffix) {
  color: #94a3b8 !important;
}

:deep(.ant-picker-input > input) {
  color: #e2e8f0 !important;
  font-size: 0.875rem !important;
}
</style>
