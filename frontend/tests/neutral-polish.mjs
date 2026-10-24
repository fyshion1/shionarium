// Browser CSS checks; static synthetic content and no backend connections.
import assert from 'node:assert/strict'
import {readFile, mkdir} from 'node:fs/promises'
import {chromium} from '@playwright/test'
const root=new URL('../', import.meta.url)
const css=(await Promise.all(['index.css','visual/core-appearance.css','visual/core-layout.css','visual/neutral-polish.css'].map(file=>readFile(new URL('src/'+file,root),'utf8')))).join('\n')
const browser=await chromium.launch({headless:true,executablePath:process.argv[2]})
try {
  const page=await browser.newPage({viewport:{width:1100,height:800}})
  await page.setContent(`<html data-core-ui="true" data-core-palette="warm"><style>${css}</style><main style="max-width:880px;margin:24px auto;padding:20px"><header class="topbar"><div class="core-bar-inner"><strong>Shionarium</strong>　聊天　助手　记忆　设置</div></header><section class="visual-chat-reading" style="padding:24px;min-height:180px"><p>助手 · 通用对话</p><div style="padding:16px;background:var(--surface);color:var(--text);border-radius:18px">你好，可以从这里创建助手并开始聊天。</div></section><div class="chat-composer-footer"><textarea class="composer-textarea" aria-label="消息" placeholder="输入消息…"></textarea><button class="composer-send">发送</button></div><p><label>模型连接　<input placeholder="服务地址"></label></p><details><summary>插件市场</summary>安装不会自动启用插件。</details></main></html>`)
  await mkdir(new URL('artifacts/neutral-polish/',root),{recursive:true})
  for(const dark of [false,true]) for(const palette of ['warm','slate','blue','green']) {
    await page.evaluate(({dark,palette})=>{document.documentElement.classList.toggle('dark',dark);document.documentElement.dataset.corePalette=palette},{dark,palette})
    const styles=await page.evaluate(()=>{
      const style=getComputedStyle(document.documentElement)
      const color=value=>{
        const c=document.createElement('canvas');c.width=c.height=1
        const ctx=c.getContext('2d');ctx.fillStyle=value;ctx.fillRect(0,0,1,1)
        return [...ctx.getImageData(0,0,1,1).data].slice(0,3)
      }
      return {ink:color(style.getPropertyValue('--text')),bg:color(style.getPropertyValue('--bg')),buttonRadius:getComputedStyle(document.querySelector('.composer-send')).borderRadius}
    })
    const luminance=rgb=>rgb.map(c=>c/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4).reduce((s,c,i)=>s+c*[.2126,.7152,.0722][i],0)
    const [a,b]=[luminance(styles.ink),luminance(styles.bg)].sort((a,b)=>b-a)
    assert.ok((a+.05)/(b+.05)>=4.5,`body contrast ${palette} dark=${dark}`)
    assert.equal(styles.buttonRadius,'12px')
    if(palette==='warm')await page.screenshot({path:new URL(`artifacts/neutral-polish/${dark?'dark':'light'}.png`,root).pathname.replace(/^\/([A-Z]:)/,'$1'),fullPage:true})
  }
  await page.evaluate(()=>document.documentElement.removeAttribute('data-core-ui'))
  assert.notEqual(await page.locator('.composer-send').evaluate(el=>getComputedStyle(el).borderRadius),'12px','polish must not leak into optional theme')
  console.log('PASS: four neutral palettes, light/dark body contrast and theme isolation; static fixture only.')
} finally {await browser.close()}
