<template>
  <div class="h-screen flex flex-col bg-slate-900 text-white overflow-hidden">
    <!-- Navbar -->
    <NavBar />

    <!-- Main Content -->
    <main class="flex-1 flex overflow-hidden relative min-h-0">
      <!-- Sidebar -->
      <aside 
        class="glass-card flex flex-col overflow-hidden transition-all duration-300 z-10 flex-shrink-0 transform vessel-sidebar"
        :class="sidebarOpen ? 'w-64 translate-x-0 m-4 mr-0' : 'w-0 -translate-x-full m-0'"
      >
        <div class="p-4 border-b border-white/10 flex justify-between items-center bg-white/5">
          <h2 class="font-bold text-lg">船舶列表</h2>
          <button @click="sidebarOpen = false" class="text-gray-400 hover:text-white cursor-pointer relative z-50 p-1">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        
        <!-- Search Box -->
        <div class="p-4 border-b border-white/10">
          <div class="relative">
            <input 
              v-model="searchQuery" 
              type="text" 
              placeholder="搜索船舶名称/MMSI..." 
              class="w-full bg-slate-800/50 border border-white/10 rounded-lg py-2 px-3 text-sm focus:outline-none focus:border-blue-500 transition-colors"
            />
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 absolute right-3 top-2.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>

        <!-- Vessel Tree -->
        <div class="flex-1 overflow-y-auto custom-scrollbar">
          <div v-if="loading" class="p-4 text-center text-gray-400">
            加载中...
          </div>
          <div v-else-if="Object.keys(groupedVessels).length === 0" class="p-4 text-center text-gray-400">
            无匹配船舶
          </div>
          
          <a-collapse v-else v-model:activeKey="activeKeys" ghost expand-icon-position="right">
            <a-collapse-panel 
              v-for="(group, company) in groupedVessels" 
              :key="company" 
              :header="`${company || '未知船队'} (${group.length})`"
              class="vessel-group"
            >
              <div class="flex flex-col gap-1">
                <div 
                  v-for="vessel in group" 
                  :key="vessel.id"
                  class="flex items-center justify-between p-2 rounded hover:bg-white/5 cursor-pointer transition-colors group"
                  :class="{ 'bg-blue-500/10': selectedVesselId === vessel.id }"
                  @click="handleVesselClick(vessel)"
                >
                  <div class="flex items-center gap-2 overflow-hidden">
                    <div 
                      class="w-2 h-2 rounded-full flex-shrink-0"
                      :style="{ backgroundColor: getStatusColor(vessel), boxShadow: `0 0 8px ${getStatusColor(vessel)}` }"
                    ></div>
                    <span class="text-sm truncate" :style="getStatusTextStyle(vessel)" :title="vessel.name">{{ vessel.name }}</span>
                  </div>
                  <div class="flex items-center gap-2 text-xs font-mono" :style="getStatusTextStyle(vessel)">
                    <span>{{ formatSpeed(vessel.speed) }}</span>
                  </div>
                </div>
              </div>
            </a-collapse-panel>
          </a-collapse>
        </div>
      </aside>
      
      <!-- Toggle Sidebar Button (When closed) -->
      <div 
        v-if="!sidebarOpen"
        class="absolute top-8 left-4 z-20 glass-card p-2 rounded-lg cursor-pointer hover:bg-white/10 transition-colors vessel-sidebar-toggle"
        @click="sidebarOpen = true"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </div>

      <!-- Map Container -->
      <div class="flex-1 m-4 ml-0 glass-card overflow-hidden flex flex-col min-h-0">
        <div class="relative flex-1 min-h-[360px]">
          <div ref="mapContainer" class="w-full h-full z-0"></div>

          <!-- Status Legend -->
          <div class="absolute top-4 right-4 z-[1000] glass-card px-3 py-2 rounded-xl flex flex-col gap-1 text-xs sm:text-sm">
          <div class="flex flex-wrap gap-x-4 gap-y-1">
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="text-gray-400">监控</span>
              <span class="text-white font-bold" title="配置了MMSI的船舶数量">{{ stats.active }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="text-gray-400">总计</span>
              <span class="text-white font-bold">{{ stats.total }}</span>
            </div>
          </div>
          <div class="flex flex-wrap gap-x-4 gap-y-1 border-t border-white/10 pt-1">
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span 
                class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.6)]"
                :style="{ backgroundColor: statusColors.dredging }"
              ></span>
              <span class="text-gray-300">施工中</span>
              <span class="text-blue-400 font-mono">{{ stats.dredging }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span 
                class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]"
                :style="{ backgroundColor: statusColors.underway }"
              ></span>
              <span class="text-gray-300">航行中</span>
              <span class="text-green-400 font-mono">{{ stats.underway }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span 
                class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full shadow-[0_0_8px_rgba(239,68,68,0.6)]"
                :style="{ backgroundColor: statusColors.moored }"
              ></span>
              <span class="text-gray-300">停泊</span>
              <span class="text-red-400 font-mono">{{ stats.moored }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span 
                class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full shadow-[0_0_8px_rgba(107,114,128,0.6)]"
                :style="{ backgroundColor: statusColors.offline }"
              ></span>
              <span class="text-gray-300">离线</span>
              <span class="text-gray-400 font-mono">{{ stats.offline }}</span>
            </div>
          </div>
        </div>
        
          <!-- Map Tools -->
          <div class="absolute bottom-8 right-4 z-[1000] flex flex-col gap-2">
          <button 
            class="w-10 h-10 glass-card rounded-lg flex items-center justify-center hover:bg-white/20 transition-colors text-white"
            title="复位"
            @click="resetView"
          >
            <i class="fa-solid fa-house"></i>
          </button>
          <button 
            class="w-10 h-10 glass-card rounded-lg flex items-center justify-center hover:bg-white/20 transition-colors text-white"
            title="清空轨迹"
            @click="clearAllTracks"
          >
            <i class="fa-solid fa-trash"></i>
          </button>
          <button 
            class="w-10 h-10 glass-card rounded-lg flex items-center justify-center hover:bg-white/20 transition-colors text-white"
            :class="{ '!bg-blue-600/50': isPickingPoint }"
            title="点位置"
            @click="togglePickPoint"
          >
            <i class="fa-solid fa-location-dot"></i>
          </button>
          <button 
            class="w-10 h-10 glass-card rounded-lg flex items-center justify-center hover:bg-white/20 transition-colors text-white"
            :class="{ '!bg-blue-600/50': isMeasuring }"
            title="测距"
            @click="toggleMeasure"
          >
            <i class="fa-solid fa-ruler-horizontal"></i>
          </button>
          </div>
        </div>

        <div v-if="trackDisplayList.length" ref="trackListRef" class="border-t border-white/10 bg-white/5 p-3 text-xs text-gray-300 max-h-[240px] flex flex-col overflow-hidden">
          <div class="flex items-center justify-between mb-2 sticky top-0 z-10 bg-white/5 pb-2">
            <span class="font-semibold text-gray-200">最近3天轨迹</span>
          </div>
          <div class="flex-1 overflow-y-auto custom-scrollbar">
            <div class="flex flex-col gap-3">
              <div v-for="item in trackDisplayList" :key="item.mmsi" class="rounded-lg border border-white/10 bg-white/5 p-2 flex flex-col max-h-[180px]">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: item.color }"></span>
                    <span class="font-semibold text-gray-200">{{ item.name }}</span>
                    <span class="text-gray-500 font-mono">MMSI {{ item.mmsi }}</span>
                  </div>
                </div>
                <div v-if="getTrackPage(item.mmsi).length === 0" class="text-gray-400">暂无轨迹点</div>
                <div v-else class="flex flex-col gap-1 flex-1 overflow-y-auto custom-scrollbar">
                  <div class="grid grid-cols-[40px_1fr_1fr_1fr] gap-2 text-[11px] text-gray-500 border-b border-white/10 pb-1 text-center">
                    <span class="text-center">序号</span>
                    <span class="text-center">时间</span>
                    <span class="text-center">位置</span>
                    <span class="text-center">拉取时间</span>
                  </div>
                  <div v-for="(p, idx) in getTrackPage(item.mmsi)" :key="`${p.timestamp}-${p.created_at}-${idx}`" class="grid grid-cols-[40px_1fr_1fr_1fr] gap-2 items-center">
                    <span class="text-gray-500">#{{ getTrackRowIndex(item.mmsi, idx) }}</span>
                    <span class="text-gray-400">{{ formatTrackTime(p.timestamp) }}</span>
                    <span class="font-mono">{{ formatTrackCoord(p.lat) }}, {{ formatTrackCoord(p.lng) }}</span>
                    <span class="text-gray-500 text-right">{{ formatTrackTime(p.created_at) }}</span>
                  </div>
                </div>
                <div class="flex items-center justify-between mt-2">
                  <button class="px-2 py-1 rounded bg-white/10 hover:bg-white/20" @click="prevTrackPage(item.mmsi)" :disabled="getTrackPageIndex(item.mmsi) <= 1">上一页</button>
                  <span class="text-gray-400">{{ getTrackPageIndex(item.mmsi) }}/{{ getTrackTotalPages(item.mmsi) }}</span>
                  <button class="px-2 py-1 rounded bg-white/10 hover:bg-white/20" @click="nextTrackPage(item.mmsi)" :disabled="getTrackPageIndex(item.mmsi) >= getTrackTotalPages(item.mmsi)">下一页</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import L from 'leaflet'
import type { LeafletMouseEvent } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import NavBar from '@/components/NavBar.vue'

interface Vessel {
  id: string
  mmsi: string
  name: string
  status: string
  lat: number
  lng: number
  speed?: number
  heading?: number
  country: string
  continent?: string
  province?: string
  city?: string
  updated_at?: string
  company?: string
  is_active?: boolean
}

const mapContainer = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
const sidebarOpen = ref(true)
const loading = ref(false)
const selectedVesselId = ref<string | null>(null)
const activeKeys = ref<string[]>([]) // Default collapsed

// Fleet colors mapping
const fleetColors: Record<string, string> = {
  '上航局': '#3b82f6', // Blue
  '天航局': '#3b82f6', // Blue
  '广航局': '#3b82f6', // Blue
  'Boskalis': '#f97316', // Orange
  'DEME': '#22c55e', // Green
  'JanDeNUL': '#eab308', // Yellow
  'NMDC': '#a855f7', // Purple
  'VanOORD': '#ec4899', // Pink
  '其他': '#9ca3af' // Gray
}

const fleetSortOrder = ['上航局', '天航局', '广航局', 'Boskalis', 'DEME', 'JanDeNUL', 'NMDC', 'VanOORD']


const vessels = ref<Vessel[]>([])
const searchQuery = ref('')
const stats = ref({
  total: 0,
  active: 0,
  underway: 0,
  dredging: 0,
  moored: 0,
  offline: 0
})

const statusColors: Record<string, string> = {
  dredging: '#3b82f6',
  underway: '#22c55e',
  moored: '#ef4444',
  offline: '#6b7280',
  untracked: '#6b7280'
}

const currentZoom = ref(3)
let vesselLayerGroup: L.LayerGroup | null = null
let tagLayerGroup: L.LayerGroup | null = null
const vesselMarkerMap = new Map<string, L.Marker>()
let trackLayerGroup: L.LayerGroup | null = null
const trackLayerMap = new Map<string, { line: L.Polyline, points: L.LayerGroup, color: string }>()
const trackOrder = ref<string[]>([])
const maxTrackCount = 10
const trackColors = ['#3b82f6', '#22c55e', '#f97316', '#eab308', '#a855f7', '#ec4899', '#ef4444', '#14b8a6', '#38bdf8', '#f472b6']
const mapZoomDuration = 3
const trackListRef = ref<HTMLDivElement | null>(null)

interface TrackPoint {
  lat: number
  lng: number
  timestamp?: string
  created_at?: string
}

interface TrackState {
  points: TrackPoint[]
  pageIndex: number
  pageSize: number
}

const trackStates = ref<Record<string, TrackState>>({})
const selectedTrackMmsi = computed(() => {
  if (!selectedVesselId.value) return null
  const vessel = vessels.value.find(v => v.id === selectedVesselId.value)
  return vessel?.mmsi || null
})

const trackDisplayList = computed(() => {
  const target = selectedTrackMmsi.value
  const list = target ? trackOrder.value.filter(mmsi => mmsi === target) : []
  return list.map((mmsi, index) => {
    const vessel = vessels.value.find(v => v.mmsi === mmsi)
    return {
      mmsi,
      name: vessel?.name || '未知船舶',
      color: trackLayerMap.get(mmsi)?.color || trackColors[index % trackColors.length]
    }
  })
})

// Map Tools State
const isPickingPoint = ref(false)
const isMeasuring = ref(false)
const measurePoints = ref<L.LatLng[]>([])
let measureLayerGroup: L.LayerGroup | null = null
let pickTooltip: L.Tooltip | null = null
let measureHintTooltip: L.Tooltip | null = null

// Group vessels by company
const groupedVessels = computed(() => {
  const query = searchQuery.value.toLowerCase().trim()
  const filtered = vessels.value.filter(v => {
    if (!query) return true
    const name = String(v.name || '').toLowerCase()
    const mmsi = String(v.mmsi || '')
    const company = String(v.company || '').toLowerCase()
    return name.includes(query) || mmsi.includes(query) || company.includes(query)
  })
  
  const groups: Record<string, Vessel[]> = {}
  filtered.forEach(v => {
    const company = v.company || '其他'
    if (!groups[company]) {
      groups[company] = []
    }
    groups[company].push(v)
  })
  
  // Sort companies by custom order
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    const indexA = fleetSortOrder.indexOf(a)
    const indexB = fleetSortOrder.indexOf(b)
    
    // Both in list
    if (indexA !== -1 && indexB !== -1) return indexA - indexB
    // A in list, B not
    if (indexA !== -1) return -1
    // B in list, A not
    if (indexB !== -1) return 1
    
    // Special case for '其他' (Others) - always last
    if (a === '其他') return 1
    if (b === '其他') return -1
    
    // Both not in list - alphabetical
    return a.localeCompare(b)
  })
  
  const sortedGroups: Record<string, Vessel[]> = {}
  sortedKeys.forEach(k => {
    sortedGroups[k] = groups[k].sort((a, b) => {
      const rankDiff = getVesselSortRank(a) - getVesselSortRank(b)
      if (rankDiff !== 0) return rankDiff
      return a.name.localeCompare(b.name)
    })
  })
  
  return sortedGroups
})

