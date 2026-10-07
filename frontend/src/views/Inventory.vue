<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const rows = ref<any[]>([])
const allowFrozen = ref(false)
const saving = ref(false)
const error = ref('')
const saved = ref(false)

async function load() {
  const [items, settings] = await Promise.all([
    api('/inventory'),
    api('/inventory/settings'),
  ])
  rows.value = items
  allowFrozen.value = settings.allow_frozen_substitute
}

async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const res = await api('/inventory/settings', {
      method: 'PUT',
      body: JSON.stringify({
        allow_frozen_substitute: allowFrozen.value,
        markers: rows.value.map(r => ({ code: r.code, storage_type: r.storage_type })),
      }),
    })
    rows.value = res.items
    allowFrozen.value = res.allow_frozen_substitute
    saved.value = true
  } catch (e: any) {
    // 开关非法或编码对不上：四处都停在保存前
    error.value = `保存失败，未写入任何改动：${e?.message ?? ''}`
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <h1>库存</h1>
  <p class="sub">鲜仓 · 冻仓 · 未区分分套记账；生成备料单不扣结存</p>
  <div class="card" style="margin-bottom:0.85rem;display:flex;align-items:center;gap:0.9rem;flex-wrap:wrap">
    <label style="display:flex;align-items:center;gap:0.45rem;cursor:pointer">
      <input type="checkbox" v-model="allowFrozen" />
      <span>允许冻顶鲜</span>
      <span class="badge" :class="allowFrozen ? 'badge-ok' : 'badge-warn'">{{ allowFrozen ? '允许冻顶' : '禁替' }}</span>
    </label>
    <button class="btn" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存标记与开关' }}</button>
    <span v-if="saved" class="badge badge-ok">已保存</span>
    <span v-if="error" class="badge badge-bad">{{ error }}</span>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>编码</th><th>名称</th><th>标记</th><th>鲜仓</th><th>冻仓</th><th>库存</th><th>单位</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td>
          <td>{{ r.name }}</td>
          <td>
            <select v-model="r.storage_type">
              <option value="">不区分</option>
              <option value="fresh">鲜品</option>
              <option value="frozen">冻品</option>
            </select>
          </td>
          <td>{{ r.storage_type === 'fresh' ? r.fresh_stock_qty : '—' }}</td>
          <td>{{ r.storage_type === 'fresh' || r.storage_type === 'frozen' ? r.frozen_stock_qty : '—' }}</td>
          <td>{{ r.storage_type === '' ? r.stock_qty : '—' }}</td>
          <td>{{ r.unit }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
