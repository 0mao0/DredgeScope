<template>
  <div class="min-h-screen flex flex-col h-screen overflow-hidden bg-[#0f172a]">
    <!-- Navbar -->
    <NavBar class="flex-shrink-0" />

    <!-- Top Filter Area -->
    <header class="px-4 py-1.5 flex items-center justify-between bg-white/5 border-b border-white/10 flex-shrink-0">
      <div class="flex items-center gap-4">
        <div class="text-[10px] text-gray-500 bg-black/20 px-2 py-0.5 rounded border border-white/5">
          共 {{ total }} 条记录
        </div>
      </div>
      
      <div class="flex items-center gap-2">
        <!-- 搜索 -->
        <a-input-search
          v-model:value="filters.keyword"
          placeholder="搜索标题/摘要..."
          size="small"
          class="w-56 header-filter-input"
          @search="handleSearch"
        />
        
        <!-- 有效/失效筛选 -->
        <a-select 
          v-model:value="filters.valid" 
          placeholder="数据状态"
          size="small"
          class="w-28 header-filter-input"
          @change="handleSearch"
        >
          <a-select-option :value="null">全部状态</a-select-option>
          <a-select-option :value="1">有效数据</a-select-option>
          <a-select-option :value="0">失效数据</a-select-option>
        </a-select>
        
        <!-- 时间维度 -->
        <a-range-picker 
          v-model:value="dateRange" 
          size="small"
          class="w-64 header-filter-input"
          format="YYYY-MM-DD"
          @change="handleSearch"
        />

        <a-button type="primary" size="small" ghost @click="resetFilters" class="border-none hover:bg-white/5">
          <i class="fa-solid fa-rotate-right mr-1"></i> 重置
        </a-button>
      </div>
    </header>

    <main class="flex-1 flex overflow-hidden p-4 gap-4">
      <!-- Zone A: Tree (20%) -->
      <aside class="w-1/5 glass-card rounded-xl flex flex-col overflow-hidden border border-white/10">
        <div class="p-3 border-b border-white/5 bg-white/5 flex items-center justify-between">
          <span class="text-sm font-bold text-gray-300">来源树</span>
          <div 
            class="text-[10px] text-brand-400 bg-brand-500/10 px-1.5 py-0.5 rounded border border-brand-500/20 cursor-pointer hover:bg-brand-500/20 transition-colors flex items-center gap-1"
            @click="isSchedulerModalVisible = true"
          >
            <i class="fa-solid fa-clock-rotate-left text-[9px]"></i>
            {{ latestRunTime }}
          </div>
        </div>
        <div class="flex-1 overflow-y-auto custom-scrollbar p-2">
          <div v-if="loading && articleList.length === 0" class="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
            <a-spin />
            <span class="text-xs">加载中...</span>
          </div>
          <div v-else-if="groupedArticles.length === 0" class="flex items-center justify-center h-full text-gray-500 text-sm">
            暂无数据
          </div>
          <div v-else class="space-y-1">
            <div v-for="group in groupedArticles" :key="group.sourceName" class="space-y-1">
              <!-- Source Name (Level 1) -->
              <div 
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/5 cursor-pointer text-gray-400 group transition-colors"
                @click="toggleGroup(group.sourceName)"
              >
                <i :class="['fa-solid fa-chevron-right text-[10px] transition-transform', expandedGroups.has(group.sourceName) ? 'rotate-90' : '']"></i>
                <i class="fa-solid fa-globe text-xs text-blue-400/70"></i>
                <span class="text-xs font-medium truncate flex-1">{{ group.sourceName || '未知来源' }}</span>
                <span class="text-[10px] bg-slate-800 px-1.5 rounded text-gray-500">{{ group.articles.length }}</span>
              </div>
              
              <!-- Articles (Level 2) -->
              <div v-if="expandedGroups.has(group.sourceName)" class="ml-4 space-y-0.5 border-l border-white/5 pl-1">
                <div 
                  v-for="article in group.articles" 
                  :key="article.id"
                  @click="selectArticle(article)"
                  :class="[
                    'px-2 py-2 rounded text-xs cursor-pointer transition-all flex flex-col gap-1',
                    selectedArticle?.id === article.id ? 'bg-brand-500/20 text-brand-300 border-l-2 border-brand-500' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                  ]"
                >
                  <div class="flex items-center gap-1.5">
                    <span 
                      v-if="article.categories && article.categories.length > 0"
                      :class="['px-1 rounded-[2px] text-[9px] flex-shrink-0 min-w-[48px] text-center', getCategoryMeta(article.categories[0]).bg, getCategoryMeta(article.categories[0]).color]"
                    >
                      {{ getCategoryMeta(article.categories[0]).name }}
                    </span>
                    <span v-else :class="['px-1 rounded-[2px] text-[9px] flex-shrink-0 min-w-[48px] text-center', getCategoryMeta(undefined).bg, getCategoryMeta(undefined).color]">
                      {{ getCategoryMeta(undefined).name }}
                    </span>
                    <span class="truncate font-medium flex-1">{{ article.title_cn || article.title }}</span>
                  </div>
                  <div class="text-[10px] text-gray-500 flex items-center justify-between mt-0.5 px-0.5">
                    <div class="flex items-center gap-1">
                      <i class="fa-regular fa-calendar text-[9px] opacity-40"></i>
                      <span>{{ formatDateShort(article.pub_date) }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <div class="flex items-center gap-1">
                        <i class="fa-regular fa-clock text-[9px] opacity-40"></i>
                        <span class="opacity-60">{{ formatTimeHour(article.created_at) }} 入库</span>
                      </div>
                      <i v-if="article.screenshot_path" class="fa-solid fa-image text-[9px] text-brand-400/50"></i>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Pagination inside Tree -->
            <div class="pt-4 pb-2 px-2 flex items-center justify-between border-t border-white/5 mt-2">
               <button 
                :disabled="filters.page <= 1" 
                @click="changePage(filters.page - 1)"
                class="text-[10px] text-gray-400 hover:text-brand-400 disabled:opacity-30 disabled:hover:text-gray-400"
              >
                <i class="fa-solid fa-chevron-left mr-1"></i>上一页
              </button>
              <span class="text-[10px] text-gray-500">{{ filters.page }} / {{ maxPage }}</span>
              <button 
                :disabled="filters.page >= maxPage" 
                @click="changePage(filters.page + 1)"
                class="text-[10px] text-gray-400 hover:text-brand-400 disabled:opacity-30 disabled:hover:text-gray-400"
              >
                下一页<i class="fa-solid fa-chevron-right ml-1"></i>
              </button>
            </div>
          </div>
        </div>
      </aside>

      <!-- Zone B: Original Content (40%) -->
      <section class="w-2/5 glass-card rounded-xl flex flex-col overflow-hidden border border-white/10">
        <div class="p-2 border-b border-white/5 bg-white/5 flex items-center justify-between">
          <div class="flex bg-black/20 p-1 rounded-lg border border-white/5">
            <button 
              @click="zoneBView = 'text'"
              :class="[
                'px-3 py-1 rounded text-xs font-medium transition-all flex items-center gap-1.5',
                zoneBView === 'text' ? 'bg-brand-500 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'
              ]"
            >
              <i class="fa-solid fa-file-lines text-[10px]"></i> 原文内容
            </button>
            <button 
              @click="zoneBView = 'screenshot'"
              :class="[
                'px-3 py-1 rounded text-xs font-medium transition-all flex items-center gap-1.5',
                zoneBView === 'screenshot' ? 'bg-brand-500 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'
              ]"
            >
              <i class="fa-solid fa-image text-[10px]"></i> 页面截图
            </button>
          </div>
          <a 
            v-if="selectedArticle?.url" 
            :href="selectedArticle.url" 
            target="_blank" 
            class="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1 mr-2"
          >
            <i class="fa-solid fa-external-link-alt"></i> 查看源站
          </a>
        </div>
        
        <div class="flex-1 overflow-y-auto custom-scrollbar p-6 bg-slate-900/30">
          <div v-if="!selectedArticle" class="flex flex-col items-center justify-center h-full text-gray-600 gap-3">
            <i class="fa-solid fa-mouse-pointer text-3xl opacity-20"></i>
            <p class="text-sm">请从左侧选择一篇新闻查看详情</p>
          </div>
          
          <template v-else>
            <div v-if="zoneBView === 'text'" class="prose prose-invert prose-sm max-w-none">
              <h1 class="text-xl font-bold text-white mb-4 leading-tight">{{ selectedArticle.title }}</h1>
              
              <!-- 原文展示 -->
              <div v-if="selectedArticle.content" class="text-gray-300 leading-relaxed whitespace-pre-wrap font-serif text-base">
                {{ selectedArticle.content }}
              </div>
              
              <!-- 兜底展示：如果没有原文但有翻译，提供说明 -->
              <div v-else-if="selectedArticle.full_text_cn" class="flex flex-col items-center justify-center py-20 bg-black/20 rounded-xl border border-white/5 gap-4">
                <i class="fa-solid fa-language text-4xl text-gray-700"></i>
                <div class="text-center px-6">
                  <p class="text-gray-400 text-sm mb-2">未保存原文文本内容</p>
                  <p class="text-[11px] text-gray-500 mb-4">系统已成功抓取并分析该文章（详见右侧分析结果），但未在本地保留原始英文文本。</p>
                  <a :href="selectedArticle.url" target="_blank" class="inline-flex items-center gap-2 px-4 py-2 bg-brand-500/20 text-brand-400 rounded-lg border border-brand-500/30 hover:bg-brand-500/30 transition-colors text-sm">
                    <i class="fa-solid fa-external-link-alt"></i> 直接打开原网页查看原文
                  </a>
                </div>
              </div>

              <!-- 完全没有内容 -->
              <div v-else class="flex flex-col items-center justify-center py-20 bg-black/20 rounded-xl border border-white/5 gap-4">
                <i class="fa-solid fa-file-circle-exclamation text-4xl text-gray-700"></i>
                <div class="text-center px-6">
                  <p class="text-gray-400 text-sm mb-2">正文提取失败</p>
                  <p class="text-[11px] text-gray-500 mb-4">该文章可能由于动态加载、反爬虫限制或证书问题导致无法提取正文。</p>
                  <a :href="selectedArticle.url" target="_blank" class="inline-flex items-center gap-2 px-4 py-2 bg-brand-500/20 text-brand-400 rounded-lg border border-brand-500/30 hover:bg-brand-500/30 transition-colors text-sm">
                    <i class="fa-solid fa-external-link-alt"></i> 尝试在浏览器中打开
                  </a>
                </div>
              </div>
            </div>
            
            <div v-else class="h-full flex items-start justify-center">
              <div v-if="!selectedArticle.screenshot_path" class="flex flex-col items-center justify-center h-full w-full py-20 bg-black/20 rounded-xl border border-white/5 gap-4">
                <i class="fa-solid fa-image-slash text-4xl text-gray-700"></i>
                <div class="text-center">
                  <p class="text-gray-400 text-sm mb-2">该文章采集时未生成截图</p>
                  <p class="text-[10px] text-gray-600 max-w-[200px] mx-auto">截图通常由多模态视觉模型在分析阶段生成，部分文章可能因加载超时跳过截图。</p>
                </div>
              </div>
              <a-image 
                v-else
                :src="selectedArticle.screenshot_path" 
                class="w-full rounded-lg shadow-2xl border border-white/10"
              />
            </div>
          </template>
        </div>
      </section>

      <!-- Zone C: AI Analysis & System Info (40%) -->
      <section class="w-2/5 glass-card rounded-xl flex flex-col overflow-hidden border border-white/10">
        <div class="p-3 border-b border-white/5 bg-white/5 flex items-center justify-between">
          <span class="text-sm font-bold text-gray-300">分析与处理结果</span>
          <div class="flex items-center gap-2">
            <span v-if="selectedArticle" :class="['px-2 py-0.5 rounded-full text-[10px] font-bold border', selectedArticle.valid !== 0 ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20']">
              {{ selectedArticle.valid !== 0 ? '有效' : '失效' }}
            </span>
            <i class="fa-solid fa-robot text-brand-400 text-xs"></i>
          </div>
        </div>
        
        <div class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-6 bg-slate-900/10">
          <div v-if="!selectedArticle" class="flex flex-col items-center justify-center h-full text-gray-600 gap-3">
            <i class="fa-solid fa-chart-pie text-3xl opacity-20"></i>
            <p class="text-sm">选择新闻以查看 AI 处理结果</p>
          </div>
          
          <template v-else>
            <!-- 提示：基于标题的分析 -->
            <div v-if="!selectedArticle.content" class="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 flex items-center gap-2 mb-4">
              <i class="fa-solid fa-circle-info text-amber-400 text-xs"></i>
              <span class="text-[10px] text-amber-300/80">提示：该文章正文提取失败，下方分析结果基于标题及元数据生成。</span>
            </div>

            <!-- Qwen2.5 翻译结果 -->
            <div class="space-y-3">
              <div class="flex items-center gap-2">
                <div class="w-1 h-4 bg-brand-500 rounded-full"></div>
                <h4 class="text-xs font-bold text-gray-400 uppercase tracking-widest">Qwen2.5 智能翻译与摘要</h4>
              </div>
              <div class="bg-white/5 rounded-xl p-4 border border-white/5 space-y-4">
                <div>
                  <h5 class="text-sm font-bold text-brand-300 mb-1.5">{{ selectedArticle.title_cn }}</h5>
                  <p class="text-xs text-gray-400 leading-relaxed italic">摘要：{{ selectedArticle.summary_cn }}</p>
                </div>
                <div class="pt-3 border-t border-white/5">
                  <div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {{ selectedArticle.full_text_cn || '暂无详细翻译内容' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Qwen3-VL 识别内容 -->
            <div class="space-y-3">
              <div class="flex items-center gap-2">
                <div class="w-1 h-4 bg-purple-500 rounded-full"></div>
                <h4 class="text-xs font-bold text-gray-400 uppercase tracking-widest">Qwen3-VL 视觉多模态识别</h4>
              </div>
              <div class="bg-purple-500/5 rounded-xl p-4 border border-purple-500/10">
                <p class="text-sm text-gray-300 leading-relaxed">
                  {{ selectedArticle.vl_desc || '未进行视觉分析或未发现显著视觉特征' }}
                </p>
              </div>
            </div>

            <!-- 系统处理结果 -->
            <div class="space-y-3">
              <div class="flex items-center gap-2">
                <div class="w-1 h-4 bg-blue-500 rounded-full"></div>
                <h4 class="text-xs font-bold text-gray-400 uppercase tracking-widest">系统处理元数据</h4>
              </div>
              <div class="bg-blue-500/5 rounded-xl p-4 border border-blue-500/10 grid grid-cols-2 gap-y-4 gap-x-6">
                <div class="space-y-1">
                  <span class="text-[10px] text-gray-500 block">发布时间</span>
                  <span class="text-xs text-gray-300 font-mono">{{ selectedArticle.pub_date || '未知' }}</span>
                </div>
                <div class="space-y-1">
                  <span class="text-[10px] text-gray-500 block">入库时间</span>
                  <span class="text-xs text-gray-300 font-mono">{{ formatDate(selectedArticle.created_at) }}</span>
                </div>
                <div class="space-y-1">
                  <span class="text-[10px] text-gray-500 block">分类归属</span>
                  <span 
                    v-if="selectedArticle.categories && selectedArticle.categories.length > 0"
                    :class="['inline-flex px-2 py-0.5 rounded text-[10px]', getCategoryMeta(selectedArticle.categories[0]).bg, getCategoryMeta(selectedArticle.categories[0]).color]"
                  >
                    {{ getCategoryMeta(selectedArticle.categories[0]).name }}
                  </span>
                  <span 
                    v-else
                    :class="['inline-flex px-2 py-0.5 rounded text-[10px]', getCategoryMeta(undefined).bg, getCategoryMeta(undefined).color]"
                  >
                    {{ getCategoryMeta(undefined).name }}
                  </span>
                </div>
                <div class="space-y-1">
                  <span class="text-[10px] text-gray-500 block">来源站点</span>
                  <span class="text-xs text-gray-300 truncate block">{{ selectedArticle.source_name }}</span>
                </div>
                <div class="space-y-1 col-span-2">
                  <span class="text-[10px] text-gray-500 block mb-1">关键实体提取</span>
                  <div v-if="selectedArticle.events && selectedArticle.events.length > 0" class="space-y-2">
                    <div v-for="(evt, idx) in selectedArticle.events" :key="idx" class="text-[11px] bg-black/20 p-2 rounded border border-white/5 grid grid-cols-2 gap-1">
                       <div v-if="evt.project_name" class="col-span-2 text-brand-400 font-medium mb-1">{{ evt.project_name }}</div>
                       <div v-if="evt.location"><span class="text-gray-500">位置:</span> {{ evt.location }}</div>
                       <div v-if="evt.contractor"><span class="text-gray-500">承包商:</span> {{ evt.contractor }}</div>
                       <div v-if="evt.client"><span class="text-gray-500">客户:</span> {{ evt.client }}</div>
                       <div v-if="evt.amount"><span class="text-gray-500">金额:</span> {{ evt.amount }} {{ evt.currency }}</div>
                    </div>
                  </div>
                  <div v-else class="text-xs text-gray-600 italic">未提取到关键实体</div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </section>
    </main>

    <!-- Polling Results Modal -->
    <a-modal
      v-model:open="isSchedulerModalVisible"
      title="调度任务执行历史"
      :footer="null"
      width="800px"
      centered
      class="scheduler-modal"
    >
      <div class="flex h-[500px] overflow-hidden">
        <!-- Sidebar: List of runs -->
        <div class="w-1/3 border-r border-white/5 pr-4 overflow-y-auto custom-scrollbar">
          <div 
            v-for="run in schedulerRuns" 
            :key="run.id"
            @click="fetchRunDetail(run.id)"
            :class="[
              'p-2 rounded cursor-pointer mb-1 transition-all text-xs border border-transparent',
              selectedRunId === run.id ? 'bg-brand-500/20 border-brand-500/30 text-brand-300' : 'text-gray-400 hover:bg-white/5'
            ]"
          >
            <div class="flex items-center gap-2">
              <i class="fa-regular fa-calendar-check opacity-60"></i>
              <span>{{ run.timestamp }}</span>
            </div>
          </div>
        </div>
        
        <!-- Content: Markdown preview -->
        <div class="w-2/3 pl-4 overflow-y-auto custom-scrollbar bg-black/10 rounded-lg p-4">
          <div v-if="loadingRun" class="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
            <a-spin />
            <span class="text-[10px]">正在加载详情...</span>
          </div>
          <div v-else-if="selectedRunContent" class="markdown-body">
            <pre class="whitespace-pre-wrap text-[11px] text-gray-400 font-mono leading-relaxed">{{ selectedRunContent }}</pre>
          </div>
          <div v-else class="flex flex-col items-center justify-center h-full text-gray-600 gap-2">
            <i class="fa-solid fa-list-check text-2xl opacity-20"></i>
            <span class="text-xs">请选择左侧日期查看执行详情</span>
          </div>
        </div>
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

// --- 状态定义 ---
const loading = ref(false)
const articleList = ref<NewsItem[]>([])
const total = ref(0)

// 调度任务相关状态
const schedulerRuns = ref<{id: string, timestamp: string, short_ts: string}[]>([])
const isSchedulerModalVisible = ref(false)
const selectedRunContent = ref('')
const selectedRunId = ref('')
const loadingRun = ref(false)

const latestRunTime = computed(() => {
  if (schedulerRuns.value.length > 0) {
    return schedulerRuns.value[0].short_ts
  }
  return '02-27 10:00'
})

const fetchSchedulerRuns = async () => {
  try {
    const res = await fetch('/api/scheduler/runs')
    const data = await res.json()
    schedulerRuns.value = data.runs
  } catch (err) {
    console.error('获取调度历史失败:', err)
  }
}

const fetchRunDetail = async (runId: string) => {
  selectedRunId.value = runId
  loadingRun.value = true
  try {
    const res = await fetch(`/api/scheduler/run/${runId}`)
    const data = await res.json()
    selectedRunContent.value = data.content
  } catch (err) {
    console.error('获取调度详情失败:', err)
  } finally {
    loadingRun.value = false
  }
}
const sources = ref<{ name: string; url?: string }[]>([])
const expandedGroups = ref<Set<string>>(new Set())
const selectedArticle = ref<NewsItem | null>(null)
const zoneBView = ref<'text' | 'screenshot'>('text')

const filters = reactive({
  page: 1,
  pageSize: 50, // 增加单页数量以便于树形展示
  keyword: '',
  category: '',
  sourceType: '',
  sourceName: '',
  valid: 1 as number | null // 默认显示有效
})

const dateRange = ref<[Dayjs, Dayjs]>([
  dayjs().subtract(3, 'month'), // 历史页面默认范围大一点
  dayjs()
])

// --- 分类元数据 ---
const categoriesMeta: Record<string, any> = {
  Market: { name: '市场动态', icon: 'fa-chart-line', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  Bid: { name: '中标信息', icon: 'fa-gavel', color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/20' },
  Project: { name: '项目信息', icon: 'fa-building', color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20' },
  Equipment: { name: '设备修造', icon: 'fa-gears', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  'R&D': { name: '科技研发', icon: 'fa-flask', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  Regulation: { name: '技术法规', icon: 'fa-scale-balanced', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  Other: { name: '其他信息', icon: 'fa-circle-info', color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20' },
  unknown: { name: '其他', icon: 'fa-question', color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20' }
}

function getCategoryMeta(cat: string | undefined) {
  if (!cat) return categoriesMeta.unknown
  // 查找匹配（忽略大小写）
  const found = Object.keys(categoriesMeta).find(k => k.toLowerCase() === cat.toLowerCase())
  return found ? categoriesMeta[found] : categoriesMeta.unknown
}

// --- 数据处理 ---
const groupedArticles = computed(() => {
  const groups: Record<string, NewsItem[]> = {}
  articleList.value.forEach(article => {
    const source = article.source_name || '其他来源'
    if (!groups[source]) groups[source] = []
    groups[source].push(article)
  })
  
  return Object.entries(groups).map(([sourceName, articles]) => ({
    sourceName,
    articles
  })).sort((a, b) => b.articles.length - a.articles.length)
})

const maxPage = computed(() => Math.ceil(total.value / filters.pageSize) || 1)

// --- 方法 ---
function toggleGroup(sourceName: string) {
  if (expandedGroups.value.has(sourceName)) {
    expandedGroups.value.delete(sourceName)
  } else {
    expandedGroups.value.add(sourceName)
  }
}

async function selectArticle(article: NewsItem) {
  if (selectedArticle.value?.id === article.id) return
  
  // 详情字段可能不全，去后端取完整详情和关联事件
  try {
    const res = await fetch(`/api/article/${article.id}`)
    const data = await res.json()
    // 这里的 data 包含 { article: {...}, events: [...] }
    selectedArticle.value = { ...article, ...data.article, events: data.events }
  } catch (e) {
    console.error('获取文章详情失败', e)
    selectedArticle.value = article
  }
}

function formatDate(value: string | undefined) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 16)
}

function formatDateShort(value: string | undefined) {
  if (!value) return '-'
  return dayjs(value).format('MM-DD')
}

function formatTimeHour(value: string | undefined) {
  if (!value) return '-'
  return dayjs(value).format('HH:mm')
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
  if (filters.valid !== null) params.set('valid', String(filters.valid))
  
  params.set('page', String(filters.page))
  params.set('page_size', String(filters.pageSize))
  return params.toString()
}

async function fetchArticles() {
  loading.value = true
  try {
    const query = buildQuery()
    const res = await fetch(`/api/articles?${query}`)
    const data = await res.json()
    articleList.value = data.items || []
    total.value = data.total || 0
    
    // 默认展开第一个来源
    if (groupedArticles.value.length > 0 && expandedGroups.value.size === 0) {
      expandedGroups.value.add(groupedArticles.value[0].sourceName)
    }
    
    // 如果没有选中任何文章，默认选中第一个
    if (!selectedArticle.value && articleList.value.length > 0) {
      selectArticle(articleList.value[0])
    }
  } catch (error) {
    console.error('Failed to fetch articles:', error)
  } finally {
    loading.value = false
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
  filters.valid = 1
  filters.page = 1
  dateRange.value = [dayjs().subtract(3, 'month'), dayjs()]
  fetchArticles()
}

watch(dateRange, () => {
  handleSearch()
})

onMounted(() => {
  fetchArticles()
  fetchSchedulerRuns()
})
</script>

<style scoped>
.glass-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* 紧凑型页头样式 */
:deep(.header-filter-input) {
  &.ant-input-search .ant-input,
  &.ant-picker,
  &.ant-select-selector {
    background: rgba(255, 255, 255, 0.03) !important;
    border: none !important;
    box-shadow: none !important;
    color: #94a3b8 !important; /* text-slate-400 */
    font-size: 11px !important;
  }
  
  &.ant-input-search .ant-input-search-button {
    background: transparent !important;
    border: none !important;
    color: #475569 !important; /* text-slate-600 */
    &:hover {
      color: #38bdf8 !important; /* text-brand-400 */
    }
  }

  /* 调整 placeholder 颜色 */
  &.ant-input-search .ant-input::placeholder,
  &.ant-picker .ant-picker-input > input::placeholder,
  &.ant-select-selection-placeholder {
    color: #475569 !important; /* text-slate-600 */
  }
}

:deep(.ant-input-search .ant-input) {
  background: rgba(15, 23, 42, 0.6);
  border-color: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

:deep(.ant-picker) {
  background: rgba(15, 23, 42, 0.6) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
}

:deep(.ant-picker-input > input) {
  color: #e2e8f0;
}

:deep(.ant-select-selector) {
  background: rgba(15, 23, 42, 0.6) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
  color: #e2e8f0 !important;
}

:deep(.ant-select-selection-item) {
  color: #e2e8f0 !important;
}

:deep(.ant-image) {
  width: 100%;
}
</style>