// Auto-expand search results
watch(searchQuery, (newVal) => {
  if (newVal) {
    activeKeys.value = Object.keys(groupedVessels.value)
  }
})

const scheduleMapResize = async () => {
  await nextTick()
  if (map) {
    map.invalidateSize()
  }
}

watch([sidebarOpen, () => trackDisplayList.value.length], () => {
  scheduleMapResize()
})

/**
 * 计算船舶的展示状态键
 */
function getVesselStatusKey(vessel: Vessel): keyof typeof statusColors {
  if (!vessel.mmsi) return 'untracked'
  const key = mapStatusToIconKey(vessel.status)
  const speed = typeof vessel.speed === 'number' ? vessel.speed : Number(vessel.speed)
  if (key === 'offline' && Number.isFinite(speed) && speed > 0.2) {
    return 'underway'
  }
  return key
}

/**
 * 获取船舶状态颜色
 */
function getStatusColor(vessel: Vessel): string {
  const key = getVesselStatusKey(vessel)
  return statusColors[key]
}

/**
 * 获取状态文本颜色样式
 */
function getStatusTextStyle(vessel: Vessel): Record<string, string> {
  return { color: getStatusColor(vessel) }
}

/**
 * 获取船舶列表排序权重
 */
function getVesselSortRank(vessel: Vessel): number {
  if (!vessel.mmsi) return 4
  const key = getVesselStatusKey(vessel)
  if (key === 'dredging') return 0
  if (key === 'underway') return 1
  if (key === 'moored') return 2
  if (key === 'offline') return 3
  return 2
}

