import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface NewsItem {
  id: string
  article_id?: string
  title?: string
  title_cn?: string
  summary?: string
  summary_cn?: string
  translation?: string
  category?: string
  tags?: string[]
  imageUrl?: string
  sourceUrl?: string
  source_name?: string
  source_type?: string
  publishDate?: string
  pub_date?: string
  summaryCN?: string
  vlDescription?: string
  vl_desc?: string
  article_title?: string
  article_url?: string
  screenshot_path?: string
  full_text_cn?: string
  contractor?: string
  client?: string
  location?: string
  project_name?: string
  amount?: string
  currency?: string
  content?: string
  time?: string
  created_at?: string
  updated_at?: string
  details?: Record<string, any>
  [key: string]: any
}

export interface VesselItem {
  id: string
  name: string
  type: string
  status: string
  lat: number
  lng: number
  country: string
  continent?: string
  province?: string
  city?: string
  lastUpdate?: string
  updated_at?: string
}

export const useNewsStore = defineStore('news', () => {
  const newsList = ref<NewsItem[]>([])
  const loading = ref(false)
  const currentNews = ref<NewsItem | null>(null)

  const currentCount = computed(() => newsList.value.length)
  const historyTotal = ref(0)

  const categories = ref({
    Market: { name: '市场动态', icon: 'fa-chart-line', color: '#3b82f6' },
    Bid: { name: '中标信息', icon: 'fa-gavel', color: '#eab308' },
    Project: { name: '项目信息', icon: 'fa-building', color: '#22c55e' },
    Equipment: { name: '设备修造', icon: 'fa-gears', color: '#f97316' },
    'R&D': { name: '科技研发', icon: 'fa-flask', color: '#a855f7' },
    Regulation: { name: '技术法规', icon: 'fa-scale-balanced', color: '#ef4444' }
  })

  const groupedNews = computed(() => {
    const grouped: Record<string, NewsItem[]> = {}
    for (const key in categories.value) {
      grouped[key] = newsList.value.filter(item => item.category === key)
    }
    return grouped
  })

  async function fetchNews() {
    loading.value = true
    try {
      const response = await fetch('/api/events')
      if (!response.ok) {
        console.error('Failed to fetch news:', response.status, response.statusText)
        newsList.value = []
        historyTotal.value = 0
        return
      }
      const data = await response.json()
      const rawEvents = data.events || []
      
      const invalidKeywords = ['dredging and maritime', '行业链接', '疏浚: 101', 'dredging 101']
      const filteredEvents = rawEvents.filter((item: NewsItem) => {
        const title = (item.title_cn || item.summary_cn || item.article_title || '').toLowerCase()
        return !invalidKeywords.some(keyword => title.includes(keyword.toLowerCase()))
      })
      
      newsList.value = filteredEvents
      historyTotal.value = data.count || data.article_count || data.event_count || 0
    } catch (error) {
      console.error('Failed to fetch news:', error)
    } finally {
      loading.value = false
    }
  }

  function setCurrentNews(news: NewsItem | null) {
    currentNews.value = news
  }

  return {
    newsList,
    loading,
    currentNews,
    currentCount,
    historyTotal,
    categories,
    groupedNews,
    fetchNews,
    setCurrentNews
  }
})

export const useVesselStore = defineStore('vessel', () => {
  const vessels = ref<VesselItem[]>([])
  const loading = ref(false)
  const trackedCount = ref(0)
  const totalCount = ref(0)

  const vesselsByStatus = computed(() => ({
    dredging: vessels.value.filter(v => v.status === 'dredging').length,
    underway: vessels.value.filter(v => v.status === 'underway').length,
    moored: vessels.value.filter(v => v.status === 'moored').length
  }))

  async function fetchVessels() {
    loading.value = true
    try {
      const response = await fetch('/api/ships')
      if (!response.ok) {
        console.error('Failed to fetch vessels:', response.status, response.statusText)
        vessels.value = []
        trackedCount.value = 0
        totalCount.value = 0
        return
      }
      const data = await response.json()
      vessels.value = data.ships || []
      trackedCount.value = data.visible || data.tracked || 0
      totalCount.value = data.total || 0
    } catch (error) {
      console.error('Failed to fetch vessels:', error)
    } finally {
      loading.value = false
    }
  }

  return {
    vessels,
    loading,
    trackedCount,
    totalCount,
    vesselsByStatus,
    fetchVessels
  }
})
