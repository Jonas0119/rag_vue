/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// 为 tus-js-client 提供类型声明（如果库未内置 TS 类型，则视为 any）
declare module 'tus-js-client';


