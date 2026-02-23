<template>
  <div class="h-screen flex flex-col overflow-hidden">
    <!-- Navbar -->
    <nav class="h-16 flex items-center justify-between px-6 border-b border-white/5 bg-slate-900/50 backdrop-blur-md z-50">
      <div class="flex items-center gap-4">
        <router-link to="/" class="w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors border border-white/10" title="返回首页">
          <i class="fa-solid fa-arrow-left text-white"></i>
        </router-link>
        <div>
          <h1 class="text-xl font-bold text-white flex items-center gap-2">
            <i class="fa-solid fa-earth-americas text-brand-500"></i>
            全球疏浚船舶分布 
            <span class="text-xs font-normal text-gray-500 ml-2 bg-slate-800 px-2 py-1 rounded border border-slate-700">AIS 实时模拟</span>
          </h1>
        </div>
      </div>
      <div class="flex gap-4 text-sm hidden md:flex">
        <div class="flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"></span>
          <span class="text-gray-300">施工中 (Dredging)</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
          <span class="text-gray-300">航行中 (Underway)</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-3 h-3 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]"></span>
          <span class="text-gray-300">停泊 (Moored)</span>
        </div>
      </div>
    </nav>

    <!-- Map Container -->
    <div class="flex-1 p-4 relative">
      <div ref="mapContainer" class="glass-card" :style="{ height: 'calc(100vh - 100px)', width: '100%' }"></div>
      
      <!-- Overlay Stats -->
      <div class="absolute top-8 right-8 z-[1000] glass-card p-4 rounded-xl w-64">
        <h3 class="text-sm font-bold text-white mb-3 border-b border-white/10 pb-2">船队状态监控</h3>
        <div class="space-y-3">
          <div class="flex justify-between items-center">
            <span class="text-xs text-gray-400">船队总数</span>
            <span class="text-sm font-bold text-white">{{ stats.total }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-gray-400">活跃 (地图展示)</span>
            <span class="text-sm font-bold text-white">{{ stats.active }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-gray-400">航行中 (Underway)</span>
            <span class="text-xs font-mono text-green-400">{{ stats.underway }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-gray-400">作业中 (Dredging)</span>
            <span class="text-xs font-mono text-blue-400">{{ stats.dredging }}</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-xs text-gray-400">停泊 (Moored)</span>
            <span class="text-xs font-mono text-yellow-400">{{ stats.moored }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

interface Vessel {
  id: string
  name: string
  status: string
  lat: number
  lng: number
  country: string
  continent?: string
  province?: string
  city?: string
  updated_at?: string
}

const mapContainer = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null

const vessels = ref<Vessel[]>([])
const stats = ref({
  total: 0,
  active: 0,
  underway: 0,
  dredging: 0,
  moored: 0
})

const statusColors: Record<string, string> = {
  dredging: '#3b82f6',
  underway: '#22c55e',
  moored: '#eab308'
}

function mapStatusToIconKey(status: string | undefined): string {
  if (!status) return 'moored'
  const s = status.toLowerCase()
  
  if (s === 'dredging') return 'dredging'
  if (s === 'underway using engine' || s === 'underway') return 'underway'
  if (s === 'moored' || s === 'at anchor') return 'moored'
  if (s === 'stopped') return 'moored'
  
  if (s.includes('施工') || s.includes('作业') || s.includes('疏浚')) return 'dredging'
  if (s.includes('操纵能力受限')) return 'dredging'
  if (s.includes('机动船在航')) return 'underway'
  if (s.includes('调遣')) return 'underway'
  if (s.includes('锚泊') || s.includes('系泊') || s.includes('停泊') || s.includes('停靠') || s.includes('抛锚')) return 'moored'
  
  return 'moored'
}

function translateStatus(status: string | undefined): string {
  if (!status) return '停泊'
  const s = status.toLowerCase()
  
  if (/[\u4e00-\u9fa5]/.test(status)) {
    if (s.includes('施工') || s.includes('作业') || s.includes('疏浚') || s.includes('操纵能力受限')) return '作业中'
    if (s.includes('航') || s.includes('在航') || s.includes('调遣')) return '航行中'
    if (s.includes('锚泊') || s.includes('系泊') || s.includes('停泊') || s.includes('停靠') || s.includes('抛锚')) return '停泊'
    return '停泊'
  }
  
  if (s === 'dredging') return '作业中'
  if (s === 'underway using engine' || s === 'underway') return '航行中'
  if (s === 'moored' || s === 'at anchor' || s === 'stopped' || s === 'unknown') return '停泊'
  return '停泊'
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

function translateLocation(str: string | undefined): string {
  if (!str) return ''
  const map: Record<string, string> = {
    'Liaoning': '辽宁', 'Guangdong': '广东', 'Guangzhou': '广州', 'Shenzhen': '深圳',
    'Shanghai': '上海', 'Beijing': '北京', 'Tianjin': '天津',
    'Zhejiang': '浙江', 'Hangzhou': '杭州', 'Ningbo': '宁波',
    'Jiangsu': '江苏', 'Nanjing': '南京',
    'Fujian': '福建', 'Xiamen': '厦门', 'Fuzhou': '福州',
    'Shandong': '山东', 'Qingdao': '青岛',
    'Hebei': '河北', 'Tangshan': '唐山',
    'Guangxi': '广西', 'Beihai': '北海',
    'Hainan': '海南', 'Haikou': '海口'
  }
  return map[str] || str
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

const chinaFlagSvg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="22" height="16" viewBox="0 0 22 16" aria-hidden="true">
    <rect width="22" height="16" rx="2" fill="#E11D48"/>
    <path fill="#FBBF24" d="M4.6 3.2l.6 1.7h1.8l-1.4 1.1.5 1.7-1.5-1-1.5 1 .6-1.7-1.4-1.1h1.7z"/>
    <path fill="#FBBF24" d="M7.6 2.3l.2.6h.6l-.5.4.2.6-.5-.4-.5.4.2-.6-.5-.4h.6z"/>
    <path fill="#FBBF24" d="M9.1 3.5l.2.6h.6l-.5.4.2.6-.5-.4-.5.4.2-.6-.5-.4h.6z"/>
  </svg>
`

const chinaFlagIcon = L.divIcon({
  className: 'china-flag-marker',
  html: chinaFlagSvg,
  iconSize: [22, 16],
  iconAnchor: [11, 16]
})

const icons: Record<string, L.DivIcon> = {
  dredging: createIcon(statusColors.dredging),
  underway: createIcon(statusColors.underway),
  moored: createIcon(statusColors.moored)
}

async function fetchVessels() {
  try {
    const response = await fetch('/api/ships')
    const data = await response.json()
    vessels.value = data.ships || []
    stats.value.total = data.total || 0
    
    const statusStats = { underway: 0, dredging: 0, moored: 0 }
    vessels.value.forEach(v => {
      const key = mapStatusToIconKey(v.status)
      if (key === 'underway') statusStats.underway++
      else if (key === 'dredging') statusStats.dredging++
      else if (key === 'moored') statusStats.moored++
    })
    
    stats.value.underway = statusStats.underway
    stats.value.dredging = statusStats.dredging
    stats.value.moored = statusStats.moored
    stats.value.active = statusStats.underway + statusStats.dredging + statusStats.moored
    
    renderMarkers()
  } catch (error) {
    console.error('Failed to fetch vessels:', error)
  }
}

function renderMarkers() {
  if (!map) return
  
  vessels.value.forEach(v => {
    const iconKey = mapStatusToIconKey(v.status)
    const marker = L.marker([v.lat, v.lng], { icon: icons[iconKey] }).addTo(map!)
    
    const isChina = v.country === 'China' || v.country === 'CN' || v.country === '中国'
    if (isChina) {
      L.marker([v.lat, v.lng], { icon: chinaFlagIcon, interactive: false, keyboard: false }).addTo(map!)
    }
    
    let timeStr = '未知'
    if (v.updated_at) {
      try {
        const date = new Date(v.updated_at)
        timeStr = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:00`
      } catch (e) {}
    }
    
    let locHtml = ''
    if (v.continent || v.country) {
      locHtml += `<div class="flex justify-between"><span class="text-gray-500">区域:</span> <span>${v.continent || '-'} / ${translateCountry(v.country)}</span></div>`
    }
    
    if ((v.country === 'China' || v.country === 'CN' || v.country === '中国') && (v.province || v.city)) {
      locHtml += `<div class="flex justify-between"><span class="text-gray-500">详情:</span> <span>${translateLocation(v.province)} ${translateLocation(v.city)}</span></div>`
    }
    
    if (!locHtml) {
      locHtml += `<div class="flex justify-between"><span class="text-gray-500">位置:</span> <span class="text-gray-600 italic">数据更新中...</span></div>`
    }
    
    const statusCN = translateStatus(v.status)
    const statusClass = iconKey === 'dredging' ? 'text-blue-400 font-bold' : 
                      iconKey === 'underway' ? 'text-green-400' : 'text-yellow-400'
    
    const popupContent = `
      <div style="min-width: 200px;">
        <div class="font-bold text-white mb-2">${v.name}</div>
        <div class="flex justify-between mb-1">
          <span class="text-gray-500">状态:</span>
          <span class="${statusClass}">${statusCN}</span>
        </div>
        ${locHtml}
        <div class="flex justify-between mt-2 pt-2 border-t border-white/10">
          <span class="text-gray-500">更新时间:</span>
          <span class="text-gray-400 text-xs">${timeStr}</span>
        </div>
      </div>
    `
    
    marker.bindPopup(popupContent, {
      className: 'dark-popup'
    })
  })
}

onMounted(async () => {
  if (!mapContainer.value) return
  
  map = L.map(mapContainer.value, {
    center: [25, 110],
    zoom: 3,
    zoomControl: false,
    attributionControl: false
  })
  
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd'
  }).addTo(map)
  
  try {
    const res = await fetch('/static/continents.geojson')
    const data = await res.json()
    L.geoJSON(data, {
      style: {
        color: '#94a3b8',
        weight: 1,
        opacity: 0.5,
        fillColor: '#cbd5e1',
        fillOpacity: 0.1
      }
    }).addTo(map)
  } catch (err) {
    console.error('Failed to load continents:', err)
  }
  
  await fetchVessels()
})

onUnmounted(() => {
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

:deep(.leaflet-popup-content-wrapper) {
  background: rgba(30, 41, 59, 0.95);
  backdrop-filter: blur(8px);
  color: #fff;
  border: 1px solid rgba(255,255,255,0.1);
}

:deep(.leaflet-popup-tip) {
  background: rgba(30, 41, 59, 0.95);
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
</style>
