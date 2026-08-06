<template>
  <div class="h-full flex flex-col overflow-hidden p-4">
    <main class="flex-1 overflow-y-auto custom-scrollbar space-y-6">
      <!-- Tabs -->
      <div class="glass-card rounded-2xl p-5">
        <a-tabs v-model:activeKey="activeTab" class="statistics-tabs">
          <a-tab-pane key="source" tab="来源分析">
            <SourceAnalysisTab />
          </a-tab-pane>
          <a-tab-pane key="company" tab="公司运营">
            <CompanyOperationsTab />
          </a-tab-pane>
          <a-tab-pane key="industry">
            <template #tab>
              <span class="industry-tab">
                行业动向
                <span class="ai-text">AI</span>
              </span>
            </template>
            <IndustryTrendsTab />
          </a-tab-pane>
        </a-tabs>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import SourceAnalysisTab from '../components/SourceAnalysisTab.vue'
import CompanyOperationsTab from '../components/CompanyOperationsTab.vue'
import IndustryTrendsTab from '../components/IndustryTrendsTab.vue'

const activeTab = ref('source')
</script>

<style scoped>
.glass-card {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.statistics-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
}
.statistics-tabs :deep(.ant-tabs-tab) {
  font-size: 15px;
  padding: 10px 20px;
}
.statistics-tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: var(--color-brand-500) !important;
}
.statistics-tabs :deep(.ant-tabs-ink-bar) {
  background: var(--color-brand-500);
}

/* tab标签上的AI特效字 */
.industry-tab {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ai-text {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1px;
  padding: 1px 6px;
  border-radius: 6px;
  color: #fff;
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  box-shadow: 0 0 10px rgba(139, 92, 246, 0.6);
  animation: ai-glow 1.6s ease-in-out infinite;
}
@keyframes ai-glow {
  0%, 100% {
    box-shadow: 0 0 6px rgba(139, 92, 246, 0.4);
  }
  50% {
    box-shadow: 0 0 14px rgba(139, 92, 246, 0.9);
  }
}
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}
</style>
