<template>
  <div class="space-y-6">
    <!-- 第1行：整体洞察 -->
    <div class="glass-card p-5 rounded-2xl border-l-4 relative overflow-hidden" :style="{ borderLeftColor: '#8b5cf6' }">
      <div class="ai-glow"></div>
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-1/3">
          <h3 class="text-lg font-semibold mb-2 flex items-center gap-2">
            <span class="text-purple-400">AI</span> 整体洞察
          </h3>
          <span class="text-xs text-gray-500" v-if="aiGeneratedAt">生成于 {{ aiGeneratedAt }}</span>
          <ul class="mt-3 space-y-2">
            <li
              v-for="(line, i) in splitLines(aiReport.summary)"
              :key="i"
              class="text-gray-300 leading-relaxed pl-3 border-l-2 border-purple-400/40"
            >
              {{ line }}
            </li>
            <li v-if="!aiReport.summary" class="text-gray-500">AI报告生成中，请稍后刷新...</li>
          </ul>
        </div>
        <div class="lg:w-2/3">
          <h4 class="text-sm font-semibold text-gray-400 mb-2">月度项目数趋势</h4>
          <div class="chart-container-sm">
            <canvas ref="projectTrendChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 第2行：产业规模 -->
    <div class="glass-card p-5 rounded-2xl">
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-1/3">
          <h3 class="text-lg font-semibold mb-3">产业规模趋势</h3>
          <ul class="space-y-2">
            <li
              v-for="(line, i) in splitLines(aiReport.scale_trend)"
              :key="i"
              class="text-gray-300 leading-relaxed pl-3 border-l-2 border-sky-400/40"
            >
              {{ line }}
            </li>
            <li v-if="!aiReport.scale_trend" class="text-gray-500">暂无分析</li>
          </ul>
        </div>
        <div class="lg:w-2/3">
          <div class="chart-container-sm">
            <canvas ref="scaleTrendChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 第3行：研发趋势 -->
    <div class="glass-card p-5 rounded-2xl">
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-1/3">
          <h3 class="text-lg font-semibold mb-3">研发/技术趋势</h3>
          <ul class="space-y-2">
            <li
              v-for="(line, i) in splitLines(aiReport.rd_trend)"
              :key="i"
              class="text-gray-300 leading-relaxed pl-3 border-l-2 border-emerald-400/40"
            >
              {{ line }}
            </li>
            <li v-if="!aiReport.rd_trend" class="text-gray-500">暂无分析</li>
          </ul>
        </div>
        <div class="lg:w-2/3">
          <div class="chart-container-sm">
            <canvas ref="techTrendChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 第4行：船型结构 -->
    <div class="glass-card p-5 rounded-2xl">
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-1/3">
          <h3 class="text-lg font-semibold mb-3">船型结构</h3>
          <ul class="space-y-2">
            <li
              v-for="(line, i) in splitLines(aiReport.ship_trend)"
              :key="i"
              class="text-gray-300 leading-relaxed pl-3 border-l-2 border-amber-400/40"
            >
              {{ line }}
            </li>
            <li v-if="!aiReport.ship_trend" class="text-gray-500">暂无分析</li>
          </ul>
        </div>
        <div class="lg:w-2/3">
          <div class="chart-container-sm">
            <canvas ref="shipTypeChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 第5行：船型体量 -->
    <div class="glass-card p-5 rounded-2xl">
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-1/3">
          <h3 class="text-lg font-semibold mb-3">船型体量</h3>
          <ul class="space-y-2">
            <li
              v-for="(line, i) in splitLines(aiReport.volume_trend)"
              :key="i"
              class="text-gray-300 leading-relaxed pl-3 border-l-2 border-rose-400/40"
            >
              {{ line }}
            </li>
            <li v-if="!aiReport.volume_trend" class="text-gray-500">暂无分析</li>
          </ul>
        </div>
        <div class="lg:w-2/3">
          <div class="chart-container-sm">
            <canvas ref="volumeTrendChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 第6行：关键洞察 + 船型详情表 -->
    <div class="glass-card p-5 rounded-2xl">
      <div class="flex flex-col lg:flex-row gap-6">
        <div class="lg:w-1/3">
          <h3 class="text-lg font-semibold mb-2">关键洞察</h3>
          <div class="flex flex-wrap gap-2" v-if="aiReport.insights?.length">
            <a-tag v-for="(insight, i) in aiReport.insights" :key="i" color="purple" class="py-1 px-2 mb-1">
              {{ insight }}
            </a-tag>
          </div>
          <p v-else class="text-gray-500 text-sm">暂无洞察</p>
        </div>
        <div class="lg:w-2/3">
          <h4 class="text-sm font-semibold text-gray-400 mb-2">船型详细分析（点击行查看项目）</h4>
          <a-table
            :columns="shipColumns"
            :data-source="shipTypeData"
            :pagination="false"
            size="small"
            class="custom-table"
            row-key="ship_type"
          >
            <template #expandedRowRender="{ record }">
              <div class="p-4 bg-black/20 rounded-lg">
                <h4 class="font-semibold mb-2">使用公司</h4>
                <div class="flex flex-wrap gap-2 mb-4">
                  <a-tag v-for="company in record.companies" :key="company" color="blue">{{ company }}</a-tag>
                  <span v-if="!record.companies?.length" class="text-gray-500 text-sm">暂无</span>
                </div>
                <h4 class="font-semibold mb-2">相关项目</h4>
                <ul class="list-disc list-inside text-sm text-gray-300">
                  <li v-for="(project, idx) in record.projects?.slice(0, 5)" :key="idx">{{ project }}</li>
                  <span v-if="!record.projects?.length" class="text-gray-500">暂无</span>
                </ul>
              </div>
            </template>
          </a-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const projectTrendChart = ref<HTMLCanvasElement | null>(null)