/**
 * 格式化航速文本
 */
function formatSpeed(value: number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '-'
  return `${value.toFixed(1)}节`
}

function mapStatusToIconKey(status: string | undefined): string {
  if (!status) return 'offline'
  const s = status.toLowerCase()
  
  if (s === 'dredging') return 'dredging'
  if (s === 'underway using engine' || s === 'underway') return 'underway'
  if (s === 'moored' || s === 'at anchor') return 'moored'
  if (s === 'stopped') return 'moored'
  if (s === 'offline' || s === 'unknown') return 'offline'
  
  if (s.includes('施工') || s.includes('作业') || s.includes('疏浚')) return 'dredging'
  if (s.includes('操纵能力受限')) return 'dredging'
  if (s.includes('机动船在航')) return 'underway'
  if (s.includes('调遣')) return 'underway'
  if (s.includes('锚泊') || s.includes('系泊') || s.includes('停泊') || s.includes('停靠') || s.includes('抛锚')) return 'moored'
  if (s.includes('离线')) return 'offline'
  
  return 'offline'
}

/**
 * 解析船舶坐标
 */
function getVesselLatLng(vessel: Vessel): L.LatLng | null {
  const lat = typeof vessel.lat === 'number' ? vessel.lat : Number(vessel.lat)
  const lng = typeof vessel.lng === 'number' ? vessel.lng : Number(vessel.lng)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return L.latLng(lat, lng)
}

