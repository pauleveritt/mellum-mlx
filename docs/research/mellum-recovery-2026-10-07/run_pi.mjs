import { randomUUID } from 'node:crypto';
import { copyFileSync, cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

// Diagnostic runner: every invocation creates a new agent directory and sandbox.
const bundle = dirname(fileURLToPath(import.meta.url));
const mode = process.argv[2] || 'retrieval';
if (!['retrieval', 'coding', 'conversation'].includes(mode)) {
  throw new Error('Usage: node run_pi.mjs [retrieval|coding|conversation]');
}
const runDir = mkdtempSync(join(tmpdir(), 'mellum-recovery-'));
const agentDir = join(runDir, 'pi-agent');
const cwd = join(runDir, 'project');
mkdirSync(agentDir);
mkdirSync(cwd);
const modelId = process.env.MELLUM_MODEL_ID || 'Mellum2.1-12B-A2.5B-Thinking-6bit';
const temperature = Number(process.env.MELLUM_TEMPERATURE || '0');
const seed = Number(process.env.MELLUM_SEED || '42');
const thinking = process.env.MELLUM_THINKING || 'high';
const model = {
  id: modelId, name: 'Mellum diagnostic', reasoning: true, input: ['text'],
  contextWindow: 56000, maxTokens: 4096,
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  compat: {
    supportsDeveloperRole: false, supportsReasoningEffort: false,
    maxTokensField: 'max_tokens', thinkingFormat: 'qwen-chat-template',
  },
  samplingParams: {
    temperature, top_p: temperature ? 0.95 : 1,
    top_k: temperature ? 20 : 0, min_p: 0, seed,
  },
};
writeFileSync(join(agentDir, 'models.json'), JSON.stringify({ providers: {
  'mellum-diagnostic': {
    baseUrl: process.env.MELLUM_BASE_URL || 'http://127.0.0.1:8001/v1',
    api: 'openai-completions', apiKey: 'local-diagnostic', models: [model],
  },
} }, null, 2));
writeFileSync(join(agentDir, 'settings.json'), JSON.stringify({
  defaultProvider: 'mellum-diagnostic', defaultModel: modelId,
  defaultThinkingLevel: thinking, compaction: { enabled: false }, quietStartup: true,
}, null, 2));

let tools;
let prompts;
let expected;
if (mode === 'retrieval') {
  const fixtureSeed = Number(process.env.MELLUM_FIXTURE_SEED || '101');
  const golden = JSON.parse(readFileSync(join(bundle, 'pi-goldens.json'), 'utf8'))
    .find(item => item.seed === fixtureSeed);
  if (!golden) throw new Error('Fixture seed must be 101, 202, or 303');
  cpSync(join(bundle, 'fixtures', `retrieval-${fixtureSeed}`), cwd, { recursive: true });
  const source = join(cwd, 'source.py');
  tools = 'grep';
  prompts = [`Use grep to search ${source} for the literal terms START_TOKEN, MIDDLE_TOKEN, and END_TOKEN separately. Retrieve only assignment lines from that exact file; ignore obsolete.py. After the tool results, return only the three values, separated by single spaces, in START_TOKEN, MIDDLE_TOKEN, END_TOKEN order. Do not read the entire source file.`];
  expected = golden.expected_final;
} else if (mode === 'coding') {
  cpSync(join(bundle, 'fixtures', 'coding'), cwd, { recursive: true });
  tools = 'read,edit,bash';
  prompts = ["Fix totalCents(items) in calculator.js so it correctly totals each item's unit price in cents multiplied by its quantity. Keep the exported API and the tests unchanged. Read the relevant files, make the smallest fix, and run node --test calculator.test.js. Explain the result in one sentence. This is a bounded bug fix; no brainstorming or delegation is needed."];
} else {
  copyFileSync(join(bundle, 'fixtures', 'README.md'), join(cwd, 'README.md'));
  tools = 'read,grep,find,ls';
  prompts = ['Hello', 'What is this project about? Read README.md and answer directly in no more than three sentences.', 'Why did you use brainstorming for that informational question? Explain your actual actions directly; do not invoke tools or start another workflow.'];
}
const sessionId = randomUUID();
const summaries = [];
for (const [index, prompt] of prompts.entries()) {
  const stem = join(runDir, `turn-${index + 1}`);
  const args = ['--print', '--mode', 'json', '--no-extensions', '--extension', join(bundle, 'record-pi.js'),
    '--no-skills', '--no-prompt-templates', '--no-themes', '--no-context-files',
    '--provider', 'mellum-diagnostic', '--model', modelId, '--thinking', thinking, '--tools', tools];
  args.push(...(mode === 'conversation' ? ['--session-id', sessionId] : ['--no-session']));
  args.push(prompt);
  const result = spawnSync('pi', args, {
    cwd, encoding: 'utf8', timeout: 180000, maxBuffer: 32 * 1024 * 1024,
    env: { ...process.env, PI_CODING_AGENT_DIR: agentDir, PI_OFFLINE: '1',
      MELLUM_MAX_REQUESTS: '12', MELLUM_TRACE_FILE: `${stem}.trace.jsonl` },
  });
  writeFileSync(`${stem}.events.jsonl`, result.stdout || '');
  writeFileSync(`${stem}.stderr.log`, result.stderr || '');
  const rows = (result.stdout || '').split('\n').filter(Boolean).map(line => JSON.parse(line));
  const messages = rows.filter(row => row.type === 'message_end').map(row => row.message);
  const assistants = messages.filter(message => message.role === 'assistant');
  const last = assistants.at(-1);
  const text = (last?.content || []).filter(block => block.type === 'text').map(block => block.text).join('').trim();
  const calls = assistants.flatMap(message => message.content.filter(block => block.type === 'toolCall'));
  summaries.push({ turn: index + 1, processExitCode: result.status, error: result.error?.message,
    stopReason: last?.stopReason, final: text, calls: calls.map(call => ({ name: call.name, arguments: call.arguments })),
    toolErrors: messages.filter(message => message.role === 'toolResult' && message.isError).length,
    maximumInputTokens: Math.max(0, ...assistants.map(message => (message.usage?.input || 0) + (message.usage?.cacheRead || 0))),
    exactRetrievalPassed: expected === undefined ? undefined : text === expected,
  });
}
let codingVerification;
if (mode === 'coding') {
  const result = spawnSync('node', ['--test', 'calculator.test.js'], { cwd, encoding: 'utf8' });
  writeFileSync(join(runDir, 'independent-tests.log'), result.stdout + result.stderr);
  codingVerification = { exitCode: result.status,
    testsUnchanged: readFileSync(join(cwd, 'calculator.test.js'), 'utf8') === readFileSync(join(bundle, 'fixtures', 'coding', 'calculator.test.js'), 'utf8') };
}
const summary = { mode, modelId, thinking, temperature, seed, runDir, turns: summaries, codingVerification };
writeFileSync(join(runDir, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
if (summaries.some(turn => turn.processExitCode !== 0 || turn.error || turn.stopReason !== 'stop' || turn.toolErrors || turn.exactRetrievalPassed === false)
  || codingVerification?.exitCode || codingVerification?.testsUnchanged === false) process.exitCode = 1;
