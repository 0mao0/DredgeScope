<template>
  <nav class="sticky top-0 z-40 w-full glass-card border-b border-white/5 mb-6">
    <div class="max-w-7xl mx-auto px-2 sm:px-4 lg:px-8">
      <div class="flex items-center justify-between h-14 sm:h-16">
        <div class="flex items-center gap-2">
          <router-link to="/" class="flex items-center gap-2">
            <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <i class="fa-solid fa-earth-americas text-white text-lg sm:text-xl"></i>
            </div>
            <div class="hidden sm:block">
              <h1 class="text-lg sm:text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                全球疏浚情报
              </h1>
            </div>
          </router-link>
        </div>
        <div class="flex items-center gap-2 md:gap-3">
          <router-link 
            to="/" 
            :class="[
              'flex items-center justify-center h-9 sm:h-10 w-9 sm:w-auto sm:min-w-24 md:min-w-28 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap transition-all',
              isActive('/') 
                ? 'bg-brand-500/20 border border-brand-500/30 text-brand-400' 
                : 'bg-white/5 border border-white/10 text-gray-200 hover:bg-white/10'
            ]"
          >
            <i class="fa-solid fa-chart-line text-sm"></i>
            <span class="hidden sm:inline ml-1.5">实时情报</span>
          </router-link>
          <router-link 
            to="/statistics" 
            :class="[
              'flex items-center justify-center h-9 sm:h-10 w-9 sm:w-auto sm:min-w-24 md:min-w-28 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap transition-all',
              isActive('/statistics') 
                ? 'bg-brand-500/20 border border-brand-500/30 text-brand-400' 
                : 'bg-white/5 border border-white/10 text-gray-200 hover:bg-white/10'
            ]"
          >
            <i class="fa-solid fa-chart-pie text-sm"></i>
            <span class="hidden sm:inline ml-1.5">统计分析</span>
          </router-link>
          <router-link 
            to="/history" 
            :class="[
              'flex items-center justify-center h-9 sm:h-10 w-9 sm:w-auto sm:min-w-24 md:min-w-28 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap transition-all',
              isActive('/history') 
                ? 'bg-brand-500/20 border border-brand-500/30 text-brand-400' 
                : 'bg-white/5 border border-white/10 text-gray-200 hover:bg-white/10'
            ]"
          >
            <i class="fa-solid fa-clock-rotate-left text-sm"></i>
            <span class="hidden sm:inline ml-1.5">历史新闻</span>
          </router-link>
          <router-link 
            to="/vessel-map" 
            target="_blank"
            class="flex items-center justify-center h-9 sm:h-10 w-9 sm:w-auto sm:min-w-24 md:min-w-28 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 hover:bg-cyan-500/20 transition-all text-xs sm:text-sm font-medium whitespace-nowrap"
          >
            <i class="fa-solid fa-ship text-sm"></i>
            <span class="hidden sm:inline ml-1.5">船舶跟踪</span>
          </router-link>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const isActive = (path: string) => {
  return route.path === path
}
</script>

<style scoped>
.glass-card {
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
