<template>
  <div class="ship-track-progress" @mouseenter="isHovering = true" @mouseleave="isHovering = false">
    <div class="time-range-selector flex items-center gap-2 mb-3">
      <span class="text-xs text-gray-400">时间范围:</span>
      <div class="flex gap-1">
        <button
          v-for="opt in timeRangeOptions"
          :key="opt.value"
          class="px-2 py-0.5 rounded text-xs transition-colors"
          :class="modelValue.days === opt.value ? 'bg-blue-500/70 text-white' : 'bg-white/10 text-gray-300 hover:bg-white/20'"
          @click="onDaysChange(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <div class="progress-wrapper relative" ref="progressContainerRef">
      <div
        class="speed-chart absolute inset-x-0 overflow-hidden rounded"
        :style="{ height: chartHeight + 'px', bottom: trackAreaHeight + 'px' }"
      >
        <svg class="w-full h-full" :viewBox="`0 0 ${chartWidth} ${chartHeight}`" preserveAspectRatio="none">
          <defs>
            <linearGradient id="speedGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="rgba(59, 130, 246, 0.5)" />
              <stop offset="100%" stop-color="rgba(59, 130, 246, 0.1)" />
            </linearGradient>
          </defs>
          <path :d="speedAreaPath" fill="url(#speedGradient)" />
          <path
            :d="speedLinePath"
            fill="none"
            stroke="#3b82f6"
            stroke-width="1.5"
            vector-effect="non-scaling-stroke"
          />
        </svg>
      </div>

      <div
        class="track-area absolute inset-x-0 cursor-pointer"
        :style="{ height: trackAreaHeight + 'px', bottom: '0px' }"
        @mousedown="startSeek"
        @touchstart="startSeek"
        @mousemove="onTrackHover"
        @mouseleave="isHovering = false"
      >
        <div class="status-bars absolute inset-x-0 bottom-0 flex h-2">
          <div
            v-for="(segment, idx) in statusSegments"
            :key="idx"
            class="status-segment h-full"
            :class="segment.status"
            :style="{ width: segment.width + '%' }"
          ></div>
        </div>

        <div
          class="progress-played absolute left-0 bottom-0 h-2 transition-all duration-75"
          :class="currentStatusClass"
          :style="{ width: playedWidth + '%' }"
        ></div>

        <div
          class="progress-handle absolute transform -translate-x-1/2 translate-y-1/2 cursor-pointer z-20"
          :class="{ 'is-playing': isPlaying }"
          :style="{ left: playedWidth + '%', bottom: '4px' }"
          @mousedown.stop="startSeek"
          @touchstart.stop="startSeek"
        >
          <div
            class="handle-ball rounded-full shadow-lg flex items-center justify-center"
            :class="currentStatusClass"
            :style="{ width: handleSize + 'px', height: handleSize + 'px' }"
          >
            <div class="handle-inner bg-white/90 rounded-full"></div>
          </div>
          <div
            v-if="isHovering || isSeeking"
            class="handle-tooltip absolute bottom-full transform -translate-x-1/2 mb-2 px-2 py-1.5 rounded text-xs whitespace-nowrap z-30"
            :class="currentStatusClass"
          >
            <div class="text-center font-medium">{{ formatDateTime(currentPointTime) }}</div>
            <div class="text-center font-semibold mt-0.5">{{ getStatusText(currentStatus) }}</div>
          </div>
        </div>

        <div
          v-if="isHovering && !isSeeking"
          class="seek-preview absolute bottom-full transform -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800/95 rounded text-xs text-white whitespace-nowrap z-10"
          :style="{ left: Math.max(10, Math.min(seekPosition, 90)) + '%' }"
        >
          <div class="text-center">{{ formatDateTime(previewTime) }}</div>
        </div>
      </div>
    </div>

    <div class="progress-controls flex items-center justify-between mt-3">
      <div class="flex items-center gap-3">
        <button
          class="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
          :class="isPlaying ? 'bg-white/20 hover:bg-white/30' : 'bg-blue-500/60 hover:bg-blue-500/80'"
          @click="togglePlay"
        >
          <i :class="isPlaying ? 'fa-solid fa-pause' : 'fa-solid fa-play'" class="text-sm ml-0.5"></i>
        </button>

        <div class="time-display flex items-center gap-1 text-xs text-gray-300">
          <span>{{ currentPointTime ? formatDateTime(currentPointTime) : '--:--' }}</span>
          <span class="text-gray-500">/</span>
          <span class="text-gray-400">{{ formatDateTime(timeRangeEnd) }}</span>
        </div>
      </div>

      <div class="speed-controls flex items-center gap-2">
        <span class="text-xs text-gray-400">倍速:</span>
        <select
          v-model="playbackSpeed"
          class="bg-slate-800/50 border border-white/10 rounded px-2 py-0.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
        >
          <option :value="0.5">0.5x</option>
          <option :value="1">1x</option>
          <option :value="1.5">1.5x</option>
          <option :value="2">2x</option>
          <option :value="3">3x</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'

