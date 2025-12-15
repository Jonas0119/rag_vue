<template>
  <div class="layout">
    <!-- 移动端菜单按钮 -->
    <button 
      class="menu-toggle"
      @click="toggleMenu"
      aria-label="切换菜单"
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line v-if="!isMenuOpen" x1="3" y1="6" x2="21" y2="6"/>
        <line v-if="!isMenuOpen" x1="3" y1="12" x2="21" y2="12"/>
        <line v-if="!isMenuOpen" x1="3" y1="18" x2="21" y2="18"/>
        <line v-if="isMenuOpen" x1="18" y1="6" x2="6" y2="18"/>
        <line v-if="isMenuOpen" x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>

    <!-- 遮罩层 -->
    <div 
      v-if="isMenuOpen"
      class="overlay"
      @click="closeMenu"
    ></div>

    <!-- 侧边栏 -->
    <aside 
      class="sidebar"
      :class="{ 'sidebar-open': isMenuOpen }"
    >
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
          @click="closeMenuOnMobile"
        >
          💬 智能问答
        </router-link>
        <router-link 
          to="/documents" 
          class="nav-item"
          :class="{ active: $route.path === '/documents' }"
          @click="closeMenuOnMobile"
        >
          📁 知识库管理
        </router-link>
        <router-link 
          to="/settings" 
          class="nav-item"
          :class="{ active: $route.path === '/settings' }"
          @click="closeMenuOnMobile"
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
            @click="handleSessionClick(session.session_id)"
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
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()
const isMenuOpen = ref(false)

function toggleMenu() {
  isMenuOpen.value = !isMenuOpen.value
}

function closeMenu() {
  isMenuOpen.value = false
}

function closeMenuOnMobile() {
  // 在移动端点击导航项时关闭菜单
  if (window.innerWidth < 768) {
    closeMenu()
  }
}

function handleSessionClick(sessionId: string) {
  chatStore.selectSession(sessionId)
  // 在移动端点击会话项时关闭菜单
  closeMenuOnMobile()
}

// 监听窗口大小变化，在桌面端自动打开菜单
function handleResize() {
  if (window.innerWidth >= 768) {
    // 桌面端：侧边栏始终可见，保持状态一致性
    isMenuOpen.value = true
  } else {
    // 移动端：默认关闭菜单
    isMenuOpen.value = false
  }
}

onMounted(async () => {
  if (authStore.isAuthenticated) {
    await chatStore.fetchSessions()
  }
  window.addEventListener('resize', handleResize)
  handleResize() // 初始化时检查
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

async function handleLogout() {
  await authStore.logout()
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  position: relative;
}

/* 移动端菜单按钮 */
.menu-toggle {
  display: none;
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 1001;
  width: 44px;
  height: 44px;
  padding: 10px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  color: var(--color-text-primary);
  align-items: center;
  justify-content: center;
}

.menu-toggle:hover {
  background: var(--color-bg-hover);
  box-shadow: var(--shadow-lg);
}

.menu-toggle svg {
  width: 100%;
  height: 100%;
}

/* 遮罩层 */
.overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  animation: fadeIn var(--transition-base);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 侧边栏 */
.sidebar {
  width: 280px;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition-slow);
  z-index: 1000;
}

.sidebar-header {
  padding: var(--spacing-xl);
  border-bottom: 1px solid var(--color-border);
}

.sidebar-header h2 {
  margin: 0 0 var(--spacing-lg) 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.user-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  gap: var(--spacing-md);
}

.user-info span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.logout-btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-danger);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  transition: all var(--transition-base);
}

.logout-btn:hover {
  background: var(--color-danger-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.nav {
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--color-border);
}

.nav-item {
  display: block;
  padding: var(--spacing-md) var(--spacing-xl);
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: all var(--transition-base);
  font-size: 14px;
  border-left: 3px solid transparent;
}

.nav-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: var(--color-bg-hover);
  color: var(--color-primary);
  font-weight: 600;
  border-left-color: var(--color-primary);
}

.session-list {
  flex: 1;
  padding: var(--spacing-xl);
  overflow-y: auto;
}

.session-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.session-list-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.new-chat-btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all var(--transition-base);
}

.new-chat-btn:hover {
  background: var(--color-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.sessions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.session-item {
  padding: var(--spacing-md);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-base);
}

.session-item:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
  transform: translateX(2px);
  box-shadow: var(--shadow-sm);
}

.session-item.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.session-item.active .session-title {
  color: white;
}

.session-item.active .session-meta {
  color: rgba(255, 255, 255, 0.9);
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: var(--spacing-xs);
  color: var(--color-text-primary);
}

.session-meta {
  font-size: 12px;
  color: var(--color-text-muted);
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: var(--color-bg-secondary);
  transition: margin-left var(--transition-slow);
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .menu-toggle {
    display: flex;
  }

  .overlay {
    display: block;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    transform: translateX(-100%);
    box-shadow: var(--shadow-lg);
  }

  .sidebar.sidebar-open {
    transform: translateX(0);
  }

  /* 为关闭按钮留出空间，避免遮挡标题 */
  .sidebar-header {
    padding-top: 76px; /* 16px (top) + 44px (button) + 16px (spacing) */
  }

  .main-content {
    margin-left: 0;
    width: 100%;
  }
}

/* 桌面端 */
@media (min-width: 769px) {
  .menu-toggle {
    display: none;
  }

  .overlay {
    display: none !important;
  }

  .sidebar {
    position: relative;
    transform: translateX(0) !important;
  }

  .main-content {
    margin-left: 0;
  }
}
</style>
