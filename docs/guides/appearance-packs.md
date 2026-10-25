# 外观包 API v1

2026-10-25。外观包是本体提供的声明式显示接口，独立于角色包、默认人设与旧的 React 主题。包内不执行 Python、JavaScript、HTML 或 CSS，不读取聊天和记忆。原创示例：[纸与墨](../../examples/appearance-packs/paper-ink/theme.json)；机器可读规范：[JSON Schema](../schemas/appearance-pack-v1.schema.json)。

## 用户安装

顶栏 **外观 → 选择外观包 ZIP**，先查看作者、许可及日夜色板，再勾选许可并确认安装。安装不会自动切换；选择包后点 **应用外观** 才生效。不刷新网页、不重启后端、不重新构建前端。切换日夜模式使用包内对应色板。

点击任意内置配色可立即恢复本体预设。外观包选项和内置配色偏好仅保存在当前浏览器，不跨设备同步。刷新时从本机重新读取外观包，不往服务器上传聊天、角色或个人资料。

选择一个已导入的包，可展开“移除此外观包”并确认；移除会把目录移动到本机 `backend/data/appearance-packs/.removed/`。当前浏览器随后回退到内置配色；其他已打开的浏览器在刷新页面或列表后回退。导入的外观保存在 `backend/data/appearance-packs/<id>/`，属于本机用户文件，不提交 Git。ZIP 先暂存，预览一小时过期；总暂存上限 80 MB，单次安装消耗该预览标识。

本地后端保存导入包，因此若将本体部署到远程服务器，包也会存到该服务器；这里不承诺云部署时“文件始终不离开电脑”。安装与管理沿用本机后台权限检查，不提供开放的远程上传入口。

## 作者最快路径

复制 `examples/appearance-packs/paper-ink/`，修改 `theme.json` 的 `id`、`name`、`author`、`license` 和色板。每个包使用自己的稳定 ID，例如 `my-blue-room`，无需沿用 `xiaotangren-theme` 目录名。

用本体 Python 环境打包（Windows）：

```powershell
backend\.venv\Scripts\python.exe tools/build_appearance_pack.py examples/appearance-packs/paper-ink dist/paper-ink-1.0.0.zip
```

Linux/macOS 使用 `backend/.venv/bin/python`。打包器计算资源 SHA-256，用运行时同一验证器检查清单，不修改源目录。构建环境需要本体的 Python 依赖，不需要 Node 或前端构建。将生成 ZIP 发给朋友或放到自己的 GitHub Releases，用户从“外观”导入；当前未加入中心市场或自动更新。

本机开发也可把整个源码目录放到当前插件根目录的任意直接子目录：例如 `features/my-blue-room/theme.json`，组合仓库则为 `plugins/my-blue-room/theme.json`。后端自动发现根部清单，点“刷新列表”即可出现；不需要 Python 入口或重新编译。资源 SHA-256 仍须正确，可从打包后的清单复制。该目录由作者自行维护，界面的移除按钮只管理导入包。导入包优先于插件根目录；相同 ID 的重复项会显示错误，不能用多个同名 ID 切换实现。

## 清单契约

ZIP 根目录直接包含 `theme.json`，不套一层项目目录。可附 `LICENSE.txt`、`README.md`，图片或字体放在 `assets/` 下。版本为 `format: "appearance-pack"`、`format_version: 1`；清单拒绝未知字段和不支持的格式版本。v1 字段的语义保持兼容；新增不兼容格式另起版本，不能悄悄改变已有色板的含义。