interface TrackPoint {
  lat: number
  lng: number
  timestamp?: string
  speed?: number
  status?: 'dredging' | 'underway' | 'moored'
}

const props = defineProps<{
  points: TrackPoint[]
  modelValue: {
    days: number
  }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: { days: number }): void
  (e: 'timeChange', days: number): void
  (e: 'positionChange', point: TrackPoint | null): void
}>()

const timeRangeOptions = [
  { label: '1天', value: 1 },
  { label: '3天', value: 3 },
  { label: '5天', value: 5 },
  { label: '10天', value: 10 }
]

const chartHeight = 36
const chartWidth = 1000
const trackAreaHeight = 28
const handleSize = 16

const progressContainerRef = ref<HTMLDivElement | null>(null)
const isHovering = ref(false)
const isSeeking = ref(false)
const isPlaying = ref(false)
const seekPosition = ref(0)

const playbackSpeed = ref(1)
const defaultDuration = 15

const playedIndex = ref(0)
const playProgress = ref(0)

let playInterval: number | null = null
let animationFrameId: number | null = null
let lastTimestamp: number = 0

const timeRangeEnd = computed(() => {
  if (!props.points || props.points.length === 0) return ''
  const lastPoint = props.points[props.points.length - 1]
  return lastPoint?.timestamp || ''
})

const playedWidth = computed(() => {
  if (props.points.length <= 1) return 0
  const progress = isPlaying.value ? playProgress.value : playedIndex.value / (props.points.length - 1)
  return Math.min(progress * 100, 100)
})

const statusSegments = computed(() => {
  if (!props.points || props.points.length < 2) return []

  const segments: { width: number; status: string }[] = []
  let currentStatus = props.points[0].status || 'underway'
  let startIndex = 0

  for (let i = 1; i < props.points.length; i++) {
    const status = props.points[i].status || 'underway'
    if (status !== currentStatus) {
      segments.push({
        width: ((i - startIndex) / (props.points.length - 1)) * 100,
        status: currentStatus
      })
      currentStatus = status
      startIndex = i
    }
  }

  segments.push({
    width: ((props.points.length - startIndex) / (props.points.length - 1)) * 100,
    status: currentStatus
  })

  return segments
})

const currentPointTime = computed(() => {
  if (!props.points || props.points.length === 0) return ''
  const point = props.points[Math.min(playedIndex.value, props.points.length - 1)]
  return point?.timestamp || ''
})

const currentPointSpeed = computed(() => {
  if (!props.points || props.points.length === 0) return 0
  const point = props.points[Math.min(playedIndex.value, props.points.length - 1)]
  return point?.speed || 0
})

const currentStatus = computed(() => {
  if (!props.points || props.points.length === 0) return 'underway'
  const point = props.points[Math.min(playedIndex.value, props.points.length - 1)]
  return point?.status || 'underway'
})

const currentStatusClass = computed(() => {
  const map: Record<string, string> = {
    dredging: 'bg-blue-500',
    underway: 'bg-green-500',
    moored: 'bg-red-500'
  }
  return map[currentStatus.value] || 'bg-blue-500'
})

const speedLinePath = computed(() => {
  if (!props.points || props.points.length < 2) return ''

  const maxSpeed = Math.max(...props.points.map((p) => p.speed || 0), 10)
  const points: string[] = []

  props.points.forEach((p, i) => {
    const x = (i / (props.points.length - 1)) * chartWidth
    const y = chartHeight - ((p.speed || 0) / maxSpeed) * (chartHeight - 4) - 2
    points.push(`${i === 0 ? 'M' : 'L'}${x},${y}`)
  })

  return points.join(' ')
})

const speedAreaPath = computed(() => {
  if (!props.points || props.points.length < 2) return ''

  const maxSpeed = Math.max(...props.points.map((p) => p.speed || 0), 10)
  const points: string[] = []

  props.points.forEach((p, i) => {
    const x = (i / (props.points.length - 1)) * chartWidth
    const y = chartHeight - ((p.speed || 0) / maxSpeed) * (chartHeight - 4) - 2
    points.push(`${i === 0 ? 'M' : 'L'}${x},${y}`)
  })

  const lastX = chartWidth
  const firstX = 0
  points.push(`L${lastX},${chartHeight}`)
  points.push(`L${firstX},${chartHeight}`)
  points.push('Z')

  return points.join(' ')
})

const previewTime = computed(() => {
  if (!props.points || props.points.length < 2) return ''
  const index = Math.round((seekPosition.value / 100) * (props.points.length - 1))
  const point = props.points[Math.min(index, props.points.length - 1)]
  return point?.timestamp || ''
})

watch(playedIndex, (newIndex) => {
  if (props.points && props.points.length > 0) {
    const point = props.points[Math.min(newIndex, props.points.length - 1)]
    emit('positionChange', point || null)
  }
})

