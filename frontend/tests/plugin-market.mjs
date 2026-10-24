// Real browser, synthetic API and downloads; never touches the user's live backend.
import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {mkdir,readFile,readdir} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {build} from './feature-build.mjs'
import {chromium} from '@playwright/test'

const root=fileURLToPath(new URL('../',import.meta.url))
const bundle=await build({stdin:{contents:`import React from 'react';import{createRoot}from'react-dom/client';import PluginManager from './src/components/PluginManager';createRoot(document.getElementById('root')).render(<PluginManager/>);`,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'esm',platform:'browser',jsx:'automatic'})
const cssFile=(await readdir(root+'dist/assets')).find(name=>name.endsWith('.css'))
const css=await readFile(root+'dist/assets/'+cssFile,'utf8')
const server=createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/app.js'?'text/javascript':req.url==='/app.css'?'text/css':'text/html');res.end(req.url==='/app.js'?bundle.outputFiles[0].text:req.url==='/app.css'?css:'<html data-core-ui="true" data-core-palette="warm"><link rel="stylesheet" href="/app.css"><main style="max-width:1000px;margin:auto;padding:16px" id="root"></main><script type="module" src="/app.js"></script>')})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let browser
try{
  browser=await chromium.launch({executablePath:process.argv[2]||process.env.CHROME_PATH,headless:true})
  const page=await browser.newPage({viewport:{width:1100,height:1000}})
  const errors=[];page.on('pageerror',error=>errors.push(error.message))
  let jobs=[],requests=0,success=false
  const items=[
    {id:'desktop_pet',name:'桌宠',kind:'plugin',description:'桌面聊天',size:'数百 MB',revision:'test',available:true},
    {id:'tools',name:'联网搜索',kind:'plugin',description:'网络搜索',size:'可选依赖',revision:'test',available:false,reason:'插件仓库尚未公开'},
    {id:'local_voice',name:'本地说话与听写',kind:'component',description:'ASR 把声音转文字，TTS 把回复念出来',size:'数百 MB',revision:'test',available:true},
  ]
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url());let data={items:[]}
    if(url.pathname==='/api/plugin-market')data={items:items.map(item=>({...item,installed:success&&item.id==='local_voice',occupied:false}))}
    else if(url.pathname==='/api/plugin-market/jobs')data={items:jobs.map(job=>success?{...job,status:'succeeded',phase:'安装完成',message:'组件已安装，请重启后端。'}:job)}
    else if(url.pathname==='/api/plugin-market/install'){
      const body=route.request().postDataJSON();assert.equal(body.accept_code,true);assert.equal(body.id,'local_voice');requests++
      const job={id:'a'.repeat(32),item_id:body.id,name:'本地说话与听写',status:'running',phase:'安装运行库与模型',message:''};jobs=[job];data=job
    }
    else if(url.pathname==='/api/character-packs/catalog')data={items:[],errors:[]}
    await route.fulfill({json:data})
  })
  await page.goto(`http://127.0.0.1:${server.address().port}`)
  const market=page.getByRole('region',{name:'插件市场',exact:true})
  await market.getByRole('button',{name:'暂未开放'}).waitFor()
  assert.equal(await market.getByRole('button',{name:'暂未开放'}).isDisabled(),true)
  const voice=market.locator('article').filter({has:page.getByRole('heading',{name:'本地说话与听写',exact:true})})
  await voice.getByRole('button',{name:'查看并安装'}).click()
  const dialog=market.getByRole('dialog')
  assert.equal(await dialog.getByRole('button',{name:'确认安装',exact:true}).isDisabled(),true)
  await dialog.getByRole('checkbox').check();await dialog.getByRole('button',{name:'确认安装',exact:true}).click()
  await market.getByRole('progressbar').waitFor();assert.equal(requests,1)
  await page.reload();await page.getByRole('progressbar').waitFor();assert.equal(requests,1)
  success=true
  await page.getByText('组件已安装，请重启后端。',{exact:true}).waitFor()
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  const output=root+'artifacts/plugin-market';await mkdir(output,{recursive:true});await page.screenshot({path:output+'/mobile.png',fullPage:true})
  await page.setViewportSize({width:1100,height:1000});await page.screenshot({path:output+'/desktop.png',fullPage:true})
  assert.deepEqual(errors,[])
  console.log('PASS: empty install browsing, private source notice, explicit consent, task recovery after reload, completion, and mobile layout; synthetic downloads only.')
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
