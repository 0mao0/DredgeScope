import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '全球疏浚情报' }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/History.vue'),
    meta: { title: '历史新闻' }
  },
  {
    path: '/statistics',
    name: 'Statistics',
    component: () => import('@/views/Statistics.vue'),
    meta: { title: '统计分析' }
  },
  {
    path: '/vessel-map',
    name: 'VesselMap',
    component: () => import('@/views/VesselMap.vue'),
    meta: { title: '全球船舶跟踪' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
