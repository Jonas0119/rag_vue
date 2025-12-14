<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2>RAG 系统</h2>
        <div class="user-info" v-if="authStore.user">
          <span>{{ authStore.user.display_name || authStore.user.username }}</span>
          <button @click="handleLogout" class="logout-btn">登出</button>
        </div>
      </div>

      <nav class="nav">
        <router-link 
          to="/" 
          class="nav-item"
          :class="{ active: $route.path === '/' }"
        >
          💬 智能问答
        </router-link>
        <router-link 
          to="/documents" 
          class="nav-item"
          :class="{ active: $route.path === '/documents' }"
        >
          📁 知识库管理
        </router-link>
        <router-link 
          to="/settings" 
          class="nav-item"
          :class="{ active: $route.path === '/settings' }"
        >
          ⚙️ 系统设置
        </router-link>
      </nav>

      <div v-if="$route.path === '/'" class="session-list">
        <div class="session-list-header">
          <h3>会话列表</h3>
          <button @click="chatStore.newChat()" class="new-chat-btn">+ 新建</button>
        </div>
        <div class="sessions">
          <div
            v-for="session in chatStore.sessions"
            :key="session.session_id"
            :class="['session-item', { active: chatStore.currentSessionId === session.session_id }]"
            @click="chatStore.selectSession(session.session_id)"
          >
            <div class="session-title">{{ session.title }}</div>
            <div class="session-meta">
              <span>{{ session.message_count }} 条消息</span>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()

async function handleLogout() {
  await authStore.logout()
}

onMounted(async () => {
  if (authStore.isAuthenticated) {
    await chatStore.fetchSessions()
  }
})
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 280px;
  background: #2d3748;
  color: white;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #4a5568;
}

.sidebar-header h2 {
  margin: 0 0 15px 0;
  font-size: 20px;
}

.user-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.logout-btn {
  padding: 6px 12px;
  background: #e53e3e;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.logout-btn:hover {
  background: #c53030;
}

.nav {
  padding: 10px 0;
  border-bottom: 1px solid #4a5568;
}

.nav-item {
  display: block;
  padding: 12px 20px;
  color: #cbd5e0;
  text-decoration: none;
  transition: background 0.2s;
}

.nav-item:hover {
  background: #4a5568;
}

.nav-item.active {
  background: #4a5568;
  color: white;
  font-weight: 600;
}

.session-list {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.session-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.session-list-header h3 {
  margin: 0;
  font-size: 16px;
}

.new-chat-btn {
  padding: 6px 12px;
  background: #4299e1;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.new-chat-btn:hover {
  background: #3182ce;
}

.sessions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-item {
  padding: 12px;
  background: #4a5568;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.session-item:hover {
  background: #5a6578;
}

.session-item.active {
  background: #4299e1;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
}

.session-meta {
  font-size: 12px;
  color: #cbd5e0;
  opacity: 0.8;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: #f7fafc;
}
</style>
