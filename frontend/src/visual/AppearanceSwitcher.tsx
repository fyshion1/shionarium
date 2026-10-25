import {useRef,useState,useSyncExternalStore} from 'react'
import {useDismissableDetails} from './useDismissableDetails'
import {applyCorePalette,corePalettes,readCorePalette} from './coreAppearance'
import {appearanceRequest,getAppearanceSnapshot,refreshAppearancePacks,selectAppearancePack,subscribeAppearance,type AppearancePack} from './appearancePacks'

export default function AppearanceSwitcher() {
  const [palette,setPalette]=useState(readCorePalette)
  const ref=useDismissableDetails()
  const packs=useSyncExternalStore(subscribeAppearance,getAppearanceSnapshot)
  const [draft,setDraft]=useState(()=>packs.selectedId||'')
  const [preview,setPreview]=useState<{token:string;manifest:AppearancePack;size:number}|null>(null)
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const [consent,setConsent]=useState(false)
  const fileInput=useRef<HTMLInputElement>(null)
  const current=packs.items.find(item=>item.id===packs.selectedId)
  const selectedDraft=packs.items.find(item=>item.id===draft)
  async function run(action:()=>Promise<void>) {
    setBusy(true);setMessage('')
    try {await action()} catch(error) {setMessage(error instanceof Error?error.message:'操作失败，请重试')}
    finally {setBusy(false)}
  }
  return <details ref={ref} className="core-appearance">
    <summary aria-label="外观">外观</summary>
    <section aria-label="外观预设" className="core-appearance-panel">
      <h2>外观</h2><p>选择常用配色，日夜模式沿用当前设置。偏好保存在此浏览器。</p>
      <div className="core-palette-options">{corePalettes.map(item=><button type="button" key={item.id} aria-pressed={!packs.selectedId&&palette===item.id} onClick={()=>{selectAppearancePack(null);setDraft('');setPalette(item.id);applyCorePalette(item.id);setMessage('已使用内置配色。')}}>
        <span aria-hidden="true" className="core-palette-swatches">{item.colors.map(color=><i key={color} style={{background:color}}/>)}</span>
        {item.name}<span aria-hidden="true">{!packs.selectedId&&palette===item.id?' ✓':''}</span>
      </button>)}</div>
      <div className="appearance-pack-section" aria-label="外观包">
        <h3>外观包</h3>
        <p>当前：{current?current.name:'内置配色'}。外观包只改变显示，不包含角色或记忆。</p>
        <label htmlFor="appearance-pack-choice">已安装的外观</label>
        <select id="appearance-pack-choice" value={selectedDraft?draft:''} disabled={busy||packs.loading} onChange={event=>setDraft(event.target.value)}>
          <option value="">选择外观包</option>
          {packs.items.map(item=><option value={item.id} key={item.id}>{item.name} · {item.version}</option>)}
        </select>
        {draft&&<p>{packs.items.find(item=>item.id===draft)?.description}</p>}
        <div className="appearance-pack-actions">
          <button type="button" disabled={busy||packs.loading||!selectedDraft||draft===packs.selectedId} onClick={()=>{
            try {selectAppearancePack(draft);setMessage('外观已应用，无需刷新。')}
            catch(error) {setMessage(error instanceof Error?error.message:'外观已不可用，请刷新列表')}
          }}>应用外观</button>
          <button type="button" disabled={busy||packs.loading} onClick={()=>void refreshAppearancePacks()}>刷新列表</button>
        </div>
        {current&&<p>{current.author} · {current.license}</p>}
        <input ref={fileInput} type="file" accept=".zip,application/zip" aria-label="选择外观包 ZIP" disabled={busy} onChange={event=>{
          const file=event.target.files?.[0];event.target.value=''
          if(!file)return
          setPreview(null);setConsent(false)
          void run(async()=>{
            if(file.size>20*1024*1024)throw new Error('外观包不能超过 20 MB')
            const form=new FormData();form.append('file',file)
            setPreview(await appearanceRequest('/preview',{method:'POST',body:form}))
          })
        }}/>
        {preview&&<section className="appearance-pack-preview" aria-label="外观包安装确认">
          <h4>{preview.manifest.name} · {preview.manifest.version}</h4>
          <p>{preview.manifest.description}</p>
          <div className="appearance-pack-samples" aria-label="日夜配色预览">{(['light','dark'] as const).map(mode=>{
            const colors=preview.manifest.colors[mode]
            return <div key={mode} style={{background:colors.background,color:colors.text,borderColor:colors.border,borderRadius:preview.manifest.radius}}>
              {mode==='light'?'日间':'夜间'}<span style={{color:colors.accent_text}}> · 强调色</span>
            </div>
          })}</div>
          <p>作者：{preview.manifest.author}<br/>许可：{preview.manifest.license}<br/>大小：{(preview.size/1024).toFixed(1)} KB</p>
          <p>将保存在本机。安装后保持未应用，字体和背景只读取包内资源。</p>
          <label><input type="checkbox" checked={consent} onChange={event=>setConsent(event.target.checked)} disabled={busy}/>我已阅读许可并同意安装</label>
          <div className="appearance-pack-actions">
            <button type="button" disabled={!consent||busy} onClick={()=>void run(async()=>{
              const result=await appearanceRequest<{id:string}>('/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:preview.token})})
              setPreview(null);await refreshAppearancePacks();setDraft(result.id);setMessage('安装完成，点击“应用外观”后生效。')
            })}>确认安装</button>
            <button type="button" disabled={busy} onClick={()=>setPreview(null)}>取消</button>
          </div>
        </section>}
        {draft&&packs.items.find(item=>item.id===draft)?.source==='imported'&&<details className="appearance-pack-remove">
          <summary>移除此外观包</summary><p>移除后保留本机备份；已在此浏览器应用时恢复内置配色。</p>
          <button type="button" disabled={busy} onClick={()=>void run(async()=>{
            await appearanceRequest('/'+encodeURIComponent(draft),{method:'DELETE'})
            setDraft('');await refreshAppearancePacks();setMessage('外观包已移除，本机备份保留。')
          })}>确认移除</button>
        </details>}
        {busy&&<p role="status">正在处理外观包…</p>}
        {packs.loading&&<p role="status">正在读取外观…</p>}
        {message&&<p role="status">{message}</p>}
        {packs.error&&<p role="alert">{packs.error}</p>}
        {packs.errors.map(error=><p role="alert" key={error.folder}>{error.folder}：{error.message}</p>)}
      </div>
    </section>
  </details>
}
