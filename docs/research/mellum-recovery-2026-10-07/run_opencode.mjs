import { cpSync, existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { mkdtempSync } from 'node:fs';

const root = mkdtempSync(join(tmpdir(), 'mellum-opencode-'));
const bundle = dirname(fileURLToPath(import.meta.url));
const [mode = 'retrieval', profile = 'clean'] = process.argv.slice(2);
const name = `${profile}-${mode}`;
if (!['configured', 'pure', 'clean'].includes(profile) || !['greeting', 'conversation', 'retrieval', 'coding'].includes(mode)) throw Error('Provide trial name, mode, profile');
const requestedCwd = join(root, name);
if (existsSync(requestedCwd)) throw Error('Refusing to overwrite existing trial');
mkdirSync(requestedCwd, {recursive:true});
const cwd = realpathSync(requestedCwd);
const fixtureSeed = Number(process.env.MELLUM_FIXTURE_SEED || '101');
if (mode === 'coding') cpSync(join(bundle, 'fixtures/coding'), cwd, { recursive:true });
else if (mode === 'retrieval') cpSync(join(bundle, `fixtures/retrieval-${fixtureSeed}`), cwd, { recursive:true });
else cpSync(join(bundle, 'fixtures/README.md'), join(cwd, 'README.md'));
const model = 'omlx/Mellum2.1-12B-A2.5B-Thinking-6bit';
const config = {
  model, small_model:model, share:'disabled', snapshot:false,
  agent:{build:{model}},
  provider:{omlx:{options:{baseURL:process.env.MELLUM_BASE_URL || 'http://127.0.0.1:8001/v1'}}},
};
const env = {...process.env, OPENCODE_CONFIG_CONTENT:JSON.stringify(config), OPENCODE_DISABLE_AUTOUPDATE:'1', OPENCODE_DISABLE_LSP_DOWNLOAD:'1'};
if (profile === 'clean') {
  env.OPENCODE_DISABLE_EXTERNAL_SKILLS='1';
  env.OPENCODE_DISABLE_CLAUDE_CODE='1';
  config.skills={paths:[]};
  config.instructions=[];
  config.agent.build.temperature=0;
  config.agent.build.steps=12;
  config.provider.omlx.models={'Mellum2.1-12B-A2.5B-Thinking-6bit':{
    limit:{context:56000,input:51904,output:4096},
    options:{chat_template_kwargs:{enable_thinking:true,preserve_thinking:true},top_p:1,top_k:0,min_p:0,seed:42},
  }};
  config.permission={ '*':'deny', read:'allow', grep:'allow', glob:'allow', list:'allow', edit:'allow', bash:'allow' };
  env.OPENCODE_CONFIG_CONTENT=JSON.stringify(config);
}
const prompts = mode === 'greeting' ? ['Hello'] : mode === 'conversation' ? [
  'Hello',
  'What is this project about? Read README.md and answer directly in no more than three sentences.',
  'Why did you use brainstorming for that informational question? Explain your actual actions directly; do not invoke tools or start another workflow.',
] : mode === 'retrieval' ? [
  `Use grep to search ${cwd}/source.py for the literal terms START_TOKEN, MIDDLE_TOKEN, and END_TOKEN separately. Retrieve only assignment lines from that exact file; ignore obsolete.py. After the tool results, return only the three values, separated by single spaces, in START_TOKEN, MIDDLE_TOKEN, END_TOKEN order. Do not read the entire source file.`,
] : [
  "Fix totalCents(items) in calculator.js so it correctly totals each item's unit price in cents multiplied by its quantity. Keep the exported API and the tests unchanged. Read the relevant files, make the smallest fix, and run node --test calculator.test.js. Explain the result in one sentence. This is a bounded bug fix; no brainstorming or delegation is needed.",
];
const summaries=[];
let session;
for (const [index,prompt] of prompts.entries()) {
  const args=['run','--dir',cwd,'--model',model,'--agent','build','--format','json','--title',`Mellum diagnostic ${name}`];
  if(profile==='clean' || profile==='pure')args.push('--pure');
  if(session)args.push('--session',session);
  args.push(prompt);
  const started=Date.now();
  const result=spawnSync('opencode',args,{cwd,env,encoding:'utf8',timeout:240000,maxBuffer:32*1024*1024});
  const stem=join(root,`${name}-turn-${index+1}`);
  writeFileSync(stem+'.events.jsonl',result.stdout||'');
  writeFileSync(stem+'.stderr.log',result.stderr||'');
  const events=(result.stdout||'').split('\n').filter(Boolean).flatMap(line=>{try{return[JSON.parse(line)];}catch{return[];}});
  session=events.find(row=>row.sessionID)?.sessionID || session;
  const texts=events.filter(e=>e.type==='text').map(e=>e.part?.text||'');
  summaries.push({turn:index+1,started,ended:Date.now(),exitCode:result.status,signal:result.signal,error:result.error?.message,sessionID:session,eventTypes:events.map(e=>e.type),text:texts.join(''),eventErrors:events.filter(e=>e.type==='error')});
  writeFileSync(join(root,name+'.summary.json'),JSON.stringify({name,mode,profile,fixtureSeed,runDir:root,cwd,config,turns:summaries},null,2));
  if(result.status!==0 || summaries.at(-1).eventErrors.length)break;
}
if(mode==='coding') {
  const result=spawnSync('node',['--test','calculator.test.js'],{cwd,encoding:'utf8'});
  writeFileSync(join(root,name+'.independent-tests.log'),result.stdout+result.stderr);
  const summary=JSON.parse(readFileSync(join(root,name+'.summary.json'),'utf8'));
  summary.codingVerification={exitCode:result.status,testsUnchanged:readFileSync(join(cwd,'calculator.test.js'),'utf8')===readFileSync(join(bundle,'fixtures/coding/calculator.test.js'),'utf8'),source:readFileSync(join(cwd,'calculator.js'),'utf8')};
  writeFileSync(join(root,name+'.summary.json'),JSON.stringify(summary,null,2));
}
const finalSummary=JSON.parse(readFileSync(join(root,name+'.summary.json'),'utf8'));
if(mode==='retrieval') {
  finalSummary.expectedFinal=JSON.parse(readFileSync(join(bundle,'pi-goldens.json'),'utf8')).find(g=>g.seed===fixtureSeed).expected_final;
  finalSummary.retrievalPassed=finalSummary.turns.at(-1)?.text.trim()===finalSummary.expectedFinal;
}
writeFileSync(join(root,name+'.summary.json'),JSON.stringify(finalSummary,null,2));
console.log(JSON.stringify(finalSummary,null,2));
if(finalSummary.turns.some(t=>t.exitCode!==0 || t.eventErrors.length) || finalSummary.retrievalPassed===false
  || finalSummary.codingVerification?.exitCode || finalSummary.codingVerification?.testsUnchanged===false)process.exitCode=1;
// For final-stop/tool-error verification, run inspect_opencode.mjs against runDir.