async function handleVesselClick(vessel: Vessel) {
  selectedVesselId.value = vessel.id
  const marker = vessel.mmsi ? vesselMarkerMap.get(vessel.mmsi) : null
  const latlng = getVesselLatLng(vessel) || marker?.getLatLng() || null
  if (!vessel.mmsi) {
    message.info('该船舶未配置MMSI，无法查询轨迹')
    return
  }
  const hasTrack = await showTrack(vessel.mmsi, { animate: false, includeLatLng: latlng })
  if (!hasTrack) {
    if (latlng && map) {
      map.setView(latlng, Math.max(12, map.getZoom()), { animate: false })
    } else {
      message.info('该船舶暂无位置信息')
    }
  }
  if (marker) {
    marker.openPopup()
  }
}

// ... (keep existing helper functions like translateStatus, translateCountry, createIcon, getCompanyAbbreviation, countryColors, chinaRedVariants, getTagColor)

/**
 * 根据状态键获取中文状态文本
 */
function translateStatusByKey(key: keyof typeof statusColors): string {
  if (key === 'dredging') return '作业中'
  if (key === 'underway') return '航行中'
  if (key === 'moored') return '停泊'
  if (key === 'untracked') return '未跟踪'
  return '离线'
}

/**
 * 将区域转换为中文
 */
function translateContinent(en: string | undefined): string {
  if (!en) return ''
  const map: Record<string, string> = {
    'Asia': '亚洲',
    'Europe': '欧洲',
    'Africa': '非洲',
    'North America': '北美洲',
    'South America': '南美洲',
    'Oceania': '大洋洲',
    'Antarctica': '南极洲',
    'Unknown': ''
  }
  return map[en] || en
}

function translateCountry(en: string | undefined): string {
  if (!en) return ''
  const map: Record<string, string> = {
    'China': '中国', 'CN': '中国',
    'United States': '美国', 'US': '美国', 'USA': '美国',
    'Netherlands': '荷兰', 'NL': '荷兰',
    'Singapore': '新加坡', 'SG': '新加坡',
    'Malaysia': '马来西亚', 'MY': '马来西亚',
    'Japan': '日本', 'JP': '日本',
    'Korea': '韩国', 'KR': '韩国', 'South Korea': '韩国',
    'Australia': '澳大利亚', 'AU': '澳大利亚',
    'United Kingdom': '英国', 'UK': '英国', 'GB': '英国',
    'Germany': '德国', 'DE': '德国',
    'France': '法国', 'FR': '法国',
    'Indonesia': '印度尼西亚', 'ID': '印度尼西亚',
    'India': '印度', 'IN': '印度',
    'Russia': '俄罗斯', 'RU': '俄罗斯',
    'Saudi Arabia': '沙特阿拉伯', 'SA': '沙特阿拉伯',
    'United Arab Emirates': '阿联酋', 'AE': '阿联酋',
    'Brazil': '巴西', 'BR': '巴西',
    'Vietnam': '越南', 'VN': '越南',
    'Philippines': '菲律宾', 'PH': '菲律宾'
  }
  return map[en] || en
}

/**
 * 格式化轨迹时间显示
 */
function formatTrackTime(value?: string) {
  if (!value) return '-'
  const text = String(value).replace('T', ' ')
  return text.length > 19 ? text.slice(0, 19) : text
}

/**
 * 格式化轨迹坐标
 */
function formatTrackCoord(value: number) {
  if (!Number.isFinite(value)) return '-'
  return value.toFixed(4)
}

function createIcon(color: string) {
  return L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; box-shadow: 0 0 12px ${color}; border: 2px solid white;"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    popupAnchor: [0, -6]
  })
}

function resetView() {
  if (!map) return
  map.flyTo([25, 110], 3, { animate: true, duration: mapZoomDuration })
}

function togglePickPoint() {
  isPickingPoint.value = !isPickingPoint.value
  isMeasuring.value = false
  if (!isPickingPoint.value && map) {
    map.closePopup()
  }
  if (!isPickingPoint.value) {
    clearPickTooltip()
  }
  if (!isMeasuring.value) {
    clearMeasureHintTooltip()
  }
}

function toggleMeasure() {
  isMeasuring.value = !isMeasuring.value
  isPickingPoint.value = false
  
  if (!isMeasuring.value) {
    // Clear measurement
    if (measureLayerGroup) measureLayerGroup.clearLayers()
    measurePoints.value = []
  }
  if (!isMeasuring.value) {
    clearMeasureHintTooltip()
  }
  if (!isPickingPoint.value) {
    clearPickTooltip()
  }
}

function onMapClick(e: LeafletMouseEvent) {
  const latlng = e.latlng
  
  if (isPickingPoint.value) {
    const text = `${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}`
    navigator.clipboard.writeText(text)
    togglePickPoint()
    return
  }
  
  if (isMeasuring.value) {
    measurePoints.value.push(latlng)
    
    // Add marker
    L.circleMarker(latlng, {
      radius: 4,
      color: '#ef4444',
      fillColor: '#ef4444',
      fillOpacity: 1
    }).addTo(measureLayerGroup!)
    
    // Draw line if more than 1 point
    if (measurePoints.value.length > 1) {
      const points = measurePoints.value
      const lastPoint = points[points.length - 2]
      
      L.polyline([lastPoint, latlng], {
        color: '#ef4444',
        weight: 2,
        dashArray: '5, 5'
      }).addTo(measureLayerGroup!)
      
      // Calculate total distance
      let totalDist = 0
      for (let i = 0; i < points.length - 1; i++) {
        totalDist += points[i].distanceTo(points[i+1])
      }
      
      // Calculate segment distance
      const segmentDist = lastPoint.distanceTo(latlng)
      
      const formatDist = (d: number) => d > 1000 
        ? `${(d / 1000).toFixed(2)} km` 
        : `${Math.round(d)} m`
        
      const popupContent = `
        <div class="text-white px-2 py-1 min-w-[120px]">
          <div class="font-bold border-b border-gray-600 mb-1 pb-1">测量结果</div>
          <div class="flex justify-between gap-4 text-sm"><span class="text-white">总距离:</span> <span class="font-mono font-bold">${formatDist(totalDist)}</span></div>
          <div class="flex justify-between gap-4 text-sm"><span class="text-white">段距离:</span> <span class="font-mono">${formatDist(segmentDist)}</span></div>
        </div>
      `
      
      L.popup({ autoClose: false, closeOnClick: false, className: 'measure-popup' })
        .setLatLng(latlng)
        .setContent(popupContent)
        .addTo(measureLayerGroup!)
    } else {
       // First point
       L.popup({ autoClose: false, closeOnClick: false, className: 'measure-popup' })
        .setLatLng(latlng)
        .setContent(`<div class="text-white px-2 py-1 text-sm">起点</div>`)
        .addTo(measureLayerGroup!)
    }
  }
}

