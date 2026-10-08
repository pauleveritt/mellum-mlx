import { appendFileSync } from 'node:fs';
export default function(pi) {
  let requests = 0;
  const record = value => appendFileSync(process.env.MELLUM_TRACE_FILE, JSON.stringify(value) + '\n');
  pi.on('before_provider_request', (event, ctx) => {
    requests += 1;
    record({type: 'provider_request', request: requests, payload: event.payload});
  });
  pi.on('tool_call', event => { record({type:'tool_call',toolName:event.toolName,input:event.input}); });
  pi.on('tool_result', event => { record({type:'tool_result',toolName:event.toolName,isError:event.isError,content:event.content}); });
}
