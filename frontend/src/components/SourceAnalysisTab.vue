<template>
  <div class="space-y-6">
    <!-- 数据概览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="glass-card p-4 rounded-xl">
        <div class="text-gray-400 text-sm">数据源总数</div>
        <div class="text-2xl font-bold mt-1">{{ summary.totalSources }}</div>
      </div>
      <div class="glass-card p-4 rounded-xl">
        <div class="text-gray-400 text-sm">有效新闻</div>
        <div class="text-2xl font-bold mt-1 text-green-400">{{ summary.validArticles }}</div>
      </div>
      <div class="glass-card p-4 rounded-xl">
        <div class="text-gray-400 text-sm">平均采集成功率</div>
        <div class="text-2xl font-bold mt-1">{{ summary.avgSuccessRate }}%</div>
      </div>
      <div class="glass-card p-4 rounded-xl">
        <div class="text-gray-400 text-sm">今日新增</div>
        <div class="text-2xl font-bold mt-1 text-blue-400">{{ summary.todayNew }}</div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="glass-card p-5 rounded-2xl">
        <h3 class="text-lg font-semibold mb-4 flex items-center justify-between">
          <span>数据源贡献</span>
          <span class="text-sm font-normal text-green-400">有效新闻共 {{ summary.validArticles }} 篇</span>
        </h3>
        <div class="chart-container">
          <canvas ref="sourceBarChart"></canvas>
        </div>
      </div>
      <div class="glass-card p-5 rounded-2xl">
        <h3 class="text-lg font-semibold mb-4">情报分类占比</h3>
        <div class="chart-container">
          <canvas ref="categoryPieChart"></canvas>
        </div>
      </div>
    </div>

    <!-- 采集健康度表格 -->
    <div class="glass-card p-5 rounded-2xl">
      <h3 class="text-lg font-semibold mb-4">采集源健康度</h3>
      <a-table
        :columns="healthColumns"
        :data-source="healthData"
        :pagination="false"
        size="small"
        class="custom-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'sourceType'">
            <a-tag :color="record.source_type === 'rss' ? 'blue' : record.source_type === 'web' ? 'purple' : 'cyan'">
              {{ record.source_type }}
            </a-tag>
          </template>
          <template v-if="column.key === 'successRate'">
            <a-progress
              :percent="record.successRate"
              :stroke-color="record.successRate >= 90 ? '#52c41a' : '#ff4d4f'"
              size="small"
            />
          </template>
          <template v-if="column.key === 'avgResponse'">
            <span v-if="record.avg_response_time">{{ (record.avg_response_time / 1000).toFixed(1) }}s</span>
            <span v-else class="text-gray-500">-</span>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const sourceBarChart = ref<HTMLCanvasElement | null>(null)
const categoryPieChart = ref<HTMLCanvasElement | null>(null)

let sourceBarInstance: Chart | null = null
let categoryPieInstance: Chart | null = null

const summary = ref({ totalSources: 0, validArticles: 0, avgSuccessRate: 0, todayNew: 0 })
const healthData = ref<any[]>([])
const healthColumns = [
  { title: '数据源', dataIndex: 'source_name', key: 'source_name' },
  { title: '类型', dataIndex: 'source_type', key: 'sourceType', width: 90 },
  { title: '采集次数', dataIndex: 'total_fetches', key: 'total_fetches', width: 100 },
  { title: '成功率', key: 'successRate', width: 180 },
  { title: '平均响应', key: 'avgResponse', width: 100 },
]

const chartColors = [
  '#0ea5e9', '#22c55e', '#eab308', '#f97316', '#ec4899', '#8b5cf6',
  '#6366f1', '#14b8a6', '#f43f5e', '#a855f7',
]

const fetchData = async () => {
  try {
    const [statsRes, healthRes] = await Promise.all([
      fetch('/api/statistics'),
      fetch('/api/source-health?days=30'),
    ])
    const statsData = await statsRes.json()
    const healthResult = await healthRes.json()

    // 有效新闻 = 全库有效文章数（不受时间范围影响）
    const validArticles = healthResult.total_valid ?? 0

    const sourceStats = healthResult.source_stats || []
    const totalFetch = sourceStats.reduce((s: number, x: any) => s + (x.total_fetches || 0), 0)
    const totalSuccess = sourceStats.reduce((s: number, x: any) => s + (x.success_count || 0), 0)
    const avgSuccessRate = totalFetch > 0 ? Math.round((totalSuccess / totalFetch) * 100) : 0

    const dailyStats = healthResult.daily_stats || []
    const todayNew = dailyStats.length > 0 ? dailyStats[dailyStats.length - 1].new_items || 0 : 0

    summary.value = { totalSources: sourceStats.length, validArticles, avgSuccessRate, todayNew }
    healthData.value = sourceStats
      .map((s: any) => ({
        ...s,
        successRate: s.total_fetches > 0 ? Math.round((s.success_count / s.total_fetches) * 100) : 0,
      }))
      .sort((a: any, b: any) => b.successRate - a.successRate)

    renderCharts(statsData)
  } catch (error) {
    console.error('Failed to fetch statistics:', error)
  }
}

