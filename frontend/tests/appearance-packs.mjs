// Browser integration with synthetic API. Real ZIP/parser/auth are tested in Python.
import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {mkdir,readFile} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {chromium} from '@playwright/test'
import {build} from './feature-build.mjs'

const root=fileURLToPath(new URL('../',import.meta.url))
const manifest=JSON.parse(await readFile(root+'../examples/appearance-packs/paper-ink/theme.json','utf8'))
const pack={...manifest,source:'imported'}
const bundle=await build({stdin:{contents:`
  import React from 'react';import{createRoot}from'react-dom/client';
  import AppearanceSwitcher from './src/visual/AppearanceSwitcher';
  import{initializeAppearancePacks}from'./src/visual/appearancePacks';
  import{applyCorePalette,readCorePalette}from'./src/visual/coreAppearance';
  applyCorePalette(readCorePalette());initializeAppearancePacks();
  createRoot(document.getElementById('root')).render(<><AppearanceSwitcher/><div className="core-character">Assistant · Example message</div></>);
`,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'esm',platform:'browser',jsx:'automatic'})
const css=(await Promise.all(['index.css','visual/core-appearance.css','visual/core-layout.css','visual/neutral-polish.css','visual/appearance-packs.css'].map(name=>readFile(root+'src/'+name,'utf8')))).join('\n')
const server=createServer((req,res)=>{
  res.setHeader('Content-Type',req.url==='/app.js'?'text/javascript':req.url==='/app.css'?'text/css':'text/html')
  res.end(req.url==='/app.js'?bundle.outputFiles[0].text:req.url==='/app.css'?css:'<html data-core-ui="true"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/app.css"><main id="root" style="margin:24px;display:flex;align-items:flex-start;justify-content:flex-end"></main><script type="module" src="/app.js"></script>')
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let browser
try {
  browser=await chromium.launch({headless:true,executablePath:process.argv[2]||process.env.CHROME_PATH})
  const page=await browser.newPage({viewport:{width:1050,height:900}})
  const errors=[];let installed=false,failList=false;let installs=0,deletes=0,loads=0
  page.on('pageerror',error=>errors.push(error.message))
  await page.route('**/api/appearance-packs**',async route=>{
    const request=route.request(),url=new URL(request.url())
    assert.equal(request.headers()['x-exploration-dashboard'],'1')
    if(failList&&request.method()==='GET')return route.fulfill({status:503,json:{detail:'测试连接失败'}})
    let data
    if(url.pathname.endsWith('/preview'))data={token:'a'.repeat(32),manifest,size:4096}
    else if(url.pathname.endsWith('/install')){assert.equal(request.postDataJSON().token,'a'.repeat(32));installs++;installed=true;data={id:pack.id}}
    else if(request.method()==='DELETE'){installed=false;deletes++;data={ok:true}}
    else data={items:installed?[pack]:[],errors:[]}
    await route.fulfill({json:data})
  })
  page.on('load',()=>loads++)
  await page.goto(`http://127.0.0.1:${server.address().port}`)
  await page.getByLabel('外观',{exact:true}).click()
  await page.getByText('当前：内置配色。',{exact:false}).waitFor()
  await page.getByLabel('选择外观包 ZIP').setInputFiles({name:'paper-ink.zip',mimeType:'application/zip',buffer:Buffer.from('synthetic preview; real ZIP covered by Python tests')})
  const preview=page.getByRole('region',{name:'外观包安装确认'})
  await preview.waitFor()
  assert.equal(await preview.getByRole('button',{name:'确认安装'}).isDisabled(),true)
  await preview.getByRole('checkbox').check()
  await preview.getByRole('button',{name:'确认安装'}).click()
  await page.getByText('安装完成，点击“应用外观”后生效。',{exact:true}).waitFor()
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.appearancePack),undefined)
  await page.getByRole('button',{name:'应用外观',exact:true}).click()
  await page.waitForFunction(()=>document.documentElement.dataset.appearancePack==='paper-ink')
  assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('--bg')),manifest.colors.light.background)
  assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('--r-md')),'12px')
  await page.evaluate(()=>document.documentElement.classList.add('dark'))
  await page.waitForFunction(color=>document.documentElement.style.getPropertyValue('--bg')===color,manifest.colors.dark.background)
  assert.equal(loads,1,'applying packs or switching dark mode must not reload the page')
  await page.reload()
  await page.waitForFunction(()=>document.documentElement.dataset.appearancePack==='paper-ink')
  await page.getByLabel('外观',{exact:true}).click()
  await page.getByRole('button',{name:'森林绿'}).click()
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.appearancePack),undefined)
  assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('--bg')),'')
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.corePalette),'green')
  await page.getByLabel('已安装的外观').selectOption('paper-ink')
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.appearancePack),undefined,'selection is staged until apply')
  await page.getByRole('button',{name:'应用外观',exact:true}).click()
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  const bounds=await page.locator('.core-appearance-panel').boundingBox()
  assert.ok(bounds.x>=0&&bounds.y>=0&&bounds.x+bounds.width<=390&&bounds.y+bounds.height<=844,'panel must fit the viewport, including its left edge and bottom')
  await mkdir(root+'artifacts/appearance-packs',{recursive:true})
  await page.screenshot({path:root+'artifacts/appearance-packs/mobile.png',fullPage:true})
  await page.setViewportSize({width:1050,height:900})
  await page.screenshot({path:root+'artifacts/appearance-packs/desktop.png',fullPage:true})
  await page.getByText('移除此外观包',{exact:true}).click()
  await page.getByRole('button',{name:'确认移除',exact:true}).click()
  await page.getByText('外观包已移除，本机备份保留。',{exact:true}).waitFor()
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.appearancePack),undefined)
  failList=true
  await page.getByRole('button',{name:'刷新列表'}).click()
  await page.getByRole('alert').filter({hasText:'测试连接失败'}).waitFor()
  assert.equal(installs,1);assert.equal(deletes,1);assert.deepEqual(errors,[])
  console.log('PASS: preview/consent, staged install/apply, light/dark, reload persistence, preset reset, removal, failed refresh and mobile layout. Synthetic API only.')
} finally {await browser?.close();await new Promise(resolve=>server.close(resolve))}
