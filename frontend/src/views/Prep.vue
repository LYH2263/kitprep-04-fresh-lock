<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const tree = ref<any[]>([])
const data = ref<any>(null)
const orders = ref<any[]>([])
const error = ref('')

const TYPE_LABELS: Record<string, string> = { '': '不区分', fresh: '鲜品', frozen: '冻品' }
const MODE_LABELS: Record<string, string> = { no_substitute: '禁替', allow_frozen: '允许冻顶' }

function apply(res: any) {
  data.value = res
}

async function run() {
  error.value = ''
  try {
    apply(await api('/prep/run', { method: 'POST' }))
  } catch (e: any) {
    error.value = e?.message ?? '生成失败'
  }
}

onMounted(async () => {
  tree.value = await api('/bom/tree')
  orders.value = await api('/orders')
  try {
    apply(await api('/prep/latest'))
  } catch { data.value = null }
})
</script>

<template>
  <h1>备料工作台</h1>
  <p class="sub">左 BOM 树 · 中备料表 · 右缺料便利贴 · 顶栏订单芯片</p>
  <div class="kp-chips" style="margin-bottom:0.75rem" v-if="orders.length">
    <span v-for="o in orders" :key="o.id" class="kp-chip" style="cursor:default">
      {{ o.code }} · {{ o.outlet }}
    </span>
  </div>
  <button class="btn" @click="run">生成备料单</button>
  <span v-if="error" class="badge badge-bad" style="margin-left:0.6rem">{{ error }}</span>
  <div class="kp-workbench" style="margin-top:0.85rem">
    <aside class="kp-bom-tree">
      <h2>菜品 / BOM</h2>
      <div v-for="d in tree" :key="d.code" class="kp-dish-node">
        <strong>{{ d.dish }}</strong>
        <span style="font-size:0.7rem;color:#8a8078">{{ d.code }}</span>
        <ul>
          <li v-for="(c,i) in d.children" :key="i">{{ c.ingredient }} · {{ c.qty }} {{ c.unit }}</li>
        </ul>
      </div>
    </aside>
    <section class="kp-worksheet" v-if="data">
      <h2>
        备料单 · {{ data.order?.code }} · {{ data.order?.outlet }}
        <span class="badge" :class="data.mode === 'allow_frozen' ? 'badge-ok' : 'badge-warn'">
          {{ MODE_LABELS[data.mode] ?? data.mode }}
        </span>
      </h2>
      <table>
        <thead>
          <tr>
            <th>原料</th><th>标记</th><th>需求</th><th>鲜仓</th><th>冻仓</th><th>库存</th>
            <th>鲜缺</th><th>冻顶</th><th>缺口</th><th>单位</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in data.prep_lines" :key="l.ingredient_id">
            <td>{{ l.ingredient_name }}</td>
            <td><span class="badge" :class="l.storage_type ? 'badge-warn' : ''">{{ TYPE_LABELS[l.storage_type] }}</span></td>
            <td>{{ l.need_qty }}</td>
            <td>{{ l.storage_type === 'fresh' ? l.fresh_stock_qty : '—' }}</td>
            <td>{{ l.storage_type ? l.frozen_stock_qty : '—' }}</td>
            <td>{{ l.storage_type === '' ? l.stock_qty : '—' }}</td>
            <td>{{ l.storage_type === 'fresh' ? l.fresh_shortage : '—' }}</td>
            <td>{{ l.frozen_cover > 0 ? l.frozen_cover : '—' }}</td>
            <td><span v-if="l.shortage > 0" class="badge badge-bad">{{ l.shortage }}</span><span v-else>0</span></td>
            <td>{{ l.unit }}</td>
          </tr>
        </tbody>
      </table>
    </section>
    <aside class="kp-shortage-sticky">
      <h2>⚠ 缺料便利贴</h2>
      <div v-for="r in data?.shortages ?? []" :key="r.ingredient_id" class="kp-shortage-item">
        <span>{{ r.ingredient_name }} <span class="badge badge-bad">{{ r.note }}</span></span>
        <span class="kp-qty">−{{ r.shortage }} {{ r.unit }}</span>
      </div>
      <p v-if="!(data?.shortages ?? []).length" style="font-size:0.8rem;margin:0.5rem 0 0">暂无缺料</p>
    </aside>
  </div>
</template>