/**
 * 跟随鼠标显示取点或测距提示
 */
function onMapMouseMove(e: LeafletMouseEvent) {
  if (!map) return
  const latlng = e.latlng
  if (isPickingPoint.value) {
    if (!pickTooltip) {
      pickTooltip = L.tooltip({ direction: 'top', className: 'map-tooltip', opacity: 0.9, offset: [0, -10] })
      pickTooltip.addTo(map)
    }
    pickTooltip.setLatLng(latlng)
    pickTooltip.setContent(`${latlng.lat.toFixed(6)}, ${latlng.lng.toFixed(6)}`)
  } else {
    clearPickTooltip()
  }

  if (isMeasuring.value) {
    if (!measureHintTooltip) {
      measureHintTooltip = L.tooltip({ direction: 'top', className: 'map-tooltip', opacity: 0.8, offset: [0, -10] })
      measureHintTooltip.addTo(map)
    }
    measureHintTooltip.setLatLng(latlng)
    measureHintTooltip.setContent('右击退出')
  } else {
    clearMeasureHintTooltip()
  }
}

function onMapRightClick() {
  if (isMeasuring.value) {
    toggleMeasure() // Cancel measurement
    message.info('已取消测量')
  }
}

/**
 * 清除取点提示
 */
function clearPickTooltip() {
  if (map && pickTooltip) {
    map.removeLayer(pickTooltip)
    pickTooltip = null
  }
}

/**
 * 清除测距提示
 */
function clearMeasureHintTooltip() {
  if (map && measureHintTooltip) {
    map.removeLayer(measureHintTooltip)
    measureHintTooltip = null
  }
}

/**
 * 生成船队简称
 * @param company 公司/船队名称
 * @returns 简称（最多4个字符）
 */
function getCompanyAbbreviation(company: string | undefined): string {
  if (!company) return ''
  
  const cleaned = company.trim()
  
  // 中文处理：取前2-4个字符
  if (/[\u4e00-\u9fa5]/.test(cleaned)) {
    return cleaned.substring(0, 4)
  }
  
  // 英文处理：取首字母缩写或前几个字符
  const words = cleaned.split(/\s+/)
  if (words.length > 1) {
    return words.map(w => w[0]?.toUpperCase() || '').join('').substring(0, 4)
  }
  
  return cleaned.substring(0, 4).toUpperCase()
}

/**
 * 国家国旗颜色映射
 */
// const countryColors: Record<string, { bg: string, text: string }> = {
//   'China': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'CN': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   '中国': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'Netherlands': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'NL': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'Singapore': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'SG': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'United States': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'US': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'USA': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'United Kingdom': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'UK': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'GB': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'Japan': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'JP': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   'Korea': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'KR': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'South Korea': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'Germany': { bg: 'rgba(220, 38, 38, 0.4)', text: '#1f2937' },
//   'DE': { bg: 'rgba(220, 38, 38, 0.4)', text: '#1f2937' },
//   'France': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'FR': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'Australia': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
//   'AU': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' }
// }

/**
 * 中国船队的红色变体
 */
// const chinaRedVariants = [
//   { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
//   { bg: 'rgba(239, 68, 68, 0.4)', text: 'white' },
//   { bg: 'rgba(185, 28, 28, 0.4)', text: 'white' },
//   { bg: 'rgba(248, 113, 113, 0.4)', text: '#1f2937' },
//   { bg: 'rgba(153, 27, 27, 0.4)', text: 'white' },
//   { bg: 'rgba(252, 165, 165, 0.4)', text: '#1f2937' }
// ]

/**
 * 根据公司名称生成颜色
 * @param company 公司名称
 * @returns 颜色对象 { bg: string, text: string }
 */
function getTagColor(company: string | undefined): { bg: string, text: string } {
  if (!company) {
     return { bg: `rgba(107, 114, 128, 0.6)`, text: 'white' } // Gray
  }
  
  const c = company.toLowerCase()
  let colorHex = fleetColors['其他']
  
  if (c.includes('上航') || c.includes('shanghai')) colorHex = fleetColors['上航局']
  else if (c.includes('天航') || c.includes('tianjin')) colorHex = fleetColors['天航局']
  else if (c.includes('广航') || c.includes('guangzhou')) colorHex = fleetColors['广航局']
  else if (c.includes('boskalis')) colorHex = fleetColors['Boskalis']
  else if (c.includes('deme')) colorHex = fleetColors['DEME']
  else if (c.includes('jan de nul') || c.includes('jandenul')) colorHex = fleetColors['JanDeNUL']
  else if (c.includes('nmdc')) colorHex = fleetColors['NMDC']
  else if (c.includes('van oord') || c.includes('vanoord')) colorHex = fleetColors['VanOORD']
  
  // Convert hex to rgba
  const r = parseInt(colorHex.slice(1, 3), 16)
  const g = parseInt(colorHex.slice(3, 5), 16)
  const b = parseInt(colorHex.slice(5, 7), 16)
  
  return { bg: `rgba(${r}, ${g}, ${b}, 0.6)`, text: 'white' }
}