const scaleTrendChart = ref<HTMLCanvasElement | null>(null)
const techTrendChart = ref<HTMLCanvasElement | null>(null)
const shipTypeChart = ref<HTMLCanvasElement | null>(null)
const volumeTrendChart = ref<HTMLCanvasElement | null>(null)

let projectInstance: Chart | null = null
let scaleInstance: Chart | null = null
let techInstance: Chart | null = null
let shipInstance: Chart | null = null
let volumeInstance: Chart | null = null

const summary = ref({ totalProjects: 0, totalAmount: 0, totalVolume: 0 })
const shipTypeData = ref<any[]>([])
const aiReport = ref<any>({})
const aiGeneratedAt = ref('')

// AI文字按句拆分为逐行列表，提升可读性
const splitLines = (text: string | undefined): string[] => {
  if (!text) return []
  return text
    .split(/(?<=[。！？；!?;])|(?<=\.)\s+/)
    .map((s: string) => s.trim())
    .filter((s: string) => s.length > 0)
}

const shipColumns = [
  { title: '船型', dataIndex: 'ship_type', key: 'ship_type' },
  { title: '出现次数', dataIndex: 'count', key: 'count' },
  { title: '涉及公司数', dataIndex: 'companyCount', key: 'companyCount' },
]

const fetchData = async () => {
  try {
    const res = await fetch('/api/industry-trends')
    const data = await res.json()

    const trends = data.trends || []
    summary.value = {
      totalProjects: trends.reduce((sum: number, t: any) => sum + t.total_projects, 0),
      totalAmount: trends.reduce((sum: number, t: any) => sum + t.total_amount, 0),
      totalVolume: trends.reduce((sum: number, t: any) => sum + t.total_volume, 0),
    }

    shipTypeData.value = Object.entries(data.ship_types || {}).map(([type, info]: [string, any]) => ({
      ship_type: type,
      count: info.count,
      companies: info.companies,
      projects: info.projects,
      companyCount: info.companies?.length || 0,
    }))

    if (data.ai_report?.summary) {
      aiReport.value = data.ai_report
      aiGeneratedAt.value = data.ai_report.generated_at?.replace('T', ' ').slice(0, 16) || ''
    }

    renderCharts(data)
  } catch (error) {
    console.error('Failed to fetch industry trends:', error)
  }
}

