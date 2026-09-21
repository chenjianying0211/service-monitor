<template>
  <div ref="el" class="chart"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkAreaComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import dayjs from 'dayjs'

echarts.use([LineChart, GridComponent, TooltipComponent, MarkAreaComponent, DataZoomComponent, CanvasRenderer])

const props = defineProps({ points: { type: Array, default: () => [] } })
const el = ref()
let chart

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

function render() {
  if (!chart) return
  const accent = css('--sm-accent') || '#2563eb'
  const down = css('--sm-down') || '#dc2626'
  const muted = css('--sm-muted') || '#64748b'
  const border = css('--sm-border') || '#e5e7eb'
  // 連續失敗區段畫成紅色底
  const areas = []
  let start = null
  props.points.forEach((p, i) => {
    if (!p.ok && start === null) start = p.ts
    if ((p.ok || i === props.points.length - 1) && start !== null) {
      areas.push([{ xAxis: start }, { xAxis: p.ts }]); start = null
    }
  })
  chart.setOption({
    animation: false,
    grid: { left: 48, right: 16, top: 16, bottom: 56 },
    tooltip: {
      trigger: 'axis',
      formatter: (ps) => {
        const p = props.points[ps[0].dataIndex]
        return `${dayjs(p.ts).format('MM-DD HH:mm:ss')}<br/>${p.ok ? '✅ 正常' : '❌ 失敗'}　${p.latency_ms ?? '—'} ms<br/><span style="opacity:.75">${p.message || ''}</span>`
      },
    },
    xAxis: {
      type: 'time', axisLine: { lineStyle: { color: border } },
      axisLabel: { color: muted, hideOverlap: true, formatter: (v) => dayjs(v).format('MM/DD HH:mm') },
    },
    yAxis: {
      type: 'value', name: 'ms', nameTextStyle: { color: muted },
      axisLabel: { color: muted }, splitLine: { lineStyle: { color: border, type: 'dashed' } },
    },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 10 }],
    series: [{
      type: 'line', showSymbol: false, smooth: 0.2, sampling: 'lttb',
      lineStyle: { width: 1.6, color: accent },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: accent + '55' }, { offset: 1, color: accent + '05' }]) },
      data: props.points.map((p) => [p.ts, p.latency_ms]),
      markArea: { silent: true, itemStyle: { color: down + '26' }, data: areas },
    }],
  }, true)
}

const ro = new ResizeObserver(() => chart?.resize())
onMounted(() => { chart = echarts.init(el.value); ro.observe(el.value); render() })
onBeforeUnmount(() => { ro.disconnect(); chart?.dispose() })
watch(() => props.points, render)
</script>

<style scoped>
.chart { width: 100%; height: 300px; }
</style>
