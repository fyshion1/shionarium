/**
 * VRM 素材扩展接口。框架不预置模型，默认清单为空。
 * 桌宠由用户在插件窗口添加已获授权的本地模型。
 */

export type VrmAsset = {
  id: string
  name: string
  /** 相对仓库根 assets/models/vrm 的文件名。 */
  file: string
  /** 面板上写一句这个模型是干嘛的 / 有什么限制。 */
  note: string
}

import { ASSETS_BASE } from './live2dAssets'

export const VRM_ASSETS: VrmAsset[] = []

export function resolveVrmAsset(id: string | undefined): VrmAsset | null {
  if (!id) return null
  return VRM_ASSETS.find((a) => a.id === id) ?? null
}

export function vrmUrl(asset: VrmAsset): string {
  return `${ASSETS_BASE}/models/vrm/${asset.file}`
}
