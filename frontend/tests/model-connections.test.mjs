import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import ts from 'typescript'

async function moduleFrom(source) {
  const result=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.ESNext}})
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

test('gallery ignores retired browser endpoints and keys but keeps prompt-channel preference',async()=>{
  const source=await readFile(new URL('../src/lib/visionRoute.ts',import.meta.url),'utf8')
  const helpers=await moduleFrom(source)
  globalThis.localStorage={getItem:()=>JSON.stringify({channel:'uncensored',baseUrl:'https://old.invalid',
    apiKey:'retired-key',chatModel:'old-chat',visionModel:'old-vision',uncensoredBaseUrl:'https://other.invalid'})}
  try {
    assert.deepEqual(helpers.visionRoute(),{baseUrl:'',apiKey:'',model:''})
    assert.deepEqual(helpers.visionRoute('chat'),{baseUrl:'',apiKey:'',model:''})
    assert.equal(helpers.isUncensoredChannel(),true)
  }finally{delete globalThis.localStorage}
})

test('prompt-channel switching cannot select another model connection or leak a chat key to vision',async()=>{
  const source=await readFile(new URL('../src/components/ChatView.tsx',import.meta.url),'utf8')
  const file=ts.createSourceFile('ChatView.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
  const node=file.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='resolveRoute')
  assert.ok(node)
  const {resolveRoute}=await moduleFrom(node.getText(file))
  const config={baseUrl:'https://chat.invalid/v1',apiKey:'chat-key',chatModel:'chat-model',
    visionBaseUrl:'https://vision.invalid/v1',visionApiKey:'',visionModel:'vision-model',
    channel:'normal',uncensoredBaseUrl:'https://retired.invalid/v1',uncensoredApiKey:'old-key',uncensoredChatModel:'old-model'}
  const normal=resolveRoute(config)
  assert.deepEqual(resolveRoute({...config,channel:'uncensored'}),normal)
  assert.equal(normal.vision.apiKey,'')
  assert.equal(resolveRoute({...config,visionBaseUrl:config.baseUrl}).vision.apiKey,'chat-key')
})
