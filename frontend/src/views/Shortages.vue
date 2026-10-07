<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const rows = ref<any[]>([])
const stats = ref<any>({})
const mode = ref<string>('')

const TYPE_LABELS: Record<string, string> = { '': '不区分', fresh: '鲜品', frozen: '冻品' }
const MODE_LABELS: Record<string, string> = { no_substitute: '禁替', allow_frozen: '允许冻顶' }

onMounted(async () => {
  const res = await api('/prep/shortages')
  rows.value = res.shortages
  stats.value = res.stats
  mode.value = res.mode
})
</script>

<template>
  <h1>缺料便利贴</h1>
  <p class="sub">当前有效单快照 · {{ MODE_LABELS[mode] ?? mode }} · 鲜缺只写鲜品不足</p>
  <div class="kp-shortage-sticky" style="max-width:360px;transform:rotate(-1deg);margin-bottom:1rem">
    <h2>⚠ 缺料 {{ stats.shortage_count }} · 合计 {{ stats.total_shortage_qty }}</h2>
    <div v-for="r in rows" :key="r.ingredient_id" class="kp-shortage-item">
      <span>{{ r.ingredient_name }} <span class="badge badge-bad">{{ r.note }}</span></span>
      <span class="kp-qty">−{{ r.shortage }} {{ r.unit }}</span>
    </div>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>原料</th><th>标记</th><th>需求</th><th>鲜仓</th><th>冻仓</th><th>库存</th><th>鲜缺</th><th>冻顶</th><th>缺料</th><th>不足类型</th><th>单位</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.ingredient_id">
          <td>{{ r.ingredient_name }}</td>
          <td>{{ TYPE_LABELS[r.storage_type] }}</td>
          <td>{{ r.need_qty }}</td>
          <td>{{ r.storage_type === 'fresh' ? r.fresh_stock_qty : '—' }}</td>
          <td>{{ r.storage_type ? r.frozen_stock_qty : '—' }}</td>
          <td>{{ r.storage_type === '' ? r.stock_qty : '—' }}</td>
          <td>{{ r.storage_type === 'fresh' ? r.fresh_shortage : '—' }}</td>
          <td>{{ r.frozen_cover > 0 ? r.frozen_cover : '—' }}</td>
          <td><span class="badge badge-bad">{{ r.shortage }}</span></td>
          <td>{{ r.note }}</td>
          <td>{{ r.unit }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