/**
 * 获取轨迹状态
 */
function getTrackState(mmsi: string | undefined): TrackState | null {
  if (!mmsi) return null
  return trackStates.value[mmsi] || null
}

/**
 * 获取轨迹分页数据
 */
function getTrackPage(mmsi: string): TrackPoint[] {
  const state = getTrackState(mmsi)
  if (!state) return []
  const start = (state.pageIndex - 1) * state.pageSize
  return state.points.slice(start, start + state.pageSize)
}

function getTrackRowIndex(mmsi: string, idx: number): number {
  const state = getTrackState(mmsi)
  if (!state) return idx + 1
  return (state.pageIndex - 1) * state.pageSize + idx + 1
}

/**
 * 获取轨迹当前页码
 */
function getTrackPageIndex(mmsi: string): number {
  const state = getTrackState(mmsi)
  return state ? state.pageIndex : 1
}

/**
 * 获取轨迹总页数
 */
function getTrackTotalPages(mmsi: string): number {
  const state = getTrackState(mmsi)
  if (!state) return 1
  return Math.max(1, Math.ceil(state.points.length / state.pageSize))
}

/**
 * 翻到上一页
 */
function prevTrackPage(mmsi: string) {
  const state = getTrackState(mmsi)
  if (!state) return
  state.pageIndex = Math.max(1, state.pageIndex - 1)
  trackStates.value = { ...trackStates.value }
}

/**
 * 翻到下一页
 */
function nextTrackPage(mmsi: string) {
  const state = getTrackState(mmsi)
  if (!state) return
  const maxPage = getTrackTotalPages(mmsi)
  state.pageIndex = Math.min(maxPage, state.pageIndex + 1)
  trackStates.value = { ...trackStates.value }
}

/**
 * 删除单条轨迹
 */
function removeTrack(mmsi: string) {
  const track = trackLayerMap.get(mmsi)
  if (track && map) {
    track.line.remove()
    track.points.remove()
  }
  trackLayerMap.delete(mmsi)
  trackOrder.value = trackOrder.value.filter(id => id !== mmsi)
  if (trackStates.value[mmsi]) {
    const next = { ...trackStates.value }
    delete next[mmsi]
    trackStates.value = next
  }
}

/**
 * 清空所有轨迹
 */
function clearAllTracks() {
  trackLayerMap.forEach((track) => {
    track.line.remove()
    track.points.remove()
  })
  trackLayerMap.clear()
  trackOrder.value = []
  trackStates.value = {}
}

/**
 * 显示最近三天轨迹
 */
async function showTrack(mmsi: string, options?: { animate?: boolean; includeLatLng?: L.LatLng | null }) {
  if (!map || !trackLayerGroup) return
  try {
    const response = await fetch(`/api/ship_tracks?mmsi=${mmsi}&days=3`)
    const tracks = await response.json()
    
    if (!tracks || tracks.length < 2) {
      message.info('暂无轨迹数据')
      return false
    }
    if (trackLayerMap.has(mmsi)) {
      removeTrack(mmsi)
    }
    while (trackOrder.value.length >= maxTrackCount) {
      const oldest = trackOrder.value.shift()
      if (oldest) {
        removeTrack(oldest)
      }
    }

    const color = trackColors[trackOrder.value.length % trackColors.length]
    const latlngs = tracks.map((t: any) => [t.lat, t.lng])
    const line = L.polyline(latlngs, {
      color,
      weight: 3,
      opacity: 0.85,
      dashArray: '5, 10'
    }).addTo(trackLayerGroup!)
    const points = L.layerGroup().addTo(trackLayerGroup!)
    tracks.forEach((t: any) => {
      const point = L.circleMarker([t.lat, t.lng], {
        radius: 2,
        color,
        fillColor: '#fff',
        fillOpacity: 1,
        weight: 1
      }).addTo(points)
      const timeText = formatTrackTime(t.timestamp || t.created_at)
      point.bindTooltip(timeText, { direction: 'top', className: 'map-tooltip', opacity: 0.9, offset: [0, -6] })
    })
    line.on('click', () => removeTrack(mmsi))

    trackLayerMap.set(mmsi, { line, points, color })
    trackOrder.value = [...trackOrder.value, mmsi]
    trackStates.value = {
      ...trackStates.value,
      [mmsi]: {
        points: tracks.map((t: any) => ({
          lat: Number(t.lat),
          lng: Number(t.lng),
          timestamp: t.timestamp,
          created_at: t.created_at
        })),
        pageIndex: 1,
        pageSize: 10
      }
    }

    const vessel = vessels.value.find(v => v.mmsi === mmsi)
    if (vessel) {
      selectedVesselId.value = vessel.id
    }

    const bounds = line.getBounds()
    const includeLatLng = options?.includeLatLng
    if (includeLatLng) {
      bounds.extend(includeLatLng)
    }
    if (bounds.isValid()) {
      const animate = options?.animate !== false
      if (bounds.getNorthEast().equals(bounds.getSouthWest())) {
        const center = bounds.getCenter()
        const singleBounds = L.latLngBounds(center, center)
        const { paddingTopLeft, paddingBottomRight } = getTrackFitPadding()
        map.fitBounds(singleBounds, { paddingTopLeft, paddingBottomRight, maxZoom: 12, animate })
      } else {
        const { paddingTopLeft, paddingBottomRight } = getTrackFitPadding()
        map.fitBounds(bounds, { paddingTopLeft, paddingBottomRight, maxZoom: 12, animate })
      }
    }
    return true
  } catch (error) {
    console.error('Failed to fetch tracks:', error)
    return false
  }
}

/**
 * 计算轨迹视野的边距，避免被下方轨迹列表遮挡
 */
