import { readFileSync, readdirSync, writeFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import { resolve } from 'node:path';

if(!process.argv[2])throw Error('Usage: node inspect_opencode.mjs /path/to/runDir');
const root=resolve(process.argv[2]);
const database=process.env.OPENCODE_DIAGNOSTIC_DB || homedir()+'/.local/share/opencode/opencode.db';
const query=sql=>{
  const result=spawnSync('sqlite3',['-readonly','-json',database,sql],{encoding:'utf8',maxBuffer:32*1024*1024});
  if(result.status!==0)throw Error(result.stderr);
  return result.stdout.trim()?JSON.parse(result.stdout):[];
};
const hash=text=>createHash('sha256').update(text).digest('hex');
const sanitize=value=>JSON.parse(JSON.stringify(value).replaceAll(homedir(),'<HOME>').replaceAll('/private'+root,'<WORKDIR>').replaceAll(root,'<WORKDIR>').replace(/\/(?:private\/)?var\/folders\/[^/]+\/[^/]+\/T/g,'<OS_TEMP>').replace(/http:\/\/127\.0\.0\.1:\d+\/[^/]+\/v1/g,'<DIAGNOSTIC_PROXY>/v1'));
const summaries=readdirSync(root).filter(f=>f.endsWith('.summary.json')).map(f=>JSON.parse(readFileSync(root+'/'+f,'utf8')));
const requests=existsSync(root+'/requests.jsonl')?readFileSync(root+'/requests.jsonl','utf8').trim().split('\n').filter(Boolean).map(JSON.parse):[];
const trials=[];
for(const summary of summaries){
  const sid=summary.turns[0]?.sessionID;
  if(!sid || !/^ses_[A-Za-z0-9]+$/.test(sid)){trials.push({summary,unrecorded:true});continue;}
  const sessions=query(`WITH RECURSIVE descendants(id) AS (SELECT '${sid}' UNION ALL SELECT s.id FROM session s JOIN descendants d ON s.parent_id=d.id) SELECT id,parent_id,title,directory,model,agent,version,tokens_input,tokens_output,tokens_reasoning,tokens_cache_read,tokens_cache_write,time_created,time_updated FROM session WHERE id IN (SELECT id FROM descendants)`);
  const ids=sessions.map(s=>`'${s.id}'`).join(',');
  const messages=query(`SELECT id,session_id,time_created,time_updated,data FROM message WHERE session_id IN (${ids}) ORDER BY time_created,id`).map(m=>({...m,data:JSON.parse(m.data)}));
  const parts=query(`SELECT id,message_id,session_id,time_created,time_updated,data FROM part WHERE session_id IN (${ids}) ORDER BY time_created,id`).map(p=>({...p,data:JSON.parse(p.data)}));
  const events=query(`SELECT type,COUNT(*) AS count,MIN(seq) AS first_seq,MAX(seq) AS last_seq FROM event WHERE aggregate_id IN (${ids}) GROUP BY type`);
  const projectedEvents=query(`SELECT type,COUNT(*) AS count FROM session_message WHERE session_id IN (${ids}) GROUP BY type`);
  const rootMessages=messages.filter(m=>m.session_id===sid);
  const turns=[];
  for(const message of rootMessages){
    const data=message.data;
    if(data.role==='user'){turns.push({user_message_id:message.id,assistant_messages:[]});continue;}
    if(data.role!=='assistant')continue;
    const msgParts=parts.filter(p=>p.message_id===message.id).map(p=>p.data);
    const tokens=data.tokens||{};
    const record={id:message.id,provider:data.providerID,model:data.modelID,agent:data.agent,finish:data.finish,error:data.error,tokens,context_tokens:(tokens.input||0)+(tokens.cache?.read||0),text:msgParts.filter(p=>p.type==='text').map(p=>p.text).join('').trim(),reasoning:msgParts.filter(p=>p.type==='reasoning').map(p=>({characters:p.text?.length||0,sha256:hash(p.text||''),preview:(p.text||'').slice(0,160)})),tool_calls:msgParts.filter(p=>p.type==='tool').map(p=>({tool:p.tool,callID:p.callID,state:p.state})),time:data.time};
    turns.at(-1)?.assistant_messages.push(record);
  }
  for(const turn of turns){const last=turn.assistant_messages.at(-1);turn.final=last?.text;turn.final_finish=last?.finish;turn.tool_error_count=turn.assistant_messages.flatMap(m=>m.tool_calls).filter(t=>t.state?.status==='error').length;turn.maximum_context_tokens=Math.max(0,...turn.assistant_messages.map(m=>m.context_tokens));turn.completed_substantive_answer=last?.finish==='stop'&&Boolean(last?.text);}
  const requestSummaries=requests.filter(r=>r.trial===summary.name).map(r=>{
    const p=r.payload||{};
    const file=`${root}/${r.trial}-request-${r.id}.response.sse`;
    const oldFile=`${root}/request-${r.id}.response.sse`;
    const responseFile=existsSync(file)?file:r.trial==='configured-fixture-conversation'&&existsSync(oldFile)?oldFile:undefined;
    const sse=responseFile?readFileSync(responseFile,'utf8'):undefined;
    const chunks=sse?.split('\n').filter(line=>line.startsWith('data: ')&&line!=='data: [DONE]').flatMap(line=>{try{return[JSON.parse(line.slice(6))];}catch{return[];}});
    return {id:r.id,time:r.time,url:r.url,parameters:Object.fromEntries(Object.entries(p).filter(([k])=>!['messages','tools'].includes(k))),tool_names:p.tools?.map(t=>t.function?.name),messages:p.messages?.map(m=>({role:m.role,characters:JSON.stringify(m.content).length,content_sha256:hash(JSON.stringify(m.content))})),sse_response_sha256:sse?hash(sse):undefined,sse_reasoning_characters:chunks?.reduce((s,c)=>s+(c.choices?.[0]?.delta?.reasoning_content?.length||0),0),sse_usage:chunks?.findLast(c=>c.usage)?.usage};
  });
  trials.push({name:summary.name,mode:summary.mode,profile:summary.profile,runner_summary:summary,sessions,turns,event_counts:events,session_message_event_counts:projectedEvents,requests:requestSummaries});
}
const evidence={date:'2026-10-07',opencode_versions:[...new Set(trials.flatMap(t=>t.sessions||[]).map(s=>s.version))],database:'~/.local/share/opencode/opencode.db',read_mode:'sqlite3 -readonly; only created diagnostic sessions and descendants',schema:'message.data and part.data JSON plus session aggregates and event counts',trials};
writeFileSync(root+'/evidence.json',JSON.stringify(sanitize(evidence),null,2)+'\n');
for(const trial of trials){console.log(trial.name,trial.turns?.map(t=>({finish:t.final_finish,final:t.final,errors:t.tool_error_count,maximum_context:t.maximum_context_tokens})));}
