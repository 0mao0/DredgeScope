<template>
  <div class="min-h-screen">
    <!-- Navbar -->
    <NavBar />

    <!-- Main Content -->
    <main class="w-full px-4 sm:px-6 lg:px-8">
      <!-- Map Container -->
      <div class="relative">
        <div ref="mapContainer" class="glass-card" :style="{ height: 'calc(100vh - 140px)', width: '100%' }"></div>
      
        <!-- Search Box (Bottom Right) -->
        <div class="absolute bottom-6 right-6 z-[1000] flex gap-2">
          <div class="glass-card px-3 py-2 flex items-center gap-2 shadow-2xl">
            <input 
              v-model="searchQuery" 
              type="text" 
              placeholder="搜索船舶名称..." 
              class="bg-transparent border-none outline-none text-white text-sm w-40 sm:w-60 placeholder:text-gray-500"
              @keyup.enter="handleSearch"
            />
            <button @click="handleSearch" class="text-gray-400 hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Status Legend -->
        <div class="absolute top-4 right-4 z-[1000] glass-card px-3 py-2 rounded-xl flex flex-col gap-1 text-xs sm:text-sm">
          <div class="flex flex-wrap gap-x-4 gap-y-1">
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="text-gray-400">跟踪</span>
              <span class="text-white font-bold" title="24小时内有API动态的船舶">{{ stats.active }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="text-gray-400">总计</span>
              <span class="text-white font-bold">{{ stats.total }}</span>
            </div>
          </div>
          <div class="flex flex-wrap gap-x-4 gap-y-1 border-t border-white/10 pt-1">
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"></span>
              <span class="text-gray-300">施工中</span>
              <span class="text-blue-400 font-mono">{{ stats.dredging }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
              <span class="text-gray-300">航行中</span>
              <span class="text-green-400 font-mono">{{ stats.underway }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2">
              <span class="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]"></span>
              <span class="text-gray-300">停泊</span>
              <span class="text-yellow-400 font-mono">{{ stats.moored }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import NavBar from '@/components/NavBar.vue'

interface Vessel {
  id: string
  mmsi: string
  name: string
  status: string
  lat: number
  lng: number
  country: string
  continent?: string
  province?: string
  city?: string
  updated_at?: string
  company?: string
}

const mapContainer = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let trackLayer: L.Polyline | null = null

const vessels = ref<Vessel[]>([])
const searchQuery = ref('')
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
const countryColors: Record<string, { bg: string, text: string }> = {
  'China': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'CN': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  '中国': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'Netherlands': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'NL': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'Singapore': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'SG': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'United States': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'US': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'USA': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'United Kingdom': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'UK': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'GB': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'Japan': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'JP': { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  'Korea': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'KR': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'South Korea': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'Germany': { bg: 'rgba(220, 38, 38, 0.4)', text: '#1f2937' },
  'DE': { bg: 'rgba(220, 38, 38, 0.4)', text: '#1f2937' },
  'France': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'FR': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'Australia': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' },
  'AU': { bg: 'rgba(37, 99, 235, 0.4)', text: 'white' }
}

/**
 * 中国船队的红色变体
 */
const chinaRedVariants = [
  { bg: 'rgba(220, 38, 38, 0.4)', text: 'white' },
  { bg: 'rgba(239, 68, 68, 0.4)', text: 'white' },
  { bg: 'rgba(185, 28, 28, 0.4)', text: 'white' },
  { bg: 'rgba(248, 113, 113, 0.4)', text: '#1f2937' },
  { bg: 'rgba(153, 27, 27, 0.4)', text: 'white' },
  { bg: 'rgba(252, 165, 165, 0.4)', text: '#1f2937' }
]

/**
 * 根据国家和公司名称生成颜色
 * @param country 国家名称
 * @param company 公司名称
 * @returns 颜色对象 { bg: string, text: string }
 */
function getTagColor(country: string | undefined, company: string | undefined): { bg: string, text: string } {
  const isChina = country === 'China' || country === 'CN' || country === '中国'
  
  if (isChina) {
    // 中国船队：红色基调，根据公司名称选择不同变体
    if (!company) {
      return chinaRedVariants[0]
    }
    let hash = 0
    for (let i = 0; i < company.length; i++) {
      hash = company.charCodeAt(i) + ((hash << 5) - hash)
    }
    const index = Math.abs(hash) % chinaRedVariants.length
    return chinaRedVariants[index]
  }
  
  // 其他国家：先看是否有国旗颜色映射
  if (country && countryColors[country]) {
    return countryColors[country]
  }
  
  // 默认蓝色
  return { bg: 'rgba(59, 130, 246, 0.4)', text: 'white' }
}

async function showTrack(mmsi: string) {
  if (!map) return
  
  // 清除旧轨迹
  if (trackLayer) {
    map.removeLayer(trackLayer)
    trackLayer = null
  }

  try {
    const response = await fetch(`/api/ship_tracks?mmsi=${mmsi}&days=3`)
    const tracks = await response.json()
    
    if (!tracks || tracks.length < 2) {
      alert('暂无轨迹数据')
      return
    }

    const latlngs = tracks.map((t: any) => [t.lat, t.lng])
    trackLayer = L.polyline(latlngs, {
      color: '#3b82f6',
      weight: 3,
      opacity: 0.8,
      dashArray: '5, 10'
    }).addTo(map)
    
    // 自动缩放到轨迹范围
    map.fitBounds(trackLayer.getBounds(), { padding: [50, 50] })
  } catch (error) {
    console.error('Failed to fetch tracks:', error)
  }
}

function handleSearch() {
  if (!searchQuery.value.trim() || !map) return
  
  const query = searchQuery.value.toLowerCase().trim()
  const vessel = vessels.value.find(v => v.name.toLowerCase().includes(query))
  
  if (vessel) {
    map.setView([vessel.lat, vessel.lng], 12, { animate: true })
    // 这里可以触发对应的 popup 弹出，但需要保存 marker 引用
  } else {
    alert('未找到该船舶')
  }
}

/**
 * 创建船队标签图标
 * @param text 标签文本
 * @param country 国家名称
 * @param company 公司名称
 * @returns Leaflet DivIcon
 */
function createCompanyTagIcon(text: string, country: string, company: string) {
  const color = getTagColor(country, company)
  const textWidth = text.length * 8 + 16
  
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
    ">${text}</div>`,
    iconSize: [textWidth, 20],
    iconAnchor: [-5, 10]
  })
}

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
    
    // 所有船舶都添加船队简称标签
    let tagMarker = null
    const companyAbbr = getCompanyAbbreviation(v.company)
    if (companyAbbr) {
      const tagIcon = createCompanyTagIcon(companyAbbr, v.country, v.company || '')
      tagMarker = L.marker([v.lat, v.lng], { icon: tagIcon }).addTo(map!)
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
    
    const popupContent = document.createElement('div')
    popupContent.style.minWidth = '200px'
    popupContent.innerHTML = `
      <div class="font-bold text-white mb-2">${v.name}</div>
      <div class="flex justify-between mb-1">
        <span class="text-gray-500">状态:</span>
        <span class="${statusClass}">${statusCN}</span>
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
    marker.bindPopup(popupContent, {
      className: 'dark-popup'
    })
    
    // 监听 popup 打开事件来绑定按钮点击
    marker.on('popupopen', () => {
      const btn = document.getElementById(`track-btn-${v.mmsi}`)
      if (btn) {
        btn.onclick = () => showTrack(v.mmsi)
      }
    })
    
    // Tag也可点击
    if (tagMarker) {
      tagMarker.bindPopup(popupContent, {
        className: 'dark-popup'
      })
      tagMarker.on('popupopen', () => {
        const btn = document.getElementById(`track-btn-${v.mmsi}`)
        if (btn) {
          btn.onclick = () => showTrack(v.mmsi)
        }
      })
    }
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
  
  // 使用高德地图暗色瓦片（wprd 接口比 webrd 更稳定）
  L.tileLayer('https://wprd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=8&x={x}&y={y}&z={z}', {
    subdomains: ['1', '2', '3', '4'],
    maxZoom: 18,
    minZoom: 3,
    attribution: '&copy; 高德地图',
    updateWhenIdle: true, // 仅在停止移动时更新，大幅减少请求被放弃 (ERR_ABORTED) 的情况
    keepBuffer: 2         // 保留更多缓存瓦片，减少白块
  }).addTo(map)
  
  try {
    const res = await fetch('/static/continents.geojson')
    const data = await res.json()
    L.geoJSON(data, {
      style: {
        color: '#475569', // 边界线条颜色
        weight: 1.5,      // 线条宽度
        opacity: 0.8,     // 线条不透明度
        fillOpacity: 0    // 完全透明，不填充颜色
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
