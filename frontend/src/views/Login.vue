<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="logo">
        <svg viewBox="0 0 32 32" width="44" height="44"><circle cx="16" cy="16" r="14" fill="#22c55e" /><path d="M6 17h5l3-7 4 13 3-6h5" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </div>
      <h1>服務監控平台</h1>
      <p class="muted">即時掌握所有服務與轉發狀態</p>
      <el-form @submit.prevent="submit" size="large">
        <el-form-item><el-input v-model="form.username" placeholder="帳號" prefix-icon="User" autofocus /></el-form-item>
        <el-form-item><el-input v-model="form.password" type="password" placeholder="密碼" prefix-icon="Lock" show-password /></el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon style="margin-bottom:14px" />
        <el-button type="primary" native-type="submit" :loading="loading" style="width:100%">登入</el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http, { auth } from '../api'

const router = useRouter()
const route = useRoute()
const form = reactive({ username: 'admin', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true; error.value = ''
  try {
    const r = await http.post('/auth/login', form, { silent: true })
    auth.set(r.token, r.username)
    router.replace(route.query.next || '/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px;
  background: radial-gradient(ellipse at top, #1e3a8a 0%, #0f172a 55%, #020617 100%);
}
.login-card {
  width: 100%; max-width: 380px; background: var(--sm-card); border-radius: 16px; padding: 36px 32px 28px;
  box-shadow: 0 25px 60px rgba(0,0,0,.35); text-align: center;
}
h1 { margin: 12px 0 4px; font-size: 22px; }
p { margin: 0 0 24px; }
</style>
