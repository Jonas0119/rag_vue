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
  padding: var(--spacing-xl);
}

.login-card {
  background: var(--color-bg-primary);
  border-radius: var(--radius-xl);
  padding: var(--spacing-3xl);
  width: 100%;
  max-width: 400px;
  box-shadow: var(--shadow-lg);
  animation: slideUp var(--transition-slow);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.title {
  text-align: center;
  margin-bottom: var(--spacing-3xl);
  color: var(--color-text-primary);
  font-size: 28px;
  font-weight: 600;
}

.tabs {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-3xl);
  border-bottom: 2px solid var(--color-border);
}

.tab {
  flex: 1;
  padding: var(--spacing-md);
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: var(--color-text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all var(--transition-base);
  font-weight: 500;
}

.tab:hover {
  color: var(--color-primary);
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.form-group input {
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  transition: all var(--transition-base);
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-group input:disabled {
  background: var(--color-bg-secondary);
  cursor: not-allowed;
  opacity: 0.6;
}

.error-message {
  padding: var(--spacing-md);
  background: rgba(229, 62, 62, 0.1);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: 14px;
  border: 1px solid rgba(229, 62, 62, 0.2);
}

.submit-btn {
  min-height: 44px;
  padding: var(--spacing-md);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-base);
}

.submit-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
  opacity: 0.6;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .login-container {
    padding: var(--spacing-md);
  }

  .login-card {
    padding: var(--spacing-xl);
  }

  .title {
    font-size: 24px;
    margin-bottom: var(--spacing-xl);
  }

  .tabs {
    margin-bottom: var(--spacing-xl);
  }

  .form {
    gap: var(--spacing-lg);
  }

  .form-group input {
    font-size: 16px; /* 防止iOS自动缩放 */
  }
}
</style>
