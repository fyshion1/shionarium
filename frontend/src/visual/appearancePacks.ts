/** Appearance API v1: semantic data, never package-supplied CSS or JavaScript. */
export const appearanceVariables = {
  background:'--bg', background_soft:'--bg-soft', surface:'--surface', surface_raised:'--surface-2',
  text:'--text', text_muted:'--text-2', text_subtle:'--text-3', border:'--border', border_strong:'--border-strong',
  accent:'--pink', accent_text:'--pink-deep', accent_soft:'--pink-soft', mint:'--mint', sky:'--sky',
} as const
export type AppearanceColors = Record<keyof typeof appearanceVariables,string>
export type AppearancePack = {
  format:'appearance-pack'; format_version:1; id:string; name:string; version:string; author:string
  license:string; description:string; colors:{light:AppearanceColors;dark:AppearanceColors}
  radius:number; font:'system'|'serif'|'monospace'; font_file:string|null
  background_file:string|null; background_opacity:number; assets:Record<string,string>
  source:'imported'|'plugin'
}
type Snapshot = {
  items:AppearancePack[]; errors:{folder:string;message:string}[]; loading:boolean
  error:string; selectedId:string|null
}
export const appearanceHeaders = {'X-Exploration-Dashboard':'1'}
const storageKey='shionarium.appearance-pack.v1'
function savedId() {try {return localStorage.getItem(storageKey)} catch {return null}}
let snapshot:Snapshot={items:[],errors:[],loading:true,error:'',selectedId:savedId()}
const listeners=new Set<()=>void>()
export const subscribeAppearance=(listener:()=>void)=>{listeners.add(listener);return ()=>{listeners.delete(listener)}}
export const getAppearanceSnapshot=()=>snapshot
function update(value:Partial<Snapshot>) {snapshot={...snapshot,...value};listeners.forEach(listener=>listener())}
let observer:MutationObserver|undefined
let initialized=false
let refreshGeneration=0

export async function appearanceRequest<T>(url:string,init:RequestInit={}):Promise<T> {
  const response=await fetch('/api/appearance-packs'+url,{...init,headers:{...appearanceHeaders,...init.headers}})
  const data=await response.json()
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'外观包操作失败，请重试')
  return data as T
}

function resource(pack:AppearancePack,name:string) {
  return `/api/appearance-packs/${encodeURIComponent(pack.id)}/assets/${encodeURIComponent(name.slice('assets/'.length))}?sha256=${pack.assets[name]}`
}
function renderPack() {
  const root=document.documentElement
  const pack=snapshot.items.find(item=>item.id===snapshot.selectedId)
  for(const variable of Object.values(appearanceVariables))root.style.removeProperty(variable)
  for(const variable of ['--r-sm','--r-md','--r-lg','--polish-font','--appearance-font','--appearance-background','--appearance-background-opacity'])root.style.removeProperty(variable)
  document.getElementById('appearance-pack-font')?.remove()
  delete root.dataset.appearancePack
  if(!pack)return
  root.dataset.appearancePack=pack.id
  const colors=pack.colors[root.classList.contains('dark')?'dark':'light']
  for(const [name,variable] of Object.entries(appearanceVariables))root.style.setProperty(variable,colors[name as keyof AppearanceColors])
  root.style.setProperty('--r-sm',`${Math.round(pack.radius/2)}px`)
  root.style.setProperty('--r-md',`${pack.radius}px`)
  root.style.setProperty('--r-lg',`${pack.radius===0?0:pack.radius+6}px`)
  const font={system:'ui-sans-serif,system-ui,sans-serif',serif:'ui-serif,Georgia,"Noto Serif CJK SC",serif',monospace:'ui-monospace,Consolas,monospace'}[pack.font]
  if(pack.font_file) {
    const style=document.createElement('style');style.id='appearance-pack-font'
    style.textContent=`@font-face{font-family:ShionariumAppearancePack;src:url("${resource(pack,pack.font_file)}") format("woff2");font-display:swap;}`
    document.head.append(style)
  }
  const family=pack.font_file?`ShionariumAppearancePack,${font}`:font
  root.style.setProperty('--appearance-font',family)
  root.style.setProperty('--polish-font',family)
  if(pack.background_file) {
    root.style.setProperty('--appearance-background',`url("${resource(pack,pack.background_file)}")`)
    root.style.setProperty('--appearance-background-opacity',String(pack.background_opacity))
  }
}

export function selectAppearancePack(id:string|null) {
  if(id&&!snapshot.items.some(item=>item.id===id))throw new Error('外观包已不可用，请刷新列表')
  update({selectedId:id})
  try {if(id)localStorage.setItem(storageKey,id);else localStorage.removeItem(storageKey)} catch { /* Browser session only. */ }
  renderPack()
}

export async function refreshAppearancePacks() {
  const generation=++refreshGeneration
  update({loading:true,error:''})
  try {
    const data=await appearanceRequest<Pick<Snapshot,'items'|'errors'>>('')
    if(generation!==refreshGeneration)return
    if(!Array.isArray(data.items)||!Array.isArray(data.errors))throw new Error('外观列表返回格式不正确，请检查后端版本')
    update({...data,loading:false})
    if(snapshot.selectedId&&!snapshot.items.some(item=>item.id===snapshot.selectedId)) {
      selectAppearancePack(null)
      update({error:'原外观包已移除或不可用，已恢复内置配色。'})
    } else renderPack()
  } catch(error) {
    if(generation===refreshGeneration)update({loading:false,error:error instanceof Error?error.message:'外观列表加载失败'})
  }
}

export function initializeAppearancePacks() {
  if(initialized)return
  initialized=true
  let dark=document.documentElement.classList.contains('dark')
  observer=new MutationObserver(()=>{
    const next=document.documentElement.classList.contains('dark')
    if(next!==dark){dark=next;renderPack()}
  })
  observer.observe(document.documentElement,{attributes:true,attributeFilter:['class']})
  void refreshAppearancePacks()
}