function getTrackFitPadding() {
  const basePadding = 40
  const listHeight = trackListRef.value?.offsetHeight || 0
  const bottomPadding = Math.max(basePadding, listHeight + 20)
  return {
    paddingTopLeft: [basePadding, basePadding] as L.PointExpression,
    paddingBottomRight: [basePadding, bottomPadding] as L.PointExpression
  }
}

/**
 * 创建船队标签图标
 * @param text 标签文本
 * @param company 公司名称
 * @param subText 次行文本
 * @returns Leaflet DivIcon
 */
function createCompanyTagIcon(text: string, company: string, subText?: string) {
  const color = getTagColor(company)
  const maxLen = Math.max(text.length, subText?.length || 0)
  const textWidth = maxLen * 8 + 16
  const height = subText ? 30 : 20
  const secondLine = subText ? `<div style="font-size: 10px; font-weight: 500; opacity: 0.9;">${subText}</div>` : ''
  
  return L.divIcon({
    className: 'company-tag-icon',
    html: `<div style="
      background: ${color.bg};
      color: ${color.text};
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
      white-space: nowrap;
      box-shadow: 0 2px 4px rgba(0,0,0,0.2);
      border: 1px solid rgba(255,255,255,0.3);
      backdrop-filter: blur(4px);
       display: flex;
       flex-direction: column;
       align-items: center;
       line-height: 1.2;
    "><div>${text}</div>${secondLine}</div>`,
    iconSize: [textWidth, height],
    iconAnchor: [-5, 10]
  })
}

const icons: Record<string, L.DivIcon> = {
  dredging: createIcon(statusColors.dredging),
  underway: createIcon(statusColors.underway),
  moored: createIcon(statusColors.moored),
  offline: createIcon(statusColors.offline)
}

/**
 * 判断是否为已配置MMSI的船舶
 */
function isTrackedVessel(vessel: Vessel): boolean {
  return Boolean(vessel.mmsi && vessel.mmsi.toString().trim())
}

async function fetchVessels() {
  loading.value = true
  try {
    const response = await fetch('/api/ships')
    const data = await response.json()
    vessels.value = data.ships || []
    stats.value.total = data.total || 0
    stats.value.active = data.tracked || 0
    
    const statusStats = { underway: 0, dredging: 0, moored: 0, offline: 0 }
    vessels.value.forEach(v => {
      if (isTrackedVessel(v)) {
        const key = getVesselStatusKey(v)
        if (key === 'underway') statusStats.underway++
        else if (key === 'dredging') statusStats.dredging++
        else if (key === 'moored') statusStats.moored++
        else if (key === 'offline') statusStats.offline++
      }
    })
    
    stats.value.underway = statusStats.underway
    stats.value.dredging = statusStats.dredging
    stats.value.moored = statusStats.moored
    stats.value.offline = statusStats.offline
    // stats.value.active is set from backend data.tracked
    
    renderMarkers()
    
    // Do NOT expand all groups initially (User requirement: Default collapsed)
    // activeKeys.value = Object.keys(groupedVessels.value)
  } catch (error) {
    console.error('Failed to fetch vessels:', error)
  } finally {
    loading.value = false
  }
}

function renderMarkers() {
  if (!map || !vesselLayerGroup || !tagLayerGroup) return
  
  vesselLayerGroup.clearLayers()
  tagLayerGroup.clearLayers()
  vesselMarkerMap.clear()
  
  const isCloseZoom = currentZoom.value >= 11

  vessels.value.forEach(v => {
    if (v.lat == null || v.lng == null) return
    if (!isTrackedVessel(v)) return
    
    const iconKey = getVesselStatusKey(v)
    const marker = L.marker([v.lat, v.lng], { icon: icons[iconKey] }).addTo(vesselLayerGroup!)
    bindPopup(marker, v, iconKey)
    if (v.mmsi) {
      vesselMarkerMap.set(v.mmsi, marker)
    }
    
    // Tag Logic
    const companyName = v.company || '其他'
    const tagText = isCloseZoom ? `${companyName}|${v.name}` : getCompanyAbbreviation(companyName)
    if (tagText) {
      const speedText = isCloseZoom ? formatSpeed(v.speed) : undefined
      const tagIcon = createCompanyTagIcon(tagText, companyName, speedText)
      const tagMarker = L.marker([v.lat, v.lng], { icon: tagIcon }).addTo(tagLayerGroup!)
      bindPopup(tagMarker, v, iconKey)
    }
  })
}

