<template>
  <div class="space-y-6">
    <!-- 公司项目数分组柱状图 -->
    <div class="glass-card p-5 rounded-2xl">
      <h3 class="text-lg font-semibold mb-4">公司新签 vs 在建项目数</h3>
      <div class="chart-container">
        <canvas ref="companyBarChart"></canvas>
      </div>
    </div>

    <!-- 公司详情表格 -->
    <div class="glass-card p-5 rounded-2xl">
      <h3 class="text-lg font-semibold mb-4">公司运营详情</h3>
      <a-table
        :columns="columns"
        :data-source="companyData"
        :pagination="false"
        size="small"
        class="custom-table"
        row-key="company"
        :expanded-row-keys="expandedKeys"
        @expanded-rows-change="onExpandedChange"
        :custom-row="rowClick"
      >
        <!-- 展开行：项目详情表 -->
        <template #expandedRowRender="{ record }">
          <div class="p-4 bg-black/20 rounded-lg">
            <h4 class="font-semibold mb-3 text-sm">
              {{ record.company }} - 项目列表 ({{ record.projects?.length || 0 }}个)
            </h4>
            <a-table
              :columns="projectColumns"
              :data-source="record.projects || []"
              :pagination="false"
              size="small"
              row-key="article_id"
              class="custom-table"
            >
              <template #bodyCell="{ column, record: project }">
                <template v-if="column.key === 'type'">
                  <a-tag :color="project.is_new_contract ? 'green' : 'blue'">
                    {{ project.is_new_contract ? '新签' : '在建' }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'amount'">
                  <template v-if="project.amount_cny">
                    {{ formatAmount(project.amount_cny) }}
                    <a-tooltip v-if="project.is_estimated" title="金额为按方量估算值">
                      <a-tag color="orange" class="ml-1">估算</a-tag>
                    </a-tooltip>
                  </template>
                  <span v-else class="text-gray-500">-</span>
                </template>
                <template v-if="column.key === 'volume'">
                  <span v-if="project.volume">{{ formatVolume(project.volume) }}</span>
                  <span v-else class="text-gray-500">-</span>
                </template>
                <template v-if="column.key === 'action'">
                  <a-button
                    v-if="project.article_url"
                    type="link"
                    size="small"
                    :href="project.article_url"
                    target="_blank"
                  >
                    查看原文
                  </a-button>
                  <span v-else class="text-gray-500">-</span>
                </template>
              </template>
            </a-table>
          </div>
        </template>

        <!-- 自定义金额列 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'newAmount'">
            <span class="font-semibold text-green-400">{{ formatAmount(record.new_contract_amount) }}</span>
          </template>
          <template v-if="column.key === 'ongoingAmount'">
            <span class="text-blue-400">{{ formatAmount(record.ongoing_amount) }}</span>
          </template>
          <template v-if="column.key === 'totalAmount'">
            <span class="font-semibold">{{ formatAmount(record.total_amount) }}</span>
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

const companyBarChart = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart | null = null
const companyData = ref<any[]>([])
const expandedKeys = ref<string[]>([])

// 点击整行切换展开/折叠（点击行内链接/按钮除外）
const rowClick = (record: any) => ({
  onClick: (event: Event) => {
    const target = event.target as HTMLElement
    if (target.closest('a, button')) return
    const key = record.company
    expandedKeys.value = expandedKeys.value.includes(key)
      ? expandedKeys.value.filter((k: string) => k !== key)
      : [...expandedKeys.value, key]
  },
})

const onExpandedChange = (keys: string[]) => {
  expandedKeys.value = keys
}

const columns = [
  { title: '公司', dataIndex: 'company', key: 'company', width: 180 },
  { title: '新签项目', dataIndex: 'new_contract_count', key: 'new_contract_count', width: 100 },
  { title: '新签金额', key: 'newAmount', width: 140 },
  { title: '在建项目', dataIndex: 'ongoing_count', key: 'ongoing_count', width: 100 },
  { title: '在建金额', key: 'ongoingAmount', width: 140 },
  { title: '总金额', key: 'totalAmount', width: 130 },
]

const projectColumns = [
  { title: '项目标题', dataIndex: 'title', key: 'title', ellipsis: true },
  { title: '类型', key: 'type', width: 90 },
  { title: '金额', key: 'amount', width: 140 },
  { title: '方量', key: 'volume', width: 110 },
  { title: '地区', dataIndex: 'region', key: 'region', width: 80 },
  { title: '操作', key: 'action', width: 90 },
]

const formatAmount = (amount: number | null | undefined) => {
  if (!amount) return '-'
  if (amount >= 10000) return `${(amount / 10000).toFixed(1)}亿元`
  return `${amount.toFixed(0)}万元`
}

const formatVolume = (volume: number | null | undefined) => {
  if (!volume) return '-'
  if (volume >= 10000) return `${(volume / 10000).toFixed(0)}万方`
  return `${volume.toFixed(0)}m³`
}

const fetchData = async () => {
  try {
    const res = await fetch('/api/company-operations')
    const data = await res.json()
    companyData.value = data.companies || []
    renderChart(companyData.value)
  } catch (error) {
    console.error('Failed to fetch company data:', error)
  }
}

const renderChart = (companies: any[]) => {
  if (!companyBarChart.value) return
  chartInstance?.destroy()
  const top10 = companies.slice(0, 10)

  chartInstance = new Chart(companyBarChart.value, {
    type: 'bar',
    data: {
      labels: top10.map(c => c.company),
      datasets: [
        {
          label: '新签项目',
          data: top10.map(c => c.new_contract_count),
          backgroundColor: 'rgba(34, 197, 94, 0.8)',
          borderColor: 'rgba(34, 197, 94, 1)',
          borderWidth: 1,
        },
        {
          label: '在建项目',
          data: top10.map(c => c.ongoing_count),
          backgroundColor: 'rgba(59, 130, 246, 0.8)',
          borderColor: 'rgba(59, 130, 246, 1)',
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#cbd5e1' } } },
      scales: {
        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
        x: { grid: { display: false } },
      },
    },
    plugins: [barValuePlugin],
  })
}

// 柱状图数字插件：每根柱子顶部显示数值
const barValuePlugin = {
  id: 'barValue',
  afterDatasetsDraw(chart: any) {
    const { ctx } = chart
    chart.data.datasets.forEach((dataset: any, di: number) => {
      const meta = chart.getDatasetMeta(di)
      meta.data.forEach((bar: any, i: number) => {
        const value = dataset.data[i]
        if (!value) return
        ctx.save()
        ctx.font = 'bold 10px sans-serif'
        ctx.fillStyle = '#e2e8f0'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText(String(value), bar.x, bar.y - 3)
        ctx.restore()
      })
    })
  },
}

onMounted(() => {
  fetchData()
  window.addEventListener('refresh-statistics', fetchData)
})
onUnmounted(() => {
  window.removeEventListener('refresh-statistics', fetchData)
  chartInstance?.destroy()
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
