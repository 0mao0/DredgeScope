<template>
  <div class="h-full overflow-y-auto custom-scrollbar">
    <main class="w-full px-4 sm:px-6 lg:px-8 space-y-6 pb-6">
      <!-- Filter Bar -->
      <div class="glass-card rounded-2xl p-5">
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-2">
            <label class="text-xs text-gray-400">时间范围</label>
            <a-range-picker 
              v-model:value="dateRange" 
              class="bg-dark-card border border-dark-border"
              format="YYYY-MM-DD"
              @change="loadStats"
            />
          </div>
          <div class="flex gap-2">
            <a-button @click="resetFilter">重置</a-button>
          </div>
        </div>
      </div>

      <!-- Charts Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Pie Chart: Categories -->
        <div class="glass-card rounded-2xl p-6">
          <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <i class="fa-solid fa-chart-pie text-brand-400"></i> 六大类情报占比
          </h3>
          <div class="chart-container">
            <canvas ref="categoryPieChartRef"></canvas>
          </div>
        </div>

        <!-- Line Chart: Trend -->
        <div class="glass-card rounded-2xl p-6">
          <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <i class="fa-solid fa-chart-line text-green-400"></i> 情报数量趋势
          </h3>
          <div class="chart-container">
            <canvas ref="trendLineChartRef"></canvas>
          </div>
        </div>

        <!-- Bar Chart: Sources Ladder -->
        <div class="lg:col-span-2 glass-card rounded-2xl p-6">
          <h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <i class="fa-solid fa-ranking-star text-yellow-400"></i> 数据源有效新闻天梯图
          </h3>
          <div class="chart-container-lg">
            <canvas ref="sourceBarChartRef"></canvas>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Chart, registerables } from 'chart.js'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'

Chart.register(...registerables)

const dateRange = ref<[Dayjs, Dayjs]>([
  dayjs().subtract(30, 'day'),
  dayjs()
])

const categoryPieChartRef = ref<HTMLCanvasElement | null>(null)
const trendLineChartRef = ref<HTMLCanvasElement | null>(null)
const sourceBarChartRef = ref<HTMLCanvasElement | null>(null)

let categoryPieChart: Chart | null = null
let trendLineChart: Chart | null = null
let sourceBarChart: Chart | null = null

const chartColors = [
  '#0ea5e9', '#22c55e', '#eab308', '#f97316', '#ec4899', '#8b5cf6', 
  '#6366f1', '#14b8a6', '#f43f5e', '#a855f7'
]

async function loadStats() {
  const start = dateRange.value[0].format('YYYY-MM-DD')
  const end = dateRange.value[1].format('YYYY-MM-DD')
  
  try {
    const response = await fetch(`/api/statistics?start=${start}&end=${end}`)
    if (!response.ok) {
      console.error('Failed to load stats:', response.status, response.statusText)
      return
    }
    const data = await response.json()
    
    renderPieChart(data.category_stats)
    renderLineChart(data.trend_stats)
    renderBarChart(data.source_stats)
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

function renderPieChart(data: { labels: string[]; values: number[] }) {
  if (!categoryPieChartRef.value) return
  
  if (categoryPieChart) categoryPieChart.destroy()
  
  categoryPieChart = new Chart(categoryPieChartRef.value, {
    type: 'pie',
    data: {
      labels: data.labels || [],
      datasets: [{
        data: data.values || [],
        backgroundColor: chartColors,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#cbd5e1' }
        }
      }
    }
  })
}

function renderLineChart(data: any) {
  if (!trendLineChartRef.value) return
  
  if (trendLineChart) trendLineChart.destroy()
  
  const categories = Array.isArray(data.categories) ? data.categories : []
  const dates = Array.isArray(data.dates) ? data.dates : []
  let datasets: any[] = []
  
  if (Array.isArray(data.datasets) && data.datasets.length > 0) {
    datasets = data.datasets.map((dataset: any, index: number) => ({
      label: dataset.label || categories[index] || `系列${index + 1}`,
      data: Array.isArray(dataset.data) ? dataset.data : dates.map(() => 0),
      borderColor: chartColors[index % chartColors.length],
      tension: 0.4,
      fill: false
    }))
  } else if (data.values) {
    datasets = categories.map((cat: string, index: number) => ({
      label: cat,
      data: dates.map((date: string) => (data.values[cat] && data.values[cat][date]) ? data.values[cat][date] : 0),
      borderColor: chartColors[index % chartColors.length],
      tension: 0.4,
      fill: false
    }))
  } else {
    datasets = categories.map((cat: string, index: number) => ({
      label: cat,
      data: dates.map(() => 0),
      borderColor: chartColors[index % chartColors.length],
      tension: 0.4,
      fill: false
    }))
  }

  trendLineChart = new Chart(trendLineChartRef.value, {
    type: 'line',
    data: {
      labels: dates,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1' }
        }
      },
      scales: {
        x: {
          ticks: { color: '#94a3b8' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        },
        y: {
          ticks: { color: '#94a3b8' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        }
      }
    }
  })
}

function renderBarChart(data: { labels: string[]; values: number[] }) {
  if (!sourceBarChartRef.value) return
  
  if (sourceBarChart) sourceBarChart.destroy()
  
  sourceBarChart = new Chart(sourceBarChartRef.value, {
    type: 'bar',
    data: {
      labels: data.labels || [],
      datasets: [{
        label: '有效新闻数',
        data: data.values || [],
        backgroundColor: chartColors,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        x: {
          ticks: { color: '#94a3b8' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        },
        y: {
          ticks: { color: '#94a3b8' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        }
      }
    }
  })
}

function resetFilter() {
  dateRange.value = [dayjs().subtract(30, 'day'), dayjs()]
  loadStats()
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.glass-card {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.chart-container {
  position: relative;
  height: 300px;
  width: 100%;
}

.chart-container-lg {
  position: relative;
  height: 400px;
  width: 100%;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Custom Ant Design Overrides for dark theme consistency */
:deep(.ant-picker) {
  background-color: rgba(30, 41, 59, 0.5) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
  color: #e2e8f0 !important;
  border-radius: 0.5rem !important;
  padding-top: 4px !important;
  padding-bottom: 4px !important;
  height: 38px !important;
}

:deep(.ant-picker-input > input) {
  color: #e2e8f0 !important;
  font-size: 0.875rem !important;
}

:deep(.ant-picker-suffix) {
  color: #94a3b8 !important;
}
</style>