const renderCharts = (data: any) => {
  if (sourceBarChart.value) {
    sourceBarInstance?.destroy()
    sourceBarInstance = new Chart(sourceBarChart.value, {
      type: 'bar',
      data: {
        labels: data.source_stats?.labels?.slice(0, 10) || [],
        datasets: [
          {
            label: '有效',
            data: data.source_stats?.valid_values?.slice(0, 10) || [],
            backgroundColor: 'rgba(34, 197, 94, 0.85)',
            borderColor: 'rgba(34, 197, 94, 1)',
            borderWidth: 1,
          },
          {
            label: '无效',
            data: data.source_stats?.invalid_values?.slice(0, 10) || [],
            backgroundColor: 'rgba(239, 68, 68, 0.55)',
            borderColor: 'rgba(239, 68, 68, 1)',
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#cbd5e1' } } },
        scales: {
          y: { beginAtZero: true, stacked: true, grid: { color: 'rgba(255,255,255,0.1)' } },
          x: { stacked: true, grid: { display: false } },
        },
      },
    })
  }

  if (categoryPieChart.value) {
    categoryPieInstance?.destroy()
    // 用全库有效文章分类分布（不受时间范围影响）
    const pieData = data.category_stats_all || data.category_stats
    categoryPieInstance = new Chart(categoryPieChart.value, {
      type: 'doughnut',
      data: {
        labels: pieData?.labels || [],
        datasets: [{ data: pieData?.values || [], backgroundColor: chartColors }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '58%',
        plugins: {
          legend: { display: false },
        },
      },
      plugins: [doughnutValuePlugin],
    })
  }
}

// 饼图数字插件：外圈显示 "类型 数量(百分比)"，中心只显示总计
const doughnutValuePlugin = {
  id: 'doughnutValue',
  afterDatasetsDraw(chart: any) {
    const { ctx } = chart
    const meta = chart.getDatasetMeta(0)
    if (!meta.data.length) return
    const values: number[] = chart.data.datasets[0].data || []
    const labels: string[] = chart.data.labels || []
    const total = values.reduce((s: number, v: number) => s + v, 0)
    if (total <= 0) return

    // 扇区数字绘制在外圈：类型 + 数量(百分比)
    ctx.save()
    ctx.font = '10px sans-serif'
    ctx.textBaseline = 'middle'
    meta.data.forEach((arc: any, i: number) => {
      const pct = Math.round((values[i] / total) * 100)
      const midAngle = (arc.startAngle + arc.endAngle) / 2
      const x = arc.x + Math.cos(midAngle) * (arc.outerRadius + 12)
      const y = arc.y + Math.sin(midAngle) * (arc.outerRadius + 8)
      ctx.textAlign = Math.cos(midAngle) >= 0 ? 'left' : 'right'
      ctx.fillStyle = '#e2e8f0'
      ctx.fillText(`${labels[i] || ''} ${values[i]} (${pct}%)`, x, y)
    })

    // 中心只显示总计
    const cx = chart.chartArea.left + chart.chartArea.width / 2
    const cy = chart.chartArea.top + chart.chartArea.height / 2
    const totalStr = String(total)
    ctx.font = 'bold 16px sans-serif'
    ctx.fillStyle = '#e2e8f0'
    ctx.fillText(totalStr, cx, cy)
    ctx.font = '10px sans-serif'
    ctx.fillStyle = '#94a3b8'
    ctx.fillText('篇', cx + ctx.measureText(totalStr).width / 2 + 4, cy - 3)
    ctx.restore()
  },
}

onMounted(() => {
  fetchData()
})
onUnmounted(() => {
  sourceBarInstance?.destroy()
  categoryPieInstance?.destroy()
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

.chart-container {
  position: relative;
  height: 300px;
  width: 100%;
}
</style>
