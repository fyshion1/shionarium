// 模型地址、密钥和名称由后端的统一模型连接解析，不再读取旧浏览器配置。
// 调用方传空字段时，画廊/角色词条接口各自选择视觉或文字默认路。
const STORAGE_KEY = 'xiaotangren.config'
export type VisionRoute = { baseUrl: string; apiKey: string; model: string }

/** 保留旧调用签名；不携带任何浏览器保存的旧模型连接。 */
export function visionRoute(_kind: 'vision' | 'chat' = 'vision'): VisionRoute {
  return {baseUrl:'',apiKey:'',model:''}
}

/** 当前是否在无审查通道（决定自动描述要不要注入越狱提示，§7）。 */
export function isUncensoredChannel(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return false
    return (JSON.parse(raw) as Record<string, string>).channel === 'uncensored'
  } catch {
    return false
  }
}
