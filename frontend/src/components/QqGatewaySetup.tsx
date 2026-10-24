import { useEffect, useState } from 'react'

type Diagnostic = { installed: boolean; folder: string; versions: string[]; old_qq: boolean; message: string; password_hint: string; install_supported: boolean }
type AudioDiagnostic = { ready: boolean; checks: Record<string, boolean>; engine: string; fallback: string; instructions: string; note: string }
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api/qq-bridge/setup/' + path, {
    method: body ? 'POST' : 'GET', headers: { 'X-Exploration-Dashboard': '1', 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || '检查失败')
  return data
}
export default function QqGatewaySetup() {
  const [info, setInfo] = useState<Diagnostic | null>(null)
  const [note, setNote] = useState('')
  const [passwordNotice, setPasswordNotice] = useState('')
  const [audio, setAudio] = useState<AudioDiagnostic | null>(null)
  const [audioError, setAudioError] = useState('')
  async function check() {
    try { setInfo(await api<Diagnostic>('diagnostics')) }
    catch (e) { setNote(String(e)) }
    try { setAudio(await api<AudioDiagnostic>('audio')); setAudioError('') }
    catch (e) { setAudioError('语音依赖检查失败：' + String(e)) }
  }
  useEffect(() => { void check() }, [])
  return <div className="mb-3 rounded-xl border border-[var(--border)] p-3 text-xs leading-relaxed">
    <b>首次接入 / 连接不上？</b>
    <button className="btn ghost sm" onClick={() => void check()}>检查安装与 QQ</button>
    {info && <>
      <p>{info.installed ? '已找到网关运行文件' : '配置目录中未找到完整网关（也可能安装在其他目录）'}：{info.folder}</p>
      <p>正在运行的 QQ：{info.versions.join('、') || '版本未知，请在 QQ 设置中核对'}。{info.message}</p>
      <p>{info.password_hint}</p>
      <button className="btn ghost sm" onClick={() => {
        if (passwordNotice) { setPasswordNotice(''); return }
        void api<{ notice: string }>('initial-password').then(r => setPasswordNotice(r.notice)).catch(e => setNote(String(e)))
      }}>{passwordNotice ? '隐藏密码提示' : '查看启动日志中的初始密码提示'}</button>
      {passwordNotice && <pre className="whitespace-pre-wrap break-words">{passwordNotice}</pre>}
      {!info.installed && <p>请从官方渠道阅读协议后手动安装网关，再在下方填写安装目录。</p>}
    </>}
    <a href="https://github.com/SnowLuma/SnowLuma/releases" target="_blank" rel="noreferrer">官方发行说明 / 手动下载</a>
    {audio && <div>
      <b>QQ 语音识别：{audio.ready ? '本地兜底依赖齐全' : '本地兜底尚未就绪'}</b>
      <p>当前引擎 {audio.engine}，QQ 失败后 {audio.fallback}。</p>
      <p>{Object.entries(audio.checks).map(([name, ready]) => `${name}：${ready ? '已找到' : '缺少'}`).join('；')}</p>
      {!audio.ready && <p>{audio.instructions}</p>}
      <p>{audio.note}</p>
    </div>}
    {audioError && <p role="status">{audioError}</p>}
    <p>SnowLuma 采用独立非商业许可；其 EULA §5.4 要求自动部署及商用须先取得书面授权。也可选择其他兼容 OneBot v11 的网关。</p>
    <p>配置顺序：登录兼容版本的 QQ → 开网关 → 在网关网页完成初始化 → 在下方连接设置保存网页密码 → 读取已登录 QQ、选择账号并自动配置，再保存。网页密码与连接 token 是两回事；非专家模式的连接设置收在「连接修复」中。</p>
    {note && <p role="status">{note}</p>}
  </div>
}
