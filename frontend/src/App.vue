<template>
  <a-config-provider :theme="themeConfig">
    <router-view />
  </a-config-provider>
</template>

<script setup lang="ts">
import { onMounted, provide, reactive } from 'vue'
import { theme } from 'ant-design-vue'
import { useNewsStore, useVesselStore } from '@/stores'

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
#app {
  min-height: 100vh;
}
</style>
