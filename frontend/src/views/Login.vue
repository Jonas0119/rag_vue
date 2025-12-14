<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="title">RAG 智能问答系统</h1>
      
      <div class="tabs">
        <button 
          :class="['tab', { active: isLogin }]"
          @click="isLogin = true"
        >
          登录
        </button>
        <button 
          :class="['tab', { active: !isLogin }]"
          @click="isLogin = false"
        >
          注册
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="form">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            required
            placeholder="请输入用户名"
            :disabled="loading"
          />
        </div>

        <div v-if="!isLogin" class="form-group">
          <label for="email">邮箱（可选）</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            placeholder="请输入邮箱"
            :disabled="loading"
          />
        </div>

        <div v-if="!isLogin" class="form-group">
          <label for="display_name">显示名称（可选）</label>
          <input
            id="display_name"
            v-model="form.display_name"
            type="text"
            placeholder="请输入显示名称"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            required
            placeholder="请输入密码"
            :disabled="loading"
          />
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <button 
          type="submit" 
          class="submit-btn"
          :disabled="loading"
        >
          {{ loading ? '处理中...' : (isLogin ? '登录' : '注册') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const isLogin = ref(true)
const loading = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
  email: '',
  display_name: ''
})

async function handleSubmit() {
  error.value = ''
  loading.value = true

  try {
    if (isLogin.value) {
      await authStore.login({
        username: form.username,
        password: form.password
      })
    } else {
      await authStore.register({
        username: form.username,
        password: form.password,
        email: form.email || undefined,
        display_name: form.display_name || undefined
      })
    }
  } catch (err: any) {
    error.value = err.message || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  background: white;
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.title {
  text-align: center;
  margin-bottom: 30px;
  color: #333;
  font-size: 28px;
  font-weight: 600;
}

.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
  border-bottom: 2px solid #f0f0f0;
}

.tab {
  flex: 1;
  padding: 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: #666;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.3s;
}

.tab.active {
  color: #667eea;
  border-bottom-color: #667eea;
  font-weight: 600;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.form-group input {
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.3s;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.form-group input:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.error-message {
  padding: 12px;
  background: #fee;
  color: #c33;
  border-radius: 6px;
  font-size: 14px;
}

.submit-btn {
  padding: 14px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s;
}

.submit-btn:hover:not(:disabled) {
  background: #5568d3;
}

.submit-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
