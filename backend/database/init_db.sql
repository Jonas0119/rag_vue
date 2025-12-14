-- RAG 智能问答系统数据库初始化脚本
-- SQLite 3.x

-- ==================== 用户表 ====================
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    display_name VARCHAR(100),
    avatar_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    preferences TEXT,  -- JSON: 用户偏好设置
    CONSTRAINT username_length CHECK(length(username) >= 3)
);

CREATE INDEX IF NOT EXISTS idx_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_active ON users(is_active);

-- ==================== 会话表 ====================
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(36) PRIMARY KEY,  -- UUID
    user_id INTEGER NOT NULL,
    title VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    is_pinned BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'archived'
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_sessions ON sessions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_pinned ON sessions(is_pinned, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_status ON sessions(status);

-- ==================== 消息表 ====================
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant'
    content TEXT NOT NULL,
    retrieved_docs TEXT,  -- JSON: 检索到的文档
    thinking_process TEXT,  -- JSON: 思考过程
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens_used INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT role_check CHECK(role IN ('user', 'assistant'))
);

CREATE INDEX IF NOT EXISTS idx_session_messages ON messages(session_id, created_at);

-- ==================== 文档表 ====================
CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR(36) PRIMARY KEY,  -- UUID
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,  -- 存储文件名
    original_filename VARCHAR(255) NOT NULL,  -- 原始文件名
    filepath VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    page_count INTEGER,
    chunk_count INTEGER DEFAULT 0,
    vector_collection VARCHAR(100),  -- Chroma collection name
    upload_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'processing', 'error'
    error_message TEXT,
    metadata TEXT,  -- JSON: 额外元数据
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT status_check CHECK(status IN ('active', 'processing', 'error', 'deleted'))
);

CREATE INDEX IF NOT EXISTS idx_user_docs ON documents(user_id, upload_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);

-- ==================== Parent-Child 映射表 ====================
CREATE TABLE IF NOT EXISTS parent_child_maps (
    user_id INTEGER NOT NULL,
    doc_id VARCHAR(36) NOT NULL,
    parent_id VARCHAR(36) NOT NULL,
    parent_content TEXT NOT NULL,
    parent_metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, doc_id, parent_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pcm_user_doc ON parent_child_maps(user_id, doc_id);
CREATE INDEX IF NOT EXISTS idx_pcm_parent_id ON parent_child_maps(parent_id);

-- ==================== 用户统计表（可选）====================
CREATE TABLE IF NOT EXISTS user_stats (
    user_id INTEGER PRIMARY KEY,
    total_sessions INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    total_documents INTEGER DEFAULT 0,
    storage_used INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    last_active TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ==================== 初始化完成 ====================
-- 插入测试数据（可选，开发阶段使用）
-- INSERT INTO users (username, password_hash, email, display_name) VALUES
-- ('admin', '$2b$12$...', 'admin@example.com', '管理员');

