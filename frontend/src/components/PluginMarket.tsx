import {useEffect, useRef, useState} from 'react'
import {asJson} from '../api/client'

type Entry = {id:string;name:string;kind:'plugin'|'component';description:string;size:string;revision:string;available:boolean;installed:boolean;occupied:boolean;reason?:string;repository?:string;url?:string}
type Job = {id:string;item_id:string;name:string;status:'running'|'succeeded'|'failed';phase:string;message:string}
const headers={'Content-Type':'application/json','X-Exploration-Dashboard':'1'}

export default function PluginMarket({onInstalled,locked=false}:{onInstalled:()=>void;locked?:boolean}) {
  const [items,setItems]=useState<Entry[]>([])
  const [jobs,setJobs]=useState<Job[]>([])
  const [selected,setSelected]=useState<Entry|null>(null)
  const [accepted,setAccepted]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(true)
  const completed=useRef(new Set<string>())
  const running=jobs.some(job=>job.status==='running')
  async function load() {
    const [catalog,history]=await Promise.all([
      asJson<{items:Entry[]}>('/api/plugin-market',{headers}),
      asJson<{items:Job[]}>('/api/plugin-market/jobs',{headers}),
    ])
    setItems(catalog.items);setJobs(history.items)
    let changed=false
    for(const job of history.items)if(job.status==='succeeded'&&!completed.current.has(job.id)){
      completed.current.add(job.id);changed=true
    }
    if(changed)onInstalled()
  }
  useEffect(()=>{let active=true
    const refresh=()=>{if(active)void load().catch(e=>{if(active)setError(String(e))}).finally(()=>{if(active)setLoading(false)})}
    refresh();const timer=window.setInterval(refresh,3000)
    return()=>{active=false;window.clearInterval(timer)}
  },[])
  async function install() {
    if(!selected||!accepted||busy||locked)return
    setBusy(true);setError('')
    try {
      const job=await asJson<Job>('/api/plugin-market/install',{method:'POST',headers,body:JSON.stringify({id:selected.id,revision:selected.revision,accept_code:true})})
      setJobs(previous=>[job,...previous.filter(row=>row.id!==job.id)].slice(0,10));setSelected(null);setAccepted(false)
    }catch(e){setError(String(e))}finally{setBusy(false)}
  }
  return <section className="plugin-market" aria-label="插件市场" aria-busy={loading||busy}>
    <div className="market-heading"><div><h3>插件市场</h3><p>按需安装，基础聊天无需全部装齐。</p></div><button onClick={()=>void load().then(()=>setError('')).catch(e=>setError(String(e)))} disabled={busy}>刷新目录</button></div>
    <p className="market-note">目录随内核更新。下载使用 GitHub 固定提交，不需要市场账号。插件是可信本机代码；安装后保持关闭，不自动启动 QQ、桌宠或调用模型。</p>
    {locked&&<p role="status">请先应用或放弃插件管理中的待应用修改，再安装新项目。</p>}
    {error&&<p role="alert" className="plugin-feedback error">{error}</p>}
    {loading&&<p role="status">正在加载可安装项目…</p>}
    <div className="market-grid">{items.map(item=><article className="market-card" key={item.id}>
      <div className="market-card-heading"><h4>{item.name}</h4><span className="market-badge">{item.kind==='plugin'?'插件':'可选依赖'}</span></div>
      <p>{item.description}</p><p className="market-size">{item.size}</p>
      {item.repository&&<a href={item.url} target="_blank" rel="noreferrer">GitHub · {item.repository}</a>}
      {!item.available&&<p>{item.reason}</p>}
      <button disabled={!item.available||item.installed||item.occupied||busy||running||locked} onClick={()=>{setSelected(item);setAccepted(false);setError('')}}>
        {item.installed?'已安装':!item.available?'暂未开放':item.occupied?'目录已存在，请检查':running?'等待当前安装完成':'查看并安装'}
      </button>
    </article>)}</div>
    {selected&&<div className="market-confirm" role="dialog" aria-modal="false" aria-label={`安装 ${selected.name}`}>
      <h4>安装 {selected.name}</h4><p>{selected.description}</p><p>预计下载：{selected.size}。来源：{selected.repository||'项目锁定的依赖与模型下载地址'}。</p>
      {selected.kind==='plugin'&&<p>固定版本：<code>{selected.revision}</code></p>}
      <p>安装会写入插件目录、后端虚拟环境或模型目录。失败可以重试；已下载的模型会复用。可能需要数分钟，不要在安装中关闭或重启后端。可选依赖不会自动卸载。</p>
      <label><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> 我同意从这些来源下载，并在本机安装可信代码和依赖。</label>
      <div className="market-actions"><button disabled={!accepted||busy||locked} onClick={()=>void install()}>{busy?'正在创建安装任务…':'确认安装'}</button><button disabled={busy} onClick={()=>setSelected(null)}>取消</button></div>
    </div>}
    {!!jobs.length&&<div className="market-jobs" aria-label="安装任务"><h4>最近安装</h4>{jobs.map(job=><div key={job.id} className={`market-job ${job.status}`} role={job.status==='failed'?'alert':'status'}><strong>{job.name} · {job.phase}</strong>{job.status==='running'&&<progress aria-label={`${job.name}安装进度`}/>}<p>{job.message||'正在后台安装，可继续查看页面。不要关闭后端。'}</p></div>)}</div>}
    <details className="market-network"><summary>网络失败怎么办？</summary><p>默认直连，不自动安装 VPN，也不自动切换第三方代理。GitHub 不可达时先检查本机已有代理与 Git 设置。模型可在你明确选择后，通过 HF_MIRROR、VOICE_MODEL_MIRROR 环境变量指定可信镜像，再重启后端后重试。镜像由第三方运营，项目不保证可用性。</p><p>联网搜索的 tools 插件尚未公开；这是仓库权限问题，代理无法解决。外部 Embedding API 可能收费，不能视为与本地检索效果完全相同。</p></details>
  </section>
}
