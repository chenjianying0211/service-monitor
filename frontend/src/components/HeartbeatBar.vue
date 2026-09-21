<template>
  <div class="hb" :style="{ '--n': slots }">
    <el-tooltip v-for="(b, i) in padded" :key="i" :disabled="!b" placement="top" :show-after="80">
      <template #content>
        <div v-if="b">
          <b>{{ b.ok ? '正常' : '失敗' }}</b> · {{ fmtTime(b.ts) }}<br />
          <span v-if="b.latency_ms != null">{{ b.latency_ms }} ms · </span>{{ b.message }}
        </div>
      </template>
      <span class="beat" :class="b ? (b.ok ? 'ok' : 'fail') : 'empty'"></span>
    </el-tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { fmtTime } from '../utils'

const props = defineProps({ beats: { type: Array, default: () => [] }, slots: { type: Number, default: 40 } })
const padded = computed(() => {
  const b = props.beats.slice(-props.slots)
  return [...Array(props.slots - b.length).fill(null), ...b]
})
</script>

<style scoped>
.hb { display: grid; grid-template-columns: repeat(var(--n), 1fr); gap: 2px; height: 26px; align-items: stretch; }
.beat { border-radius: 3px; display: block; transition: transform .1s; }
.beat:hover { transform: scaleY(1.15); }
.ok { background: var(--sm-up); }
.fail { background: var(--sm-down); }
.empty { background: var(--sm-border); }
</style>
