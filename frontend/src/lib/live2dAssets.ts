/**
 * Live2D 素材扩展接口。框架不预置模型，默认清单为空。
 * 桌宠由用户在插件窗口添加已获授权的本地模型。
 */

export type Live2DAsset = {
  /** key：角色数据里 `live2d.model` 存的就是这个。 */
  id: string
  name: string
  /** 相对仓库根 assets/live2d 的 .model3.json 路径（会拼成 /assets 下的 URL）。 */
  model3: string
  /** 有值就用它当待机动作组名，没有则用模型自带的第一个动作组。 */
  idleMotion?: string
  /** 打开展示用的默认表情名。 */
  expression?: string
}

/** 仓库根 assets/ 在 dev server 下的访问前缀（跟 vite.config.ts 的 publicDir 对齐）。 */
export const ASSETS_BASE = '/assets'

export const LIVE2D_ASSETS: Live2DAsset[] = []

export function resolveLive2DAsset(id: string | undefined): Live2DAsset | null {
  if (!id) return null
  return LIVE2D_ASSETS.find((a) => a.id === id) ?? null
}

/** 模型清单项的地址：`/assets/live2d/.../X.model3.json`。 */
export function live2dUrl(asset: Live2DAsset): string {
  return `${ASSETS_BASE}/${asset.model3}`
}