| 字段 | 说明 |
|---|---|
| `id` | 最长 64 字符，小写字母开头，小写字母/数字/连字符；例如 `my-blue-room` |
| `name`, `version`, `author`, `license` | 名称、`1.0.0` 形式版本、作者及许可；许可可写 SPDX 标识并附完整许可说明 |
| `description` | 简短描述，可省略 |
| `colors.light`, `colors.dark` | 必须分别提供完整日间与夜间色板，颜色仅接受六位十六进制 `#rrggbb` |
| `radius` | 0–24 的整数，控制本体支持的卡片/输入控件圆角，默认 12；不承诺覆盖插件自己的所有组件 |
| `font` | `system`、`serif` 或 `monospace`，默认 `system`；未附字体时使用设备字体 |
| `font_file` | 可选 `assets/name.woff2`，字体只从本机包内读取 |
| `background_file` | 可选包内 PNG、JPG 或 WebP，作为页面背景，不覆盖聊天与卡片的阅读底色 |
| `background_opacity` | 0–0.4，默认 0.12；字体和背景均不接受远程 URL |
| `assets` | 资源路径到 SHA-256 的映射；打包器自动生成，所有资源必须被字体或背景字段引用 |

颜色的稳定语义与本体内部兼容映射如下。作者使用左列字段，不依赖旧的 `pink` 命名：

| 清单颜色 | 用途 | 本体兼容变量 |
|---|---|---|
| `background`, `background_soft` | 页面与次级背景 | `--bg`, `--bg-soft` |
| `surface`, `surface_raised` | 卡片与浮起表面 | `--surface`, `--surface-2` |
| `text`, `text_muted`, `text_subtle` | 正文、辅助、次要文本 | `--text`, `--text-2`, `--text-3` |
| `border`, `border_strong` | 普通与强调边框 | `--border`, `--border-strong` |
| `accent`, `accent_text`, `accent_soft` | 强调填充、强调文字、淡强调背景 | `--pink`, `--pink-deep`, `--pink-soft` |
| `mint`, `sky` | 辅助配色 | `--mint`, `--sky` |

正文建议在对应背景达到至少 4.5:1 对比度，按钮和聊天气泡也要检查。声明式包覆盖本体语义色；写死颜色的第三方界面不会自动适配。包不修改站点品牌名称、导航结构、React 组件或角色数据，这些能力仍属于高级插件。

单 ZIP 上限 20 MB、展开上限 32 MB、最多 32 条 ZIP 目录项；最多 16 个声明资源（v1 实际只引用一个背景和一个字体）。资源只允许单层普通文件名，禁止外链、路径穿越、符号链接、加密条目和未声明资源。背景检查图片类型及像素上限，字体检查 WOFF2 文件头；这不是字体渲染器的完整安全认证。请自行确认字体和图片的使用、修改及再分发许可；本体代码的 Apache-2.0 不覆盖作者自带素材。

## HTTP 接口

| 请求 | 用途 |
|---|---|
| `GET /api/appearance-packs` | 返回有效包 `items` 和逐目录错误 `errors` |
| `GET /api/appearance-packs/schema` | 当前 v1 JSON Schema |
| `POST /api/appearance-packs/preview` | multipart `file`，只校验、暂存，返回 `token`、`manifest` 和 `size` |
| `POST /api/appearance-packs/install` | JSON `{ "token": "预览返回的标识" }`，安装但不应用，不覆盖已有 ID |
| `DELETE /api/appearance-packs/{id}` | 将导入包移到本地备份 |
| `GET /api/appearance-packs/{id}/assets/{filename}` | 仅提供有效包明确声明且校验通过的图片/字体 |

管理接口要求 `X-Exploration-Dashboard: 1` 并经过本体的本机、来源检查；聊天文本不授予安装权限。资源读取无需该请求头，以支持浏览器图片/字体加载；不能用于读取任意磁盘文件。应用选择由浏览器保存，不写后端共享开关，因此不同浏览器可使用不同外观。

## 与旧主题的关系

旧 `xiaotangren-theme` 仍是固定入口的高级 React/默认数据插件，保留其构建和重启要求。新外观包在它之后覆盖本体的语义色，选择内置配色会清除外观包覆盖，但不会启停高级插件。不要为了制作一个色板包复制旧主题中的角色、人设或私人图片。

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m unittest tests.test_appearance_packs -v
cd ../frontend
npm run build
node tests/appearance-packs.mjs "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

浏览器测试使用合成 API，验证导入确认、手动应用、日夜模式、刷新保持、移除回退和移动屏幕。Python 测试单独使用真实 ZIP、临时目录和 HTTP 路由验证解析、权限及文件边界，不读取用户数据库、不启动日常服务。