const renderCharts = (data: any) => {
  const trends = data.trends || []
  const periods = trends.map((t: any) => t.period)

  // 月度项目数趋势
  if (projectTrendChart.value) {
    projectInstance?.destroy()
    projectInstance = new Chart(projectTrendChart.value, {
      type: 'bar',
      data: {
        labels: periods,
        datasets: [{
          label: '项目数',
          data: trends.map((t: any) => t.total_projects),
          backgroundColor: 'rgba(139, 92, 246, 0.8)',
          borderColor: 'rgba(139, 92, 246, 1)',
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
          x: { grid: { display: false } },
        },
      },
    })
  }

  // 项目规模趋势（堆叠）
  if (scaleTrendChart.value) {
    scaleInstance?.destroy()
    scaleInstance = new Chart(scaleTrendChart.value, {
      type: 'bar',
      data: {
        labels: periods,
        datasets: [
          { label: '大型项目', data: trends.map((t: any) => t.scale_trend?.['大型项目'] || 0), backgroundColor: 'rgba(239, 68, 68, 0.8)' },
          { label: '中型项目', data: trends.map((t: any) => t.scale_trend?.['中型项目'] || 0), backgroundColor: 'rgba(245, 158, 11, 0.8)' },
          { label: '小型项目', data: trends.map((t: any) => t.scale_trend?.['小型项目'] || 0), backgroundColor: 'rgba(34, 197, 94, 0.8)' },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#cbd5e1' } } },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
        },
      },
    })
  }

  // 技术趋势
  if (techTrendChart.value) {
    techInstance?.destroy()
    const entries = Object.entries(data.tech_trends || {})
    techInstance = new Chart(techTrendChart.value, {
      type: 'bar',
      data: {
        labels: entries.map(([tech]) => tech),
        datasets: [{
          label: '提及次数',
          data: entries.map(([, count]) => count as number),
          backgroundColor: 'rgba(139, 92, 246, 0.8)',
          borderColor: 'rgba(139, 92, 246, 1)',
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
          x: { grid: { display: false } },
        },
      },
    })
  }

  // 船型分布
  if (shipTypeChart.value) {
    shipInstance?.destroy()
    const entries = Object.entries(data.ship_types || {})
    shipInstance = new Chart(shipTypeChart.value, {
      type: 'doughnut',
      data: {
        labels: entries.map(([type]) => type),
        datasets: [{
          data: entries.map(([, info]: [string, any]) => info.count),
          backgroundColor: ['#0ea5e9', '#22c55e', '#eab308', '#f97316', '#ec4899', '#8b5cf6', '#14b8a6'],
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '55%',
        plugins: { legend: { position: 'right', labels: { color: '#cbd5e1' } } },
      },
    })
  }

  // 船型体量分布（堆叠柱状图）
  if (volumeTrendChart.value) {
    volumeInstance?.destroy()
    const levels = ['小型(<5000m³)', '中型(5000-15000m³)', '大型(>15000m³)']
    volumeInstance = new Chart(volumeTrendChart.value, {
      type: 'bar',
      data: {
        labels: periods,
        datasets: levels.map((level, i) => ({
          label: level,
          data: trends.map((t: any) => t.volume_class_trend?.[level] || 0),
          backgroundColor: ['rgba(34, 197, 94, 0.8)', 'rgba(245, 158, 11, 0.8)', 'rgba(239, 68, 68, 0.8)'][i],
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#cbd5e1' } } },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
        },
      },
    })
  }
}

onMounted(() => {
  fetchData()
  window.addEventListener('refresh-statistics', fetchData)
})
onUnmounted(() => {
  window.removeEventListener('refresh-statistics', fetchData)
  projectInstance?.destroy()
  scaleInstance?.destroy()
  techInstance?.destroy()
  shipInstance?.destroy()
  volumeInstance?.destroy()
})
</script>

<style scoped>
.glass-card {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.custom-table :deep(.ant-table) { background: transparent; }
.custom-table :deep(.ant-table-thead > tr > th) { background: rgba(255, 255, 255, 0.05); }
.custom-table :deep(.ant-table-tbody > tr:hover > td) { background: rgba(255, 255, 255, 0.05); }

.chart-container-sm {
  position: relative;
  height: 220px;
  width: 100%;
}

/* AI 标签 */
.ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: #e9d5ff;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(99, 102, 241, 0.25));
  border: 1px solid rgba(139, 92, 246, 0.5);
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.25);
}
.ai-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #a78bfa;
  box-shadow: 0 0 6px #a78bfa;
  animation: ai-pulse 1.8s ease-in-out infinite;
}
@keyframes ai-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.75); }
}

/* AI 光晕背景 */
.ai-glow {
  position: absolute;
  top: -60px;
  right: -60px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.18) 0%, transparent 70%);
  pointer-events: none;
}
</style>