function onTrackHover(e: MouseEvent) {
  if (!progressContainerRef.value) return
  const rect = progressContainerRef.value.getBoundingClientRect()
  const percent = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100))
  seekPosition.value = percent
}

function startSeek(e: MouseEvent | TouchEvent) {
  e.preventDefault()
  isSeeking.value = true
  isHovering.value = false
  if (isPlaying.value) {
    stopPlayback()
  }

  const handleMove = (e: MouseEvent | TouchEvent) => {
    if (!progressContainerRef.value) return
    const rect = progressContainerRef.value.getBoundingClientRect()
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    const percent = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100))
    seekPosition.value = percent

    if (props.points.length > 1) {
      const index = Math.round((percent / 100) * (props.points.length - 1))
      playedIndex.value = index
      playProgress.value = percent / 100
    }
  }

  const handleUp = () => {
    isSeeking.value = false
    document.removeEventListener('mousemove', handleMove)
    document.removeEventListener('mouseup', handleUp)
    document.removeEventListener('touchmove', handleMove)
    document.removeEventListener('touchend', handleUp)
  }

  document.addEventListener('mousemove', handleMove)
  document.addEventListener('mouseup', handleUp)
  document.addEventListener('touchmove', handleMove)
  document.addEventListener('touchend', handleUp)
}

function togglePlay() {
  isPlaying.value = !isPlaying.value

  if (isPlaying.value) {
    startPlayback()
  } else {
    stopPlayback()
  }
}

function startPlayback() {
  if (playInterval) clearInterval(playInterval)
  if (animationFrameId) cancelAnimationFrame(animationFrameId)

  const duration = (defaultDuration / playbackSpeed.value) * 1000
  lastTimestamp = performance.now()
  playProgress.value = playedIndex.value / Math.max(props.points.length - 1, 1)

  function animate(timestamp: number) {
    if (!isPlaying.value) return

    const elapsed = timestamp - lastTimestamp
    const pointsCount = Math.max(props.points.length - 1, 1)
    const increment = (elapsed / duration) * pointsCount

    playProgress.value = Math.min(playProgress.value + increment / pointsCount, 1)
    playedIndex.value = Math.min(Math.floor(playProgress.value * pointsCount), pointsCount)
    lastTimestamp = timestamp

    if (playProgress.value >= 1) {
      stopPlayback()
      isPlaying.value = false
      playProgress.value = 1
      playedIndex.value = props.points.length - 1
      return
    }

    animationFrameId = requestAnimationFrame(animate)
  }

  animationFrameId = requestAnimationFrame(animate)
}

function stopPlayback() {
  if (playInterval) {
    clearInterval(playInterval)
    playInterval = null
  }
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
}

watch(playbackSpeed, () => {
  if (isPlaying.value) {
    stopPlayback()
    startPlayback()
  }
})

function onDaysChange(days: number) {
  playedIndex.value = 0
  emit('update:modelValue', { days })
  emit('timeChange', days)
}

function formatDateTime(timestamp: string): string {
  if (!timestamp) return '--:--'
  try {
    const date = new Date(timestamp)
    const month = (date.getMonth() + 1).toString().padStart(2, '0')
    const day = date.getDate().toString().padStart(2, '0')
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${month}-${day} ${hours}:${minutes}`
  } catch {
    return '--:--'
  }
}

function getStatusText(status: string): string {
  const map: Record<string, string> = {
    dredging: '施工',
    underway: '航行',
    moored: '停泊'
  }
  return map[status] || status
}

onUnmounted(() => {
  stopPlayback()
  emit('positionChange', null)
})
</script>

<style scoped>
.ship-track-progress {
  padding: 12px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
}

.progress-wrapper {
  position: relative;
  height: 68px;
}

.progress-container {
  background: rgba(30, 41, 59, 0.8);
  border-radius: 4px;
  overflow: visible;
  cursor: pointer;
}

.status-segment {
  transition: opacity 0.2s;
}

.status-segment.dredging {
  background: rgba(59, 130, 246, 0.6);
}

.status-segment.underway {
  background: rgba(34, 197, 94, 0.6);
}

.status-segment.moored {
  background: rgba(239, 68, 68, 0.6);
}

.speed-chart {
  pointer-events: none;
}

.progress-handle {
  transition: left 0.1s ease-out;
}

.progress-handle.is-playing .handle-ball {
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.15);
  }
}

.handle-ball {
  border: 2px solid rgba(255, 255, 255, 0.9);
  transition: transform 0.15s ease;
}

.handle-inner {
  width: 35%;
  height: 35%;
}

.handle-tooltip {
  border: 1px solid rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(8px);
  min-width: 80px;
}

.handle-tooltip.bg-blue-500 {
  background: rgba(59, 130, 246, 0.95);
}

.handle-tooltip.bg-green-500 {
  background: rgba(34, 197, 94, 0.95);
}

.handle-tooltip.bg-red-500 {
  background: rgba(239, 68, 68, 0.95);
}

.seek-preview {
  pointer-events: none;
}
</style>
