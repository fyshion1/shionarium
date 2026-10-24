# 插件市场下载源

网页插件市场安装桌宠与 QQ 桥时，按目录中的完整提交哈希从 GitHub codeload 下载源码，不再要求本机安装 Git。
默认先访问官方 codeload，失败后尝试 gh-proxy.com 与 ghfast.top。
第三方镜像会收到下载地址并提供源码，固定 URL 中的提交号不等于对镜像内容做了独立密码学验签。
只想使用官方源时，启动应用前设置 `SHIONARIUM_GH_MIRROR` 为空字符串；也可填写自行信任的 HTTPS 前缀。

依赖镜像只通过安装子进程的环境变量注入，不改系统 npm/pip 配置：

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| SHIONARIUM_NPM_REGISTRY | https://registry.npmmirror.com | npm 包 |
| SHIONARIUM_PYPI_INDEX | https://pypi.tuna.tsinghua.edu.cn/simple | uv / pip |
| ELECTRON_MIRROR | https://npmmirror.com/mirrors/electron/ | Electron 二进制 |
| HF_ENDPOINT / HF_MIRROR | https://hf-mirror.com | 向量模型 |
| VOICE_MODEL_MIRROR | 继承 HF_ENDPOINT / HF_MIRROR | 本地 TTS / ASR 模型 |

如需官方依赖源，分别显式指定 registry.npmjs.org、pypi.org/simple、Electron 官方二进制源和 huggingface.co。
镜像在某台机器的测速结果不代表所有网络都可用；失败摘要与阶段日志保存在本机 `backend/data/plugin-installs/`。
源码包限制为 128 MiB，解压限制为 512 MiB / 20000 项，拒绝路径穿越、Windows ADS、链接和设备文件。
依赖装完才发布插件目录，已有插件目录不会覆盖，安装后保持关闭。
市场下载的是源码快照，不含 `.git`；开发者需要 Git 历史时请自行 clone 对应仓库。

进度当前仍按阶段显示，安装取消和双指缩放尚未实现。不要把不定进度条当作实际百分比。
