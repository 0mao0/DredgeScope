<template>
  <div class="ship-track-progress" style="min-height: 90px;">
    <div class="time-range-selector flex items-center justify-between gap-2 mb-3">
      <div class="flex items-center gap-2">
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
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-400">底图等级:</span>
        <select
          :value="modelValue.zoomLevel"
          @change="onZoomLevelChange(($event.target as HTMLSelectElement).value)"
          class="bg-slate-800/50 border border-white/10 rounded px-2 py-0.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
        >
          <option v-for="level in zoomLevelOptions" :key="level" :value="level">{{ level }}</option>
        </select>
      </div>
    </div>

    <div class="progress-wrapper relative" ref="progressContainerRef">
      <div
        class="speed-chart absolute inset-x-0 overflow-hidden rounded"
        :style="{ height: chartHeight + 'px', bottom: trackAreaHeight + 'px' }"
      >
        <svg class="w-full h-full" :viewBox="`0 0 ${chartWidth} ${chartHeight}`" preserveAspectRatio="none">
          <path
            v-for="(segment, idx) in speedSegmentPaths"
            :key="idx"
            :d="segment.linePath"
            fill="none"
            :class="'stroke-' + segment.status"
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
        <div class="status-bars absolute inset-x-0 bottom-0 flex h-1.5">
          <div
            v-for="(segment, idx) in statusSegments"
            :key="idx"
            class="status-segment h-full"
            :class="[segment.status, { 'is-active': idx === activeSegmentIndex }]"
            :style="{ width: segment.width + '%' }"
          ></div>
        </div>

        <div
          class="progress-handle absolute transform -translate-x-1/2 translate-y-1/2 cursor-pointer z-20"
          :class="{ 'is-playing': isPlaying }"
          :style="{ left: playedWidth + '%', bottom: '3px' }"
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
            v-if="isHovering || isSeeking || isPlaying"
            class="handle-tooltip absolute bottom-full transform -translate-x-1/2 mb-2 px-2 py-1.5 rounded text-xs whitespace-nowrap z-30"
            :class="currentStatusClass"
          >
            <div class="text-center font-medium">{{ formatDateTime(currentPointTime) }}</div>
            <div class="text-center font-semibold mt-0.5">{{ getStatusText(currentStatus) }}{{ currentSpeedText }}</div>
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
        <span class="text-xs text-gray-400">播放时长:</span>
        <select
          :value="playbackDuration"
          @change="onDurationChange(($event.target as HTMLSelectElement).value)"
          class="bg-slate-800/50 border border-white/10 rounded px-2 py-0.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
        >
          <option :value="5">5秒</option>
          <option :value="10">10秒</option>
          <option :value="15">15秒</option>
          <option :value="30">30秒</option>
          <option :value="60">60秒</option>
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
    zoomLevel?: number
  }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: { days: number; zoomLevel?: number }): void
  (e: 'timeChange', days: number): void
  (e: 'zoomLevelChange', level: number): void
  (e: 'positionChange', point: TrackPoint | null): void
}>()

const timeRangeOptions = [
  { label: '1天', value: 1 },
  { label: '3天', value: 3 },
  { label: '5天', value: 5 },
  { label: '10天', value: 10 }
]

const zoomLevelOptions = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

const chartHeight = 16
const chartWidth = 1000
const trackAreaHeight = 12
const handleSize = 10

const progressContainerRef = ref<HTMLDivElement | null>(null)
const isHovering = ref(false)
const isSeeking = ref(false)
const isPlaying = ref(false)
const seekPosition = ref(0)

const playbackDuration = ref(60)

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

const activeSegmentIndex = computed(() => {
  const segments = statusSegments.value
  if (!segments || segments.length === 0) return -1
  
  let accumulatedWidth = 0
  const currentPos = playedWidth.value
  
  for (let i = 0; i < segments.length; i++) {
    const segmentWidth = segments[i]?.width || 0
    if (currentPos >= accumulatedWidth && currentPos < accumulatedWidth + segmentWidth) {
      return i
    }
    accumulatedWidth += segmentWidth
  }
  return segments.length - 1
})

const currentSpeed = computed(() => {
  if (!props.points || props.points.length === 0) return 0
  const point = props.points[Math.min(playedIndex.value, props.points.length - 1)]
  return point?.speed || 0
})

const currentSpeedText = computed(() => {
  const speed = currentSpeed.value
  if (speed <= 0) return ''
  const knots = (speed * 1.94384).toFixed(1)
  return ` ${knots}节`
})

const speedSegmentPaths = computed(() => {
  if (!props.points || props.points.length < 2) return []

  const maxSpeed = Math.max(...props.points.map((p) => p.speed || 0), 10)
  const segments: { linePath: string; areaPath: string; status: string }[] = []

  let currentStatus = props.points[0].status || 'underway'
  let startIndex = 0

  for (let i = 1; i <= props.points.length; i++) {
    const status = i < props.points.length ? (props.points[i].status || 'underway') : null

    if (status !== currentStatus || i === props.points.length) {
      const linePoints: string[] = []
      const areaPoints: string[] = []

      for (let j = startIndex; j <= i && j < props.points.length; j++) {
        const x = (j / (props.points.length - 1)) * chartWidth
        const y = chartHeight - ((props.points[j].speed || 0) / maxSpeed) * (chartHeight - 4) - 2
        if (j === startIndex) {
          linePoints.push(`M${x},${y}`)
          areaPoints.push(`M${x},${y}`)
        } else {
          linePoints.push(`L${x},${y}`)
          areaPoints.push(`L${x},${y}`)
        }
      }

      const endX = (Math.min(i, props.points.length - 1) / (props.points.length - 1)) * chartWidth
      const startX = (startIndex / (props.points.length - 1)) * chartWidth

      areaPoints.push(`L${endX},${chartHeight}`)
      areaPoints.push(`L${startX},${chartHeight}`)
      areaPoints.push('Z')

      segments.push({
        linePath: linePoints.join(' '),
        areaPath: areaPoints.join(' '),
        status: currentStatus
      })

      currentStatus = status || 'underway'
      startIndex = i
    }
  }

  return segments
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

  if (playProgress.value >= 1) {
    playProgress.value = 0
    playedIndex.value = 0
  }

  const duration = playbackDuration.value * 1000
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

function onDaysChange(days: number) {
  playedIndex.value = 0
  emit('update:modelValue', { days })
  emit('timeChange', days)
}

function onDurationChange(value: string) {
  playbackDuration.value = parseInt(value, 10)
}

function onZoomLevelChange(value: string) {
  const level = parseInt(value, 10)
  emit('update:modelValue', { days: props.modelValue.days, zoomLevel: level })
  emit('zoomLevelChange', level)
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
  min-height: 90px;
  flex-shrink: 0;
}

.progress-wrapper {
  position: relative;
  height: 30px;
  flex-shrink: 0;
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

.status-segment.is-active {
  opacity: 0.4;
}

.stroke-dredging {
  stroke: rgba(59, 130, 246, 0.9);
}

.stroke-underway {
  stroke: rgba(34, 197, 94, 0.9);
}

.stroke-moored {
  stroke: rgba(239, 68, 68, 0.9);
}

.speed-chart {
  pointer-events: none;
  margin-bottom: 0;
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
  background: rgba(59, 130, 246, 0.7);
}

.handle-tooltip.bg-green-500 {
  background: rgba(34, 197, 94, 0.7);
}

.handle-tooltip.bg-red-500 {
  background: rgba(239, 68, 68, 0.7);
}

.seek-preview {
  pointer-events: none;
}
</style>