function bindPopup(layer: L.Layer, v: Vessel, iconKey: string) {
    let timeStr = '未知'
    if (v.updated_at) {
      try {
        const date = new Date(v.updated_at)
        timeStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:00`
      } catch (e) {}
    }
    
    let locHtml = ''
    if (v.continent || v.country) {
      const continent = translateContinent(v.continent)
      const country = translateCountry(v.country)
      locHtml += `<div class="flex justify-between"><span class="text-gray-500">区域:</span> <span>${continent || '-'} / ${country || '-'}</span></div>`
    }
    
    if (!locHtml) {
      locHtml += `<div class="flex justify-between"><span class="text-gray-500">位置:</span> <span class="text-gray-600 italic">数据更新中...</span></div>`
    }
    
    const statusCN = translateStatusByKey(getVesselStatusKey(v))
    const statusClass = iconKey === 'dredging' ? 'text-blue-400 font-bold' : 
                      iconKey === 'underway' ? 'text-green-400' : iconKey === 'moored' ? 'text-red-400' : 'text-gray-400'
    
    const popupContent = document.createElement('div')
    popupContent.style.minWidth = '200px'
    popupContent.innerHTML = `
      <div class="font-bold text-white mb-2">${v.name}</div>
      <div class="flex justify-between mb-1">
        <span class="text-gray-500">状态:</span>
        <span class="${statusClass}">${statusCN}</span>
      </div>
      <div class="flex justify-between mb-1">
        <span class="text-gray-500">航速:</span>
        <span class="text-gray-300 font-mono">${v.speed !== null && v.speed !== undefined ? v.speed.toFixed(1) + ' 节' : '-'}</span>
      </div>
      ${v.company ? `<div class="flex justify-between mb-1"><span class="text-gray-500">船队:</span><span class="text-gray-300">${v.company}</span></div>` : ''}
      ${locHtml}
      <div class="flex justify-between mt-2 pt-2 border-t border-white/10">
        <span class="text-gray-500">更新时间:</span>
        <span class="text-gray-400 text-xs">${timeStr}</span>
      </div>
      <div class="mt-3 flex justify-center">
        <button id="track-btn-${v.mmsi}" class="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded transition-colors flex items-center gap-1">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
          显示3天轨迹
        </button>
      </div>
    `
    
    // 状态点可点击
    layer.bindPopup(popupContent, {
      className: 'dark-popup'
    })
    
    // 监听 popup 打开事件来绑定按钮点击
    layer.on('popupopen', () => {
      const btn = document.getElementById(`track-btn-${v.mmsi}`)
      if (btn) {
        btn.onclick = () => showTrack(v.mmsi)
      }
    })
}

/**
 * 根据窗口宽度调整侧边栏显示
 */
function updateSidebarForViewport() {
  if (window.innerWidth <= 768) {
    sidebarOpen.value = false
  } else {
    sidebarOpen.value = true
  }
  scheduleMapResize()
}

onMounted(async () => {
  if (!mapContainer.value) return
  
  map = L.map(mapContainer.value, {
    center: [25, 110],
    zoom: 3,
    maxZoom: 18,
    zoomControl: false,
    attributionControl: false
  })
  
  const tiandituKey = '3f9084289bc4ee4f8b5ab359f46bc856'
  const baseUrl = `https://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${tiandituKey}`
  const labelUrl = `https://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${tiandituKey}`
  const satUrl = `https://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${tiandituKey}`
  const satLabelUrl = `https://t{s}.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${tiandituKey}`
  L.tileLayer(baseUrl, {
    subdomains: ['0', '1', '2', '3', '4', '5', '6', '7'],
    maxZoom: 18,
    minZoom: 2,
    keepBuffer: 3,
    className: 'tianditu-vector-layer'
  }).addTo(map)
  L.tileLayer(labelUrl, {
    subdomains: ['0', '1', '2', '3', '4', '5', '6', '7'],
    maxZoom: 18,
    minZoom: 2,
    keepBuffer: 3,
    className: 'tianditu-vector-layer'
  }).addTo(map)
  L.tileLayer(satUrl, {
    subdomains: ['0', '1', '2', '3', '4', '5', '6', '7'],
    maxZoom: 18,
    minZoom: 6,
    keepBuffer: 3,
    className: 'tianditu-satellite-layer'
  }).addTo(map)
  L.tileLayer(satLabelUrl, {
    subdomains: ['0', '1', '2', '3', '4', '5', '6', '7'],
    maxZoom: 18,
    minZoom: 6,
    keepBuffer: 3,
    className: 'tianditu-satellite-layer'
  }).addTo(map)
  
  vesselLayerGroup = L.layerGroup().addTo(map)
  tagLayerGroup = L.layerGroup().addTo(map)
  trackLayerGroup = L.layerGroup().addTo(map)
  measureLayerGroup = L.layerGroup().addTo(map)
  
  map.on('click', onMapClick)
  map.on('contextmenu', onMapRightClick)
  map.on('mousemove', onMapMouseMove)

  map.on('zoomend', () => {
    if (!map) return
    currentZoom.value = map.getZoom()
    renderMarkers()
  })

  updateSidebarForViewport()
  window.addEventListener('resize', updateSidebarForViewport)

  await nextTick()
  map.invalidateSize()
  
  try {
    const res = await fetch('/static/continents.geojson')
    const data = await res.json()
    L.geoJSON(data, {
      style: {
        color: '#475569',
        weight: 1.5,
        opacity: 0.8,
        fillOpacity: 0
      }
    }).addTo(map)
  } catch (err) {
    console.error('Failed to load continents:', err)
  }
  
  await fetchVessels()
})

onUnmounted(() => {
  window.removeEventListener('resize', updateSidebarForViewport)
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<style scoped>
:deep(.glass-card) {
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
}

:deep(.leaflet-container) {
  background: #0f172a;
}

:deep(.tianditu-satellite-layer) {
  filter: none;
}

:deep(.leaflet-popup-content-wrapper) {
  background: rgba(30, 41, 59, 0.95);
  backdrop-filter: blur(8px);
  color: #fff;
  border: 1px solid rgba(255,255,255,0.1);
}

:deep(.leaflet-popup-tip) {
  background: rgba(30, 41, 59, 0.95);
}

:deep(.measure-popup .leaflet-popup-content-wrapper) {
  background: rgba(30, 41, 59, 0.5);
}

:deep(.measure-popup .leaflet-popup-tip) {
  background: rgba(30, 41, 59, 0.5);
}

:deep(.map-tooltip) {
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 2px 8px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
}

:deep(.leaflet-container a.leaflet-popup-close-button) {
  color: #fff;
}

:deep(.china-flag-marker) {
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.45));
}

:deep(.china-flag-marker svg) {
  display: block;
}

/* Ant Design Override for Dark Theme */
:deep(.ant-collapse-header) {
  color: #e5e7eb !important;
  padding: 8px 16px !important;
}

:deep(.ant-collapse-content-box) {
  padding: 8px !important;
  background-color: rgba(0, 0, 0, 0.2) !important;
}

:deep(.ant-collapse-item) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
}

:deep(.ant-collapse-item:last-child) {
  border-bottom: none !important;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

@media (max-width: 768px) {
  .vessel-sidebar {
    display: none !important;
  }
  .vessel-sidebar-toggle {
    display: none !important;
  }
}
</style>
