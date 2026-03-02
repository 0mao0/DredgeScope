<template>
  <a-config-provider :theme="themeConfig">
    <div class="h-screen w-screen overflow-hidden flex flex-col bg-[#0f172a] text-slate-200">
      <NavBar class="flex-shrink-0 z-50 relative mb-6" />
      <div class="flex-1 overflow-hidden relative min-h-0 w-full">
        <router-view />
      </div>
    </div>
  </a-config-provider>
</template>

<script setup lang="ts">
import { onMounted, provide, reactive } from 'vue'
import { theme } from 'ant-design-vue'
import { useNewsStore, useVesselStore } from '@/stores'
import NavBar from '@/components/NavBar.vue'

const newsStore = useNewsStore()
const vesselStore = useVesselStore()

const themeConfig = reactive({
  token: {
    colorPrimary: '#0ea5e9',
    colorBgContainer: '#1e293b',
    colorBgElevated: '#1e293b',
    colorBgLayout: '#0f172a',
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    colorBorder: '#334155',
    borderRadius: 8,
  },
  algorithm: theme.darkAlgorithm,
})

provide('theme', 'dark')

onMounted(() => {
  newsStore.fetchNews()
  vesselStore.fetchVessels()
})
</script>

<style>
/* Global styles */
</style>
