# Mellum Worker Distribution Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `github.com/pauleveritt/mellum-worker`, a Git-installable package that gives OpenCode and Pi users the measured "Mellum 2.1 as a bounded coding worker" recipe plus a guided setup skill.

**Architecture:** One repo, one `package.json` read two ways. OpenCode loads `opencode/plugin.js` (a config hook that only registers the skills directory). Pi loads `extensions/mellum-mode.ts` and the same `skills/` directory. Nothing is registered into the user's providers, agents, or defaults at load time; the `mellum-setup` skill writes those into user-scope files from templates in the repo. Prompt v5 lives in one file and a build script embeds it into both agent templates.

**Tech Stack:** Plain ES modules and TypeScript (type-stripped by Node, no transpiler), `node --test`, Pi 1.0.x extension API, OpenCode 1.18.x V1 plugin API, pi-subagents agent files, oMLX 0.6.x, Hugging Face CLI `hf`.

**Spec:** `docs/superpowers/specs/2026-10-09-mellum-worker-distribution-design.md` (in `mellum-mlx`)

## Global Constraints

- Source repo for copied files: `/Users/pauleveritt/projects/pauleveritt/mellum-mlx`. New repo lives at `/Users/pauleveritt/projects/pauleveritt/mellum-worker`.
- Node 24 or newer (TypeScript imports are type-stripped natively; the user has v25.8.1). No `dependencies`, no `devDependencies`, no build step for tests.
- Pi `extensions` in the manifest lists `./extensions/mellum-mode.ts` only. The guards file is never a package extension.
- Prompt v5 is byte-identical to `prompts/mellum-worker.md` in `mellum-mlx` (643 characters plus the `<!-- mellum-worker prompt v5 -->` first line) and appears in exactly one file in the new repo.
- Model id `Mellum2.1-12B-A2.5B-Thinking-6bit`, provider id `omlx`, base URL `http://127.0.0.1:8001/v1`, Hub repo `pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit`.
- Sampling and limits in every template: temperature 1, top_p 0.95, top_k 20, min_p 0, max output 16,384, context 56,000.
- Worker tools: `read, grep, find, ls, bash, edit, write` (Pi). OpenCode turns off `skill, task, todowrite, todoread, webfetch, websearch`.
- v1 backend is oMLX on Apple Silicon only. Ollama is a documented stub.
- Every test runs with `node --test` from the repo root and must pass before each commit.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. **Pi agent file with a `~` or relative guards path.** pi-subagents resolves `subagentOnlyExtensions` relative to the project, and `~` expansion is undocumented, so a user-scope agent file must hold an absolute path. Test in Task 6: the rendered Pi template contains the placeholder and the substitution helper produces an absolute path with no `~`.
2. **Merging into a `models.json` that already has an `omlx` provider with other models.** The merge must append the Mellum entry and keep the user's other models and providers. Test in Task 7: `mergeJson` on a models.json with an existing omlx provider and a different model yields both models, and running it twice adds nothing.
3. **Activating Mode when the model is not in the registry.** Mode must stay off and its guard hooks must stay inert, otherwise the next turn runs under the parent model with the worker prompt and seven tools. Test in Task 4.
4. **Guard state leaking between spans.** A loop breaker that remembers calls from a previous `/mellum` span would block a legitimate first read in the next span. Test in Task 4: five identical reads, off, on, one more identical read is not blocked.
5. **The OpenCode global config is JSONC with comments.** A JSON round-trip would strip the user's comments. The skill therefore edits that file with the host's edit tool instead of the merge script, and the provider template is a fragment the agent inserts. Test in Task 6: the fragment parses as JSON and contains exactly one model.

---

### Task 1: Commit the pending Mode change in mellum-mlx

The handoff-collapse feature exists only in the working tree of `mellum-mlx`. The new repo copies the committed file, so commit it first.

**Files:**
- Modify (commit only): `/Users/pauleveritt/projects/pauleveritt/mellum-mlx/.pi/mellum/mellum-mode.ts`
- Modify (commit only): `/Users/pauleveritt/projects/pauleveritt/mellum-mlx/.pi/mellum/mellum-mode.test.mjs`

**Interfaces:**
- Produces: a committed `mellum-mode.ts` exporting `MARK_ON`, `MARK_OFF`, `BOOTSTRAP_MARKER`, `WORKER_TOOLS`, `filterForMellum(payload, systemPrompt, opts?)`, `collapseHandoffs(messages)`, and a default `(pi) => void` extension.

- [ ] **Step 1: Run the Node tests in mellum-mlx**

Run: `cd /Users/pauleveritt/projects/pauleveritt/mellum-mlx && node --test .pi/mellum/`
Expected: all tests pass (19 in the two files).

- [ ] **Step 2: Commit only the two Mode files**

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-mlx
git add .pi/mellum/mellum-mode.ts .pi/mellum/mellum-mode.test.mjs
git commit -m "feat(mode): collapse finished spans into one handoff block after /mellum off

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

Leave `README.md`, `main.py`, `pyproject.toml`, `uv.lock` uncommitted; they belong to the user.

---

### Task 2: Repository skeleton and manifest test

**Files:**
- Create: `/Users/pauleveritt/projects/pauleveritt/mellum-worker/package.json`
- Create: `/Users/pauleveritt/projects/pauleveritt/mellum-worker/.gitignore`
- Create: `/Users/pauleveritt/projects/pauleveritt/mellum-worker/README.md` (stub, replaced in Task 9)
- Create: `/Users/pauleveritt/projects/pauleveritt/mellum-worker/tests/manifest.test.mjs`

**Interfaces:**
- Produces: `package.json` with `main: "./opencode/plugin.js"` and `pi.extensions: ["./extensions/mellum-mode.ts"]`, `pi.skills: ["./skills"]`. Later tasks create those paths; the manifest test fails until they exist, which is intended and noted per task.

- [ ] **Step 1: Create the directory and git repo**

```bash
mkdir -p /Users/pauleveritt/projects/pauleveritt/mellum-worker
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
git init -b main
```

- [ ] **Step 2: Write package.json**

```json
{
  "name": "mellum-worker",
  "version": "0.1.0",
  "description": "Mellum 2.1 as a bounded coding worker for OpenCode and Pi, with a guided setup skill",
  "type": "module",
  "main": "./opencode/plugin.js",
  "license": "MIT",
  "repository": "github:pauleveritt/mellum-worker",
  "keywords": ["pi-package", "opencode-plugin", "mellum", "local-llm"],
  "scripts": {
    "test": "node --test 'tests/*.test.mjs'",
    "build": "node build.mjs"
  },
  "pi": {
    "extensions": ["./extensions/mellum-mode.ts"],
    "skills": ["./skills"]
  }
}
```

- [ ] **Step 3: Write .gitignore and a README stub**

`.gitignore`:
```
node_modules/
.DS_Store
```

`README.md`:
```markdown
# mellum-worker

Mellum 2.1 as a bounded coding worker for OpenCode and Pi. Under construction; see docs/ when it lands.
```

- [ ] **Step 4: Write the failing manifest test**

`tests/manifest.test.mjs`:
```js
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { resolve } from "node:path";
import test from "node:test";

const ROOT = resolve(import.meta.dirname, "..");
const pkg = JSON.parse(readFileSync(resolve(ROOT, "package.json"), "utf8"));

test("main points at an existing file", () => {
	assert.ok(existsSync(resolve(ROOT, pkg.main)), `${pkg.main} missing`);
});

test("every pi extension and skills path exists", () => {
	for (const p of [...pkg.pi.extensions, ...pkg.pi.skills]) {
		assert.ok(existsSync(resolve(ROOT, p)), `${p} missing`);
	}
});

test("pi extensions list is explicit and never includes the guards file", () => {
	assert.deepEqual(pkg.pi.extensions, ["./extensions/mellum-mode.ts"]);
});

test("package version matches the newest git tag when one exists", () => {
	let tag = "";
	try {
		tag = execSync("git describe --tags --abbrev=0", { cwd: ROOT, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
	} catch {
		return; // no tags yet
	}
	assert.equal(tag, `v${pkg.version}`);
});
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd /Users/pauleveritt/projects/pauleveritt/mellum-worker && node --test tests/`
Expected: FAIL on "main points at an existing file" and "every pi extension and skills path exists" (paths do not exist yet). The other two pass.

- [ ] **Step 6: Commit the skeleton**

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
git add package.json .gitignore README.md tests/manifest.test.mjs
git commit -m "chore: repository skeleton and manifest test

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Prompt and guards, moved with their tests

**Files:**
- Create: `prompts/mellum-worker.md` (copy)
- Create: `extensions/mellum-guards.ts` (copy, then refactor the default export)
- Create: `tests/mellum-guards.test.mjs` (copy, path fixed, one test added)

**Interfaces:**
- Produces from `extensions/mellum-guards.ts`: everything the file exports today plus
  `createGuardSet(enabled?: typeof ENABLED): { toolCall(event: {toolName: string; input: unknown}): Decision; turnEnd(event: {message?: MessageLike}): void; beforeSettle(): Continuation | undefined }`.
  Task 4 wires this into Mode.

- [ ] **Step 1: Copy the prompt and guards**

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
mkdir -p prompts extensions tests
SRC=/Users/pauleveritt/projects/pauleveritt/mellum-mlx
cp "$SRC/prompts/mellum-worker.md" prompts/mellum-worker.md
cp "$SRC/.pi/mellum/mellum-guards.ts" extensions/mellum-guards.ts
cp "$SRC/.pi/mellum/mellum-guards.test.mjs" tests/mellum-guards.test.mjs
sed -i '' 's#"./mellum-guards.ts"#"../extensions/mellum-guards.ts"#g' tests/mellum-guards.test.mjs
```

- [ ] **Step 2: Run the copied tests to confirm they pass unchanged**

Run: `node --test tests/mellum-guards.test.mjs`
Expected: 10 pass.

- [ ] **Step 3: Write the failing test for createGuardSet**

Append to `tests/mellum-guards.test.mjs`:
```js
test("createGuardSet bundles tool_call, turn_end and settle decisions with fresh state", async () => {
	const { createGuardSet } = await import("../extensions/mellum-guards.ts");
	const set = createGuardSet({ loopBreaker: true, emptyFinalNudge: 1 });
	const read = { toolName: "read", input: { path: "x" } };
	for (let i = 0; i < 5; i++) assert.equal(set.toolCall(read), undefined);
	assert.ok(set.toolCall(read).block, "sixth identical call is blocked");
	set.turnEnd({ message: { role: "assistant", content: [{ type: "thinking", thinking: "." }] } });
	assert.ok(set.beforeSettle()?.continue, "empty final turn is nudged");
	assert.equal(set.beforeSettle(), undefined, "nudge is consumed");
	const fresh = createGuardSet({ loopBreaker: true });
	assert.equal(fresh.toolCall(read), undefined, "a new set has no memory of the old one");
});
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `node --test tests/mellum-guards.test.mjs`
Expected: FAIL, `createGuardSet is not a function`.

- [ ] **Step 5: Add createGuardSet and make the default export use it**

Replace the `export default function (...)` block at the bottom of `extensions/mellum-guards.ts` with:
```ts
export interface GuardSet {
	toolCall(event: { toolName: string; input: unknown }): Decision;
	turnEnd(event: { message?: MessageLike }): void;
	beforeSettle(): Continuation | undefined;
}

/** One run's worth of guard state. Mode creates a fresh set per span; the child extension creates one per session. */
export function createGuardSet(enabled: typeof ENABLED = resolveEnabled(ENABLED, process.env.MELLUM_GUARDS)): GuardSet {
	const guards = activeGuards(enabled);
	const nudge = enabled.emptyFinalNudge ? createEmptyFinalNudge(enabled.emptyFinalNudge) : undefined;
	let lastAssistant: MessageLike | undefined;
	return {
		toolCall(event) {
			for (const guard of guards) {
				const decision = guard({ toolName: event.toolName, input: event.input });
				if (decision?.block) return decision;
			}
			return undefined;
		},
		turnEnd(event) {
			if (event?.message?.role === "assistant") lastAssistant = event.message;
		},
		beforeSettle() {
			// Pi reports canContinue=false on the final turn, which is exactly where an
			// empty final lands; agent_before_settle still honours continue:true there
			// (probed 2026-10-08 in print mode).
			if (!nudge || !lastAssistant) return undefined;
			const decision = nudge(lastAssistant);
			if (decision) lastAssistant = undefined;
			return decision;
		},
	};
}

export default function (pi: { on: (event: string, handler: (event: any) => unknown) => void }) {
	const set = createGuardSet();
	pi.on("tool_call", (event) => set.toolCall(event));
	pi.on("turn_end", (event) => {
		set.turnEnd(event);
		return undefined;
	});
	pi.on("agent_before_settle", () => set.beforeSettle());
}
```

Also update the file's header comment: replace the sentence "adapted to Pi's `tool_call` hook at the bottom of this file" with "adapted to Pi's hooks at the bottom of this file; Mellum Mode reuses `createGuardSet` while it is on". Replace the `../local-ai-pi/extensions/guards` reference with "the mellum-mlx research repo".

- [ ] **Step 6: Run the guards tests**

Run: `node --test tests/mellum-guards.test.mjs`
Expected: 11 pass (the adapter test still passes because the default export's behaviour is unchanged).

- [ ] **Step 7: Commit**

```bash
git add prompts extensions/mellum-guards.ts tests/mellum-guards.test.mjs
git commit -m "feat: prompt v5 and child guards with a reusable guard set

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Mellum Mode as a package extension that owns its guards

**Files:**
- Create: `extensions/mellum-mode.ts` (copy from the commit in Task 1, then modify)
- Create: `tests/mellum-mode.test.mjs` (copy, path fixed)
- Create: `tests/mellum-mode-hooks.test.mjs` (new)

**Interfaces:**
- Consumes: `createGuardSet` from Task 3.
- Produces: `extensions/mellum-mode.ts` default export `(pi) => void` registering the `mellum` command and the hooks `session_start`, `agent_settled`, `session_before_compact`, `context`, `before_provider_request`, `tool_call`, `turn_end`, `agent_before_settle`.

- [ ] **Step 1: Copy Mode and its tests, fix paths**

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
SRC=/Users/pauleveritt/projects/pauleveritt/mellum-mlx
cp "$SRC/.pi/mellum/mellum-mode.ts" extensions/mellum-mode.ts
cp "$SRC/.pi/mellum/mellum-mode.test.mjs" tests/mellum-mode.test.mjs
sed -i '' 's#"./mellum-mode.ts"#"../extensions/mellum-mode.ts"#g' tests/mellum-mode.test.mjs
```

- [ ] **Step 2: Fix the prompt path and the header comment**

In `extensions/mellum-mode.ts`, in `loadPrompt()`, change
```ts
	const file = process.env.MELLUM_MODE_PROMPT || resolve(here, "..", "..", "prompts", "mellum-worker.md");
```
to
```ts
	const file = process.env.MELLUM_MODE_PROMPT || resolve(here, "..", "prompts", "mellum-worker.md");
```

In the header comment replace the last paragraph line
`Load alongside mellum-guards.ts; this file does not auto-load (it is not in .pi/extensions/).`
with
`Installed as a Pi package extension it loads in every parent session and stays dormant until /mellum. While on, it runs the child guards (createGuardSet) itself, so no second extension is needed.`

- [ ] **Step 3: Run the copied tests**

Run: `node --test tests/mellum-mode.test.mjs`
Expected: 9 pass. (Also `node --test tests/manifest.test.mjs` now passes "every pi extension ... exists"; `main` still missing until Task 5.)

- [ ] **Step 4: Write the failing hook tests**

`tests/mellum-mode-hooks.test.mjs`:
```js
import assert from "node:assert/strict";
import test from "node:test";
import install from "../extensions/mellum-mode.ts";

const MODEL = { provider: "omlx", id: "Mellum2.1-12B-A2.5B-Thinking-6bit" };

function fakePi({ registryHasModel = true } = {}) {
	const handlers = {};
	let commands = {};
	const pi = {
		on: (name, fn) => { handlers[name] = fn; },
		registerCommand: (name, def) => { commands[name] = def; },
		getActiveTools: () => ["read", "subagent"],
		setActiveTools: () => {},
		setModel: async () => true,
		sendMessage: () => {},
		sendUserMessage: () => {},
	};
	const ctx = {
		model: { provider: "anthropic", id: "parent" },
		modelRegistry: { find: (p, id) => (registryHasModel && p === MODEL.provider && id === MODEL.id ? MODEL : undefined) },
		ui: { notify: () => {} },
	};
	install(pi);
	return { handlers, ctx, mellum: (args) => commands.mellum.handler(args, ctx) };
}

const read = { toolName: "read", input: { path: "x" } };
const emptyTurn = { message: { role: "assistant", content: [{ type: "thinking", thinking: "." }] } };

test("guard hooks are inert while mode is off", () => {
	const { handlers } = fakePi();
	for (let i = 0; i < 8; i++) assert.equal(handlers.tool_call(read), undefined);
	handlers.turn_end(emptyTurn);
	assert.equal(handlers.agent_before_settle(), undefined);
});

test("guard hooks are live while mode is on", async () => {
	const { handlers, mellum } = fakePi();
	await mellum("on");
	for (let i = 0; i < 5; i++) assert.equal(handlers.tool_call(read), undefined);
	assert.ok(handlers.tool_call(read)?.block);
	handlers.turn_end(emptyTurn);
	assert.ok(handlers.agent_before_settle()?.continue);
});

test("guard state is fresh for each span", async () => {
	const { handlers, mellum } = fakePi();
	await mellum("on");
	for (let i = 0; i < 5; i++) handlers.tool_call(read);
	await mellum("off");
	await mellum("on");
	assert.equal(handlers.tool_call(read), undefined, "the new span does not remember the old reads");
});

test("activating with the model missing from the registry leaves mode and guards off", async () => {
	const { handlers, mellum } = fakePi({ registryHasModel: false });
	await mellum("on");
	for (let i = 0; i < 8; i++) assert.equal(handlers.tool_call(read), undefined);
	assert.equal(handlers.before_provider_request({ payload: { messages: [] } }), undefined);
});
```

- [ ] **Step 5: Run the hook tests to verify they fail**

Run: `node --test tests/mellum-mode-hooks.test.mjs`
Expected: "guard hooks are inert while mode is off" FAILS with `handlers.tool_call is not a function`; the others fail the same way.

- [ ] **Step 6: Wire the guard set into Mode**

In `extensions/mellum-mode.ts`:

Add the import after the existing imports:
```ts
import { createGuardSet, type GuardSet } from "./mellum-guards.ts";
```

Inside `export default function (pi: any) {`, after `let warnedMissing = false;` add:
```ts
	let guards: GuardSet | undefined;
```

In `activate`, right after `active = true;` add:
```ts
		guards = createGuardSet();
```

In `deactivate`, right after `active = false;` add:
```ts
		guards = undefined;
```

After the `before_provider_request` handler at the end of the default export, add:
```ts
	// The child's guards, run in-session while the mode is on. A fresh set per span.
	pi.on("tool_call", (event: any) => (active && guards ? guards.toolCall(event) : undefined));
	pi.on("turn_end", (event: any) => {
		if (active && guards) guards.turnEnd(event);
		return undefined;
	});
	pi.on("agent_before_settle", () => (active && guards ? guards.beforeSettle() : undefined));
```

- [ ] **Step 7: Run all Mode tests**

Run: `node --test tests/mellum-mode.test.mjs tests/mellum-mode-hooks.test.mjs`
Expected: 13 pass.

- [ ] **Step 8: Commit**

```bash
git add extensions/mellum-mode.ts tests/mellum-mode.test.mjs tests/mellum-mode-hooks.test.mjs
git commit -m "feat: Mellum Mode as a package extension that runs its own guards while on

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: OpenCode plugin

**Files:**
- Create: `opencode/plugin.js`
- Create: `tests/opencode-plugin.test.mjs`

**Interfaces:**
- Produces: named export `MellumWorkerPlugin: async (ctx) => ({ config: async (cfg) => void })` and default export `{ id: "mellum-worker", server: MellumWorkerPlugin }`. The hook appends the absolute `skills/` directory to `cfg.skills.paths` exactly once.

- [ ] **Step 1: Write the failing test**

`tests/opencode-plugin.test.mjs`:
```js
import assert from "node:assert/strict";
import { resolve } from "node:path";
import test from "node:test";
import plugin, { MellumWorkerPlugin } from "../opencode/plugin.js";

const SKILLS = resolve(import.meta.dirname, "..", "skills");

test("config hook adds the skills directory once, keeping existing paths", async () => {
	const hooks = await MellumWorkerPlugin({ directory: "/tmp/project" });
	const cfg = { skills: { paths: ["~/mine"] } };
	await hooks.config(cfg);
	await hooks.config(cfg);
	assert.deepEqual(cfg.skills.paths, ["~/mine", SKILLS]);
});

test("config hook creates skills.paths when absent", async () => {
	const hooks = await MellumWorkerPlugin({});
	const cfg = {};
	await hooks.config(cfg);
	assert.deepEqual(cfg.skills.paths, [SKILLS]);
});

test("config hook leaves a V2 flat skills array alone", async () => {
	const hooks = await MellumWorkerPlugin({});
	const cfg = { skills: ["x"] };
	await hooks.config(cfg);
	assert.deepEqual(cfg.skills, ["x"]);
});

test("default export names the plugin and points at the same function", () => {
	assert.equal(plugin.id, "mellum-worker");
	assert.equal(plugin.server, MellumWorkerPlugin);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/opencode-plugin.test.mjs`
Expected: FAIL, cannot find module `../opencode/plugin.js`.

- [ ] **Step 3: Write the plugin**

`opencode/plugin.js`:
```js
/**
 * mellum-worker plugin for OpenCode (V1 API, 1.18.x).
 *
 * Its only job is to make the mellum-setup skill discoverable: it appends this
 * package's skills/ directory to the merged config's skills.paths. It registers
 * no provider, agent, or model; the skill writes those into the user's files.
 *
 * No dependencies, so a git install needs nothing beyond this file.
 */
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SKILLS_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..", "skills");

export const MellumWorkerPlugin = async (_ctx) => ({
	config: async (cfg) => {
		if (Array.isArray(cfg.skills)) return; // V2 shape; not handled by this plugin
		cfg.skills = cfg.skills || {};
		cfg.skills.paths = cfg.skills.paths || [];
		if (!cfg.skills.paths.includes(SKILLS_DIR)) cfg.skills.paths.push(SKILLS_DIR);
	},
});

export default { id: "mellum-worker", server: MellumWorkerPlugin };
```

- [ ] **Step 4: Run the plugin test and the manifest test**

Run: `node --test tests/opencode-plugin.test.mjs tests/manifest.test.mjs`
Expected: all pass. The manifest "main" test now passes; "skills path exists" still fails until Task 8 creates `skills/`. That is expected for now.

- [ ] **Step 5: Commit**

```bash
git add opencode/plugin.js tests/opencode-plugin.test.mjs
git commit -m "feat: OpenCode plugin that registers the skills directory

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Templates and the build script

**Files:**
- Create: `build.mjs`
- Create: `templates/pi/mellum-worker.agent.md` (generated)
- Create: `templates/opencode/mellum-worker.md` (generated)
- Create: `templates/pi/models.omlx.json`
- Create: `templates/opencode/provider.omlx.json`
- Create: `tests/templates.test.mjs`

**Interfaces:**
- Produces: `build.mjs` exports `render(): Record<string, string>` mapping repo-relative paths to file contents, `PLACEHOLDER = "{{MELLUM_WORKER_ROOT}}"`, and `substituteRoot(text, root)`; running the file writes the rendered files.

- [ ] **Step 1: Write the failing template tests**

`tests/templates.test.mjs`:
```js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { PLACEHOLDER, render, substituteRoot } from "../build.mjs";

const ROOT = resolve(import.meta.dirname, "..");
const read = (p) => readFileSync(resolve(ROOT, p), "utf8");
const prompt = read("prompts/mellum-worker.md").trim();

test("rendered templates on disk match the build output (no drift)", () => {
	for (const [path, content] of Object.entries(render())) {
		assert.equal(read(path), content, `${path} is stale; run: node build.mjs`);
	}
});

test("both agent templates embed prompt v5 verbatim as their body", () => {
	for (const path of ["templates/pi/mellum-worker.agent.md", "templates/opencode/mellum-worker.md"]) {
		const body = read(path).split("---", 3)[2].trim();
		assert.equal(body, prompt, `${path} body differs from prompts/mellum-worker.md`);
	}
});

test("the Pi agent template carries the root placeholder on the guards line", () => {
	const text = read("templates/pi/mellum-worker.agent.md");
	assert.match(text, new RegExp(`^subagentOnlyExtensions: ${PLACEHOLDER.replace(/[{}]/g, "\\$&")}/extensions/mellum-guards.ts$`, "m"));
});

test("substituteRoot yields an absolute path with no tilde", () => {
	const out = substituteRoot(`x: ${PLACEHOLDER}/extensions/mellum-guards.ts`, "/Users/me/.pi/agent/git/github.com/pauleveritt/mellum-worker");
	assert.equal(out, "x: /Users/me/.pi/agent/git/github.com/pauleveritt/mellum-worker/extensions/mellum-guards.ts");
	assert.throws(() => substituteRoot("y", "~/.pi/agent/git/x"), /absolute/);
	assert.throws(() => substituteRoot("y", "relative/path"), /absolute/);
});

test("the OpenCode provider fragment is JSON with exactly the Mellum model", () => {
	const frag = JSON.parse(read("templates/opencode/provider.omlx.json"));
	assert.deepEqual(Object.keys(frag.provider.omlx.models), ["Mellum2.1-12B-A2.5B-Thinking-6bit"]);
	assert.equal(frag.provider.omlx.models["Mellum2.1-12B-A2.5B-Thinking-6bit"].limit.output, 16384);
});

test("the Pi models fragment is JSON with the validated compat fields", () => {
	const frag = JSON.parse(read("templates/pi/models.omlx.json"));
	const model = frag.providers.omlx.models[0];
	assert.equal(model.id, "Mellum2.1-12B-A2.5B-Thinking-6bit");
	assert.equal(model.compat.supportsDeveloperRole, false);
	assert.equal(model.compat.thinkingFormat, "qwen-chat-template");
	assert.equal(model.maxTokens, 16384);
	assert.equal(model.contextWindow, 56000);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/templates.test.mjs`
Expected: FAIL, cannot find module `../build.mjs`.

- [ ] **Step 3: Write build.mjs**

```js
/**
 * Renders the two agent templates from the single prompt file.
 * Run `node build.mjs` after editing prompts/mellum-worker.md.
 * tests/templates.test.mjs fails when the files on disk are stale.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
export const PLACEHOLDER = "{{MELLUM_WORKER_ROOT}}";

const PI_FRONTMATTER = `---
name: mellum-worker
description: Bounded coding task on the local Mellum model
model: omlx/Mellum2.1-12B-A2.5B-Thinking-6bit
advertise: true
systemPromptMode: replace
inheritProjectContext: false
inheritGlobalContext: false
inheritSkills: false
extensions:
subagentOnlyExtensions: ${PLACEHOLDER}/extensions/mellum-guards.ts
tools: read, grep, find, ls, bash, edit, write
excludeTools: contact_supervisor
acceptance:
  level: none
  reason: the parent verifies the child by running the tests itself
---
`;

// steps: the Pi ladder averaged 11 Mellum requests per task with no cap;
// 40 leaves room for the long multi-file rungs without letting a loop run all day.
const OPENCODE_FRONTMATTER = `---
description: Bounded coding task on the local Mellum model. Give it exact file paths, literal search terms, a precise change, and the test command. Not for exploration or design.
mode: subagent
model: omlx/Mellum2.1-12B-A2.5B-Thinking-6bit
temperature: 1
top_p: 0.95
steps: 40
options:
  chat_template_kwargs:
    enable_thinking: true
    preserve_thinking: true
  top_k: 20
  min_p: 0
tools:
  skill: false
  task: false
  todowrite: false
  todoread: false
  webfetch: false
  websearch: false
permission:
  read: allow
  grep: allow
  glob: allow
  list: allow
  edit: allow
  bash: allow
---
`;

export function render() {
	const prompt = readFileSync(resolve(ROOT, "prompts", "mellum-worker.md"), "utf8").trim() + "\n";
	return {
		"templates/pi/mellum-worker.agent.md": PI_FRONTMATTER + prompt,
		"templates/opencode/mellum-worker.md": OPENCODE_FRONTMATTER + prompt,
	};
}

/** Replace the root placeholder with an absolute install path. Used by the setup skill's helper. */
export function substituteRoot(text, root) {
	if (!isAbsolute(root) || root.startsWith("~")) throw new Error(`root must be an absolute path, got ${root}`);
	return text.replaceAll(PLACEHOLDER, root.replace(/\/+$/, ""));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	for (const [path, content] of Object.entries(render())) {
		const out = resolve(ROOT, path);
		mkdirSync(dirname(out), { recursive: true });
		writeFileSync(out, content);
		console.log(`wrote ${path}`);
	}
}
```

- [ ] **Step 4: Write the two JSON fragments**

`templates/pi/models.omlx.json`:
```json
{
  "providers": {
    "omlx": {
      "name": "oMLX",
      "baseUrl": "http://127.0.0.1:8001/v1",
      "api": "openai-completions",
      "apiKey": "not-needed",
      "models": [
        {
          "id": "Mellum2.1-12B-A2.5B-Thinking-6bit",
          "name": "Mellum 2.1 12B-A2.5B Thinking (MLX 6-bit)",
          "reasoning": true,
          "input": ["text"],
          "contextWindow": 56000,
          "maxTokens": 16384,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "samplingParams": {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0,
            "presence_penalty": 0,
            "repetition_penalty": 1
          },
          "compat": {
            "supportsDeveloperRole": false,
            "supportsReasoningEffort": false,
            "maxTokensField": "max_tokens",
            "thinkingFormat": "qwen-chat-template"
          }
        }
      ]
    }
  }
}
```

`templates/opencode/provider.omlx.json`:
```json
{
  "provider": {
    "omlx": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "oMLX",
      "options": {
        "baseURL": "http://127.0.0.1:8001/v1",
        "apiKey": "not-needed"
      },
      "models": {
        "Mellum2.1-12B-A2.5B-Thinking-6bit": {
          "name": "Mellum 2.1 12B-A2.5B Thinking (MLX 6-bit)",
          "reasoning": true,
          "tool_call": true,
          "temperature": true,
          "interleaved": { "field": "reasoning_content" },
          "modalities": { "input": ["text"], "output": ["text"] },
          "cost": { "input": 0, "output": 0, "cache_read": 0, "cache_write": 0 },
          "limit": { "context": 56000, "output": 16384 }
        }
      }
    }
  }
}
```

- [ ] **Step 5: Generate the agent templates and run the tests**

Run: `node build.mjs && node --test tests/templates.test.mjs`
Expected: two "wrote" lines, then 6 pass.

- [ ] **Step 6: Commit**

```bash
git add build.mjs templates tests/templates.test.mjs
git commit -m "feat: agent and provider templates rendered from prompt v5

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: JSON merge helper for the skill

The skill merges `templates/pi/models.omlx.json` into `~/.pi/agent/models.json`. That file is plain JSON, so a script can do it safely and idempotently. (The OpenCode config is JSONC and is edited by hand; see Review Focus 5.)

**Files:**
- Create: `scripts/merge-json.mjs`
- Create: `tests/merge-json.test.mjs`

**Interfaces:**
- Produces: `mergeJson(target: object, fragment: object): object` (pure, returns a new object) and a CLI `node scripts/merge-json.mjs <target-file> <fragment-file> [--write]` that prints the merged result (or a "no change" line) and writes only with `--write`, after copying the target to `<target>.bak-mellum-<timestamp>`.
- Merge rules: objects merge recursively; arrays of objects with an `id` merge by `id` (fragment entry replaces the same-id entry, new ids append); other arrays are replaced by the fragment's; scalars are replaced.

- [ ] **Step 1: Write the failing tests**

`tests/merge-json.test.mjs`:
```js
import assert from "node:assert/strict";
import test from "node:test";
import { mergeJson } from "../scripts/merge-json.mjs";

const fragment = { providers: { omlx: { baseUrl: "http://127.0.0.1:8001/v1", models: [{ id: "mellum", maxTokens: 16384 }] } } };

test("adds the provider when the target has none", () => {
	const out = mergeJson({ providers: { other: { baseUrl: "x" } } }, fragment);
	assert.deepEqual(Object.keys(out.providers).sort(), ["omlx", "other"]);
	assert.deepEqual(out.providers.omlx.models, [{ id: "mellum", maxTokens: 16384 }]);
});

test("keeps the user's other models in an existing omlx provider and appends by id", () => {
	const target = { providers: { omlx: { baseUrl: "http://127.0.0.1:8001/v1", models: [{ id: "gemma", maxTokens: 8192 }] } } };
	const out = mergeJson(target, fragment);
	assert.deepEqual(out.providers.omlx.models.map((m) => m.id), ["gemma", "mellum"]);
	assert.deepEqual(target.providers.omlx.models.map((m) => m.id), ["gemma"], "input not mutated");
});

test("is idempotent and refreshes an existing entry with the same id", () => {
	const once = mergeJson({}, fragment);
	const twice = mergeJson(once, fragment);
	assert.deepEqual(twice, once);
	const updated = mergeJson(once, { providers: { omlx: { models: [{ id: "mellum", maxTokens: 4096 }] } } });
	assert.equal(updated.providers.omlx.models.length, 1);
	assert.equal(updated.providers.omlx.models[0].maxTokens, 4096);
});

test("scalar arrays are replaced, not concatenated", () => {
	assert.deepEqual(mergeJson({ a: [1, 2] }, { a: [3] }), { a: [3] });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test tests/merge-json.test.mjs`
Expected: FAIL, cannot find module.

- [ ] **Step 3: Write the merge script**

`scripts/merge-json.mjs`:
```js
/**
 * Deep-merge a JSON fragment into a JSON file, by id for arrays of objects.
 *
 *   node scripts/merge-json.mjs ~/.pi/agent/models.json templates/pi/models.omlx.json          # preview
 *   node scripts/merge-json.mjs ~/.pi/agent/models.json templates/pi/models.omlx.json --write  # apply
 *
 * --write copies the target to <target>.bak-mellum-<timestamp> first.
 * Only for plain JSON files. JSONC (OpenCode's config) loses comments here; edit that by hand.
 */
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const hasId = (arr) => arr.length > 0 && arr.every((x) => isObject(x) && typeof x.id === "string");

export function mergeJson(target, fragment) {
	if (Array.isArray(target) && Array.isArray(fragment) && hasId(target) && hasId(fragment)) {
		const out = target.map((x) => structuredClone(x));
		for (const item of fragment) {
			const i = out.findIndex((x) => x.id === item.id);
			if (i === -1) out.push(structuredClone(item));
			else out[i] = mergeJson(out[i], item);
		}
		return out;
	}
	if (isObject(target) && isObject(fragment)) {
		const out = { ...target };
		for (const [k, v] of Object.entries(fragment)) out[k] = k in target ? mergeJson(target[k], v) : structuredClone(v);
		return out;
	}
	return structuredClone(fragment);
}

function main(argv) {
	const [targetArg, fragmentArg, flag] = argv;
	if (!targetArg || !fragmentArg) {
		console.error("usage: merge-json.mjs <target.json> <fragment.json> [--write]");
		process.exit(2);
	}
	const target = resolve(targetArg.replace(/^~(?=$|\/)/, process.env.HOME ?? "~"));
	const current = existsSync(target) ? JSON.parse(readFileSync(target, "utf8")) : {};
	const fragment = JSON.parse(readFileSync(resolve(fragmentArg), "utf8"));
	const merged = mergeJson(current, fragment);
	const before = JSON.stringify(current, null, 2) + "\n";
	const after = JSON.stringify(merged, null, 2) + "\n";
	if (before === after) {
		console.log(`no change: ${target} already contains the fragment`);
		return;
	}
	if (flag !== "--write") {
		console.log(after);
		console.log(`(preview only; add --write to update ${target})`);
		return;
	}
	if (existsSync(target)) {
		const backup = `${target}.bak-mellum-${new Date().toISOString().replace(/[:.]/g, "")}`;
		copyFileSync(target, backup);
		console.log(`backup: ${backup}`);
	}
	writeFileSync(target, after);
	console.log(`wrote ${target}`);
}

if (process.argv[1] && resolve(process.argv[1]).endsWith("merge-json.mjs")) main(process.argv.slice(2));
```

- [ ] **Step 4: Run the tests**

Run: `node --test tests/merge-json.test.mjs`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/merge-json.mjs tests/merge-json.test.mjs
git commit -m "feat: id-aware JSON merge helper for the setup skill

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: The mellum-setup skill

**Files:**
- Create: `skills/mellum-setup/SKILL.md`
- Create: `skills/mellum-setup/reference/01-preflight.md`
- Create: `skills/mellum-setup/reference/02-weights.md`
- Create: `skills/mellum-setup/reference/03-server.md`
- Create: `skills/mellum-setup/reference/04-provider-pi.md`
- Create: `skills/mellum-setup/reference/04-provider-opencode.md`
- Create: `skills/mellum-setup/reference/05-worker-pi.md`
- Create: `skills/mellum-setup/reference/05-worker-opencode.md`
- Create: `skills/mellum-setup/reference/06-rules.md`
- Create: `skills/mellum-setup/reference/07-smoke.md`
- Create: `skills/mellum-setup/smoke/calculator/{calculator.js,calculator.test.js,package.json}`
- Create: `scripts/render-agent.mjs`
- Create: `tests/skill.test.mjs`

**Interfaces:**
- Consumes: `substituteRoot` and `render` from `build.mjs`; `scripts/merge-json.mjs`.
- Produces: `scripts/render-agent.mjs <pi|opencode> [root]` prints the agent file for that host with the placeholder substituted (`root` required for `pi`; defaults to the directory containing this package).

- [ ] **Step 1: Write the failing skill tests**

`tests/skill.test.mjs`:
```js
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const ROOT = resolve(import.meta.dirname, "..");
const SKILL = resolve(ROOT, "skills", "mellum-setup");

test("SKILL.md has the frontmatter both tools require", () => {
	const text = readFileSync(resolve(SKILL, "SKILL.md"), "utf8");
	const fm = text.split("---")[1];
	assert.match(fm, /^name: mellum-setup$/m);
	const desc = fm.match(/^description: (.+)$/m)?.[1] ?? "";
	assert.ok(desc.length > 40 && desc.length <= 1024, "description length");
});

test("every phase referenced by SKILL.md exists", () => {
	const text = readFileSync(resolve(SKILL, "SKILL.md"), "utf8");
	const refs = [...text.matchAll(/reference\/(\d\d-[a-z-]+\.md)/g)].map((m) => m[1]);
	assert.ok(refs.length >= 9, `expected at least 9 reference links, found ${refs.length}`);
	for (const r of new Set(refs)) assert.ok(existsSync(resolve(SKILL, "reference", r)), `${r} missing`);
});

test("the smoke fixture is the failing calculator and its test command is the one in the recipe", () => {
	const dir = resolve(SKILL, "smoke", "calculator");
	const pkg = JSON.parse(readFileSync(resolve(dir, "package.json"), "utf8"));
	assert.equal(pkg.scripts.test, "node --test calculator.test.js");
	assert.throws(() => execFileSync("node", ["--test", "calculator.test.js"], { cwd: dir, stdio: "pipe" }), "the fixture must fail before the worker fixes it");
});

test("render-agent prints a Pi agent file with an absolute guards path", () => {
	const out = execFileSync("node", [resolve(ROOT, "scripts", "render-agent.mjs"), "pi", "/abs/pkg"], { encoding: "utf8" });
	assert.match(out, /^subagentOnlyExtensions: \/abs\/pkg\/extensions\/mellum-guards\.ts$/m);
	assert.ok(!out.includes("{{"), "no placeholder left");
});

test("render-agent prints the OpenCode agent file unchanged", () => {
	const out = execFileSync("node", [resolve(ROOT, "scripts", "render-agent.mjs"), "opencode"], { encoding: "utf8" });
	assert.equal(out, readFileSync(resolve(ROOT, "templates", "opencode", "mellum-worker.md"), "utf8"));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test tests/skill.test.mjs`
Expected: FAIL on every test (files missing).

- [ ] **Step 3: Copy the smoke fixture**

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
mkdir -p skills/mellum-setup/smoke/calculator skills/mellum-setup/reference scripts
SRC=/Users/pauleveritt/projects/pauleveritt/mellum-mlx/fixtures/calculator
cp "$SRC/calculator.js" "$SRC/calculator.test.js" "$SRC/package.json" skills/mellum-setup/smoke/calculator/
```

- [ ] **Step 4: Write render-agent.mjs**

`scripts/render-agent.mjs`:
```js
/**
 * Print the agent file for one host, ready to save.
 *   node scripts/render-agent.mjs pi /absolute/path/to/mellum-worker   > ~/.pi/agent/agents/mellum-worker.md
 *   node scripts/render-agent.mjs opencode                              > ~/.config/opencode/agents/mellum-worker.md
 * For pi the root defaults to this package's own directory, which is the clone Pi made.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { substituteRoot } from "../build.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const [host, rootArg] = process.argv.slice(2);

if (host === "pi") {
	const text = readFileSync(resolve(ROOT, "templates", "pi", "mellum-worker.agent.md"), "utf8");
	process.stdout.write(substituteRoot(text, rootArg ?? ROOT));
} else if (host === "opencode") {
	process.stdout.write(readFileSync(resolve(ROOT, "templates", "opencode", "mellum-worker.md"), "utf8"));
} else {
	console.error("usage: render-agent.mjs <pi|opencode> [absolute-package-root]");
	process.exit(2);
}
```

- [ ] **Step 5: Write SKILL.md**

`skills/mellum-setup/SKILL.md`:
```markdown
---
name: mellum-setup
description: Set up Mellum 2.1 as a bounded coding worker in OpenCode or Pi. Use when the user asks to install, configure, or verify Mellum Worker or Mellum Mode, or to get the Mellum model running on oMLX. Walks through weights, server, provider, agent, rules, and a smoke test, one checked phase at a time.
---

# Mellum setup

You are installing the Mellum Worker recipe into the user's own configuration.
Work one phase at a time. Each phase has a check; run the check first, and
skip the phase when it already passes. Before writing to any file that
exists, show the user what will change and wait for a yes.

Package root: the directory that contains this skill's parent `skills/`
directory. Find it with:

```bash
PKG="$(cd "$(dirname "$SKILL_PATH")/../.." && pwd)"   # if the host gives you the skill path
```

or locate it: Pi clones to `~/.pi/agent/git/github.com/pauleveritt/mellum-worker`;
OpenCode installs under `~/.cache/opencode/packages/*/node_modules/mellum-worker`.
Every command below is relative to `$PKG`.

## Which host am I in?

- Pi: the `/skill:` command form exists and `~/.pi/agent/settings.json` is present.
- OpenCode: the `skill` tool loaded this file and `~/.config/opencode/` is present.

Record the answer; phases 4 and 5 differ by host.

## Phases

| # | Phase | Check that means "already done" | Reference |
| --- | --- | --- | --- |
| 1 | Preflight | Apple Silicon, oMLX installed, host known | [reference/01-preflight.md](reference/01-preflight.md) |
| 2 | Weights | model folder with two `.safetensors` shards exists | [reference/02-weights.md](reference/02-weights.md) |
| 3 | Server | `GET http://127.0.0.1:8001/v1/models` lists the model | [reference/03-server.md](reference/03-server.md) |
| 4 | Provider | the host's model list shows `omlx/Mellum2.1-12B-A2.5B-Thinking-6bit` | Pi: [reference/04-provider-pi.md](reference/04-provider-pi.md), OpenCode: [reference/04-provider-opencode.md](reference/04-provider-opencode.md) |
| 5 | Worker | `mellum-worker` agent file exists in the host's user agents dir | Pi: [reference/05-worker-pi.md](reference/05-worker-pi.md), OpenCode: [reference/05-worker-opencode.md](reference/05-worker-opencode.md) |
| 6 | Rules | user accepted or declined the AGENTS.md fragment | [reference/06-rules.md](reference/06-rules.md) |
| 7 | Smoke test | the calculator fixture's tests exit 0 after the worker ran | [reference/07-smoke.md](reference/07-smoke.md) |

Read a phase's reference file only when its check fails. When all seven
checks pass, tell the user:

- Pi: "Mellum Worker is available to pi-subagents as `mellum-worker`, and
  `/mellum <task>`, `/mellum on`, `/mellum off` run Mellum Mode in this session."
- OpenCode: "Mellum Worker is the `mellum-worker` subagent. Ask your main
  agent to delegate a bounded task to it."

Do not invent settings. Every number in this skill was measured; if a
reference file does not cover the user's situation, say so and stop.
```

- [ ] **Step 6: Write the reference files**

`reference/01-preflight.md`:
```markdown
# Phase 1: Preflight

Checks, in order. Stop at the first failure and tell the user what v1 needs.

1. `uname -m` prints `arm64` and `uname -s` prints `Darwin`. Anything else:
   v1 supports Apple Silicon with oMLX only. Point the user at
   `docs/backends/ollama.md` for what a port needs, and stop.
2. oMLX is installed: either the menu-bar app is present
   (`ls /Applications | grep -i omlx`) or `command -v omlx` succeeds. If
   neither, tell the user to install oMLX 0.6.4 or newer from its
   release page and come back.
3. `hf --version` succeeds (Hugging Face CLI 1.0 or newer). If not:
   `uv tool install huggingface_hub` or `pip install -U huggingface_hub`.
4. `node --version` is 24 or newer; the setup scripts need it.
5. Free disk: `df -h ~ | tail -1`. The weights are 9.9 GB.

Record the host (Pi or OpenCode) from the SKILL.md rule. Done.
```

`reference/02-weights.md`:
```markdown
# Phase 2: Weights

Target folder (the name oMLX shows as the model id):

```
~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit
```

Check: that folder holds `config.json` and two `model-*.safetensors` shards.

If missing, download the published MLX 6-bit conversion into that exact
folder name:

```bash
hf download pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit \
  --local-dir ~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit
```

About 9.9 GB. Re-run the check. If the user already has the folder under
another name, do not rename it; instead tell them the model id in phases
3 to 5 must match their folder name, and ask whether to proceed with
theirs or download under the recipe's name.
```

`reference/03-server.md`:
```markdown
# Phase 3: Server

Check: `curl -s http://127.0.0.1:8001/v1/models` returns JSON whose `data`
array contains an entry with `"id": "Mellum2.1-12B-A2.5B-Thinking-6bit"`.

If the port does not answer, start oMLX. Either the menu-bar app (add
`~/.cache/huggingface/hub` as a model directory in its settings and set
port 8001, one concurrent request, hot cache off, memory guard 14), or the CLI:

```bash
omlx serve \
  --model-dir "$HOME/.cache/huggingface/hub" \
  --host 127.0.0.1 --port 8001 \
  --max-concurrent-requests 1 --hot-cache-max-size 0 --memory-guard-gb 14
```

`--model-dir` is the parent of the model folder; pointing it at the model
folder itself finds nothing. Run it in the background or another terminal.
Wait for the check to pass.

Per-model settings. These apply to every client of this model, so show
them and ask before changing. Read the current values:

```bash
curl -s http://127.0.0.1:8001/admin/api/models | python3 -c "import json,sys; [print(json.dumps(m['settings'],indent=1)) for m in json.load(sys.stdin)['models'] if m.get('id')=='Mellum2.1-12B-A2.5B-Thinking-6bit']"
```

Wanted (measured in the Pi ladder):

| key | value | why |
| --- | --- | --- |
| `max_context_window` | 56000 | 50k prompt plus generation fits the validated memory budget |
| `max_tokens` | 16384 | a 4,096 cap cut a three-file task off mid-thought; clients send their own cap, this is the ceiling |
| `forced_ct_kwargs` | `["enable_thinking"]` | thinking off failed the ladder; this stops a client switching it off |
| TurboQuant / cache quantization | off | the hybrid cache must stay native |

Apply with the user's yes:

```bash
curl -s -X PUT http://127.0.0.1:8001/admin/api/models/Mellum2.1-12B-A2.5B-Thinking-6bit/settings \
  -H 'content-type: application/json' \
  -d '{"max_context_window":56000,"max_tokens":16384,"forced_ct_kwargs":["enable_thinking"]}'
```

Then read the values back and confirm they took. If the admin API needs
an API key on their server, tell the user to set the same four values in
the admin page at `http://127.0.0.1:8001/admin` instead.
```

`reference/04-provider-pi.md`:
```markdown
# Phase 4 (Pi): Provider

Check: `pi --list-models 2>/dev/null | grep -q 'omlx/Mellum2.1-12B-A2.5B-Thinking-6bit'`
(if that flag is absent in the user's Pi, inspect `~/.pi/agent/models.json`
for an `omlx` provider with a model id `Mellum2.1-12B-A2.5B-Thinking-6bit`).

If missing, preview the merge:

```bash
node "$PKG/scripts/merge-json.mjs" ~/.pi/agent/models.json "$PKG/templates/pi/models.omlx.json"
```

Show the preview. Existing providers and other `omlx` models are kept; a
backup is written next to the file. With the user's yes:

```bash
node "$PKG/scripts/merge-json.mjs" ~/.pi/agent/models.json "$PKG/templates/pi/models.omlx.json" --write
```

If `~/.pi/agent/settings.json` has an `enabledModels` list, the model is
hidden until it is listed. Offer to add `"omlx/Mellum2.1-12B-A2.5B-Thinking-6bit"`
to that list; edit the file with the edit tool, do not rewrite it.

Why these fields: `supportsDeveloperRole: false` keeps Pi from sending the
system prompt as a `developer` message, which this server does not expect;
`thinkingFormat: qwen-chat-template` matches how the model emits thinking;
`maxTokens 16384` and `contextWindow 56000` match the server. Sampling is
the model card's agentic setting, 1 / 0.95 / 20.

Re-run the check. Restart Pi if it was open; it reads models.json at start.
```

`reference/04-provider-opencode.md`:
```markdown
# Phase 4 (OpenCode): Provider

Check: `opencode models omlx 2>/dev/null | grep -q 'omlx/Mellum2.1-12B-A2.5B-Thinking-6bit'`.

If missing, the provider block lives in the global config,
`~/.config/opencode/opencode.json` or `opencode.jsonc`. That file may hold
comments, so do not run it through the merge script. Read
`$PKG/templates/opencode/provider.omlx.json` and insert it with the edit tool:

- No `provider` key yet: add the whole `"provider": { "omlx": {...} }` object.
- A `provider` key but no `omlx`: add the `"omlx": {...}` entry inside it.
- An `omlx` provider already: add only the
  `"Mellum2.1-12B-A2.5B-Thinking-6bit": {...}` entry inside its `models`.
  Do not touch the user's other models or their `options`.

Show the user the exact insertion before making it. The `limit` block
(context 56,000, output 16,384) matches the server from phase 3; a
smaller output limit cuts long tasks off.

Re-run the check.
```

`reference/05-worker-pi.md`:
```markdown
# Phase 5 (Pi): Mellum Worker agent

Mellum Worker runs as a child of the `pi-subagents` package. Check for it:
`grep -q 'pi-subagents' ~/.pi/agent/settings.json`. If absent, tell the user
Mellum Worker needs it (`pi install https://github.com/nicobailon/pi-subagents`),
and that Mellum Mode (`/mellum`) works without it. Skip the rest of this
phase if they decline.

Check: `~/.pi/agent/agents/mellum-worker.md` exists and its
`subagentOnlyExtensions` line is an absolute path to an existing
`mellum-guards.ts`.

If missing or stale, render it with the package's absolute path. The path
must be absolute; pi-subagents does not expand `~` here.

```bash
mkdir -p ~/.pi/agent/agents
node "$PKG/scripts/render-agent.mjs" pi "$PKG" > ~/.pi/agent/agents/mellum-worker.md
cat ~/.pi/agent/agents/mellum-worker.md
```

Confirm the guards line points at a file that exists:

```bash
test -f "$(grep '^subagentOnlyExtensions:' ~/.pi/agent/agents/mellum-worker.md | cut -d' ' -f2)" && echo ok
```

What the frontmatter does: `systemPromptMode: replace` drops Pi's base
prompt, the three `inherit*: false` lines keep AGENTS.md and the skills
catalog out of the child, `extensions:` empty keeps every other extension
out (pi-subagents warns about an empty list at launch; that is intended),
`tools:` is the seven file tools, `excludeTools: contact_supervisor` removes
the supervisor protocol the model failed, and `acceptance: none` leaves
verification to the parent, which runs the tests itself.

Optional, global, and it affects every subagent the user has: setting
`{"intercomBridge": {"mode": "off"}}` in
`~/.pi/agent/extensions/subagent/config.json` halves the child's prompt.
Mention it; do not apply it unasked.

Re-run the check.
```

`reference/05-worker-opencode.md`:
```markdown
# Phase 5 (OpenCode): Mellum Worker agent

Check: `~/.config/opencode/agents/mellum-worker.md` exists and its body is
the prompt in `$PKG/prompts/mellum-worker.md`.

If missing or stale:

```bash
mkdir -p ~/.config/opencode/agents
node "$PKG/scripts/render-agent.mjs" opencode > ~/.config/opencode/agents/mellum-worker.md
cat ~/.config/opencode/agents/mellum-worker.md
```

If the user's global `opencode.json` already has an `agent.mellum-worker`
block (an older hand-made one), show both and ask which to keep; the JSON
block overrides the markdown file. Recommend removing the JSON block.

Limits to state plainly: OpenCode has no Mellum Mode and no guards. There
is no hook that rewrites the outgoing request or nudges an empty final
turn, so the `steps: 40` cap is the only guard. OpenCode also injects the
user's global and project AGENTS.md into subagents; keep those files short
or expect them in Mellum's context. The OpenCode port is unmeasured; the
numbers in the README are from Pi.

Re-run the check (`opencode agent list` if available, else the file check).
```

`reference/06-rules.md`:
```markdown
# Phase 6: Rules for the parent model

This phase is always a question, never an automatic write: AGENTS.md
belongs to the user's project.

Ask: "Do you want a short delegation rule added to this project's
AGENTS.md so your main model knows when to hand work to Mellum Worker?"

If yes, append this fragment (create the file if absent, show it first):

```markdown
## Mellum Worker

Delegate to `mellum-worker` when a task is bounded: you can name the exact
files, a literal search term, the precise change, and the test command.
Put all four in the brief. It is not for exploration, design, or multi-step
plans. After it reports, run the test command yourself before trusting the
result. If it reports "produced no output", re-dispatch once with the same
brief.
```

If no, record that the user declined and move on. Check for this phase:
the user answered.
```

`reference/07-smoke.md`:
```markdown
# Phase 7: Smoke test

A disposable copy of a three-test calculator whose total ignores quantity.

```bash
SMOKE="$(mktemp -d)/calculator"
cp -R "$PKG/skills/mellum-setup/smoke/calculator" "$SMOKE"
cd "$SMOKE" && node --test calculator.test.js; echo "exit $?"   # expect 1 (failing)
```

Then run the worker on it, from inside `$SMOKE`:

- Pi, Worker: start `pi` in `$SMOKE` and say
  "Use mellum-worker to do this: the cart total ignores quantity, fix it.
  Test command: node --test calculator.test.js"
- Pi, Mode: start `pi` in `$SMOKE` and type
  `/mellum the cart total ignores quantity, fix it. Test command: node --test calculator.test.js`
- OpenCode: start `opencode` in `$SMOKE` and say
  "Delegate to mellum-worker: the cart total ignores quantity, fix it.
  Test command: node --test calculator.test.js"

Check: `cd "$SMOKE" && node --test calculator.test.js` exits 0 and
`calculator.js` multiplies `priceCents` by `quantity`. Typical time on an
M-series Mac is under a minute.

If it fails: confirm phase 3's server answers, that the host picked
`omlx/Mellum2.1-12B-A2.5B-Thinking-6bit` (Pi shows it in the status line;
OpenCode in the session header), and that the brief named the test
command. Report what you saw; do not loosen any setting to make it pass.
```

- [ ] **Step 7: Run the skill tests and the full suite**

Run: `node --test tests/`
Expected: all pass, including the manifest test's "skills path exists".

- [ ] **Step 8: Commit**

```bash
git add skills scripts/render-agent.mjs tests/skill.test.mjs
git commit -m "feat: mellum-setup skill with phased references and smoke fixture

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Docs and README

**Files:**
- Create: `docs/recipe.md`
- Create: `docs/backends/omlx.md`
- Create: `docs/backends/ollama.md`
- Modify: `README.md` (replace the stub)
- Create: `tests/docs.test.mjs`

- [ ] **Step 1: Write the failing docs test**

`tests/docs.test.mjs`:
```js
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const ROOT = resolve(import.meta.dirname, "..");
const read = (p) => readFileSync(resolve(ROOT, p), "utf8");

test("README carries both pinned install lines and the status table", () => {
	const readme = read("README.md");
	const version = JSON.parse(read("package.json")).version;
	assert.ok(readme.includes(`mellum-worker@git+https://github.com/pauleveritt/mellum-worker.git#v${version}`));
	assert.ok(readme.includes(`pi install git:github.com/pauleveritt/mellum-worker@v${version}`));
	assert.match(readme, /15\/15/);
	assert.match(readme, /unmeasured/i);
	assert.match(readme, /uv run --offline pytest -q/);
});

test("every relative markdown link in docs and README resolves", () => {
	for (const file of ["README.md", "docs/recipe.md", "docs/backends/omlx.md", "docs/backends/ollama.md"]) {
		const dir = resolve(ROOT, file, "..");
		for (const m of read(file).matchAll(/\]\(([^)#:]+)(?:#[^)]*)?\)/g)) {
			assert.ok(existsSync(resolve(dir, m[1])), `${file}: broken link ${m[1]}`);
		}
	}
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/docs.test.mjs`
Expected: FAIL (install lines missing, docs files missing).

- [ ] **Step 3: Write docs/backends/omlx.md**

```markdown
# Backend: oMLX on Apple Silicon

The measured backend. Everything here is what the setup skill's phases 2
and 3 do, for people who prefer to do it by hand.

## Weights

```bash
hf download pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit \
  --local-dir ~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit
```

9.9 GB, two safetensors shards, MLX affine 6-bit, group size 64, MoE
routers at 8 bits. The folder name is the model id every config uses.

## Serve

```bash
omlx serve \
  --model-dir "$HOME/.cache/huggingface/hub" \
  --host 127.0.0.1 --port 8001 \
  --max-concurrent-requests 1 --hot-cache-max-size 0 --memory-guard-gb 14
```

`--model-dir` is the parent of the model folder. The menu-bar app works
the same way: add that parent directory and set the same options.

## Per-model settings

In the admin page at `http://127.0.0.1:8001/admin`, or via
`PUT /admin/api/models/Mellum2.1-12B-A2.5B-Thinking-6bit/settings`:

| setting | value |
| --- | --- |
| `max_context_window` | 56000 |
| `max_tokens` | 16384 |
| `forced_ct_kwargs` | `["enable_thinking"]` |
| TurboQuant / cache quantization | off |

Clients send their own `max_tokens`, sampling, and penalties, and oMLX
gives the request precedence over the profile. The profile values are
ceilings and the thinking lock.

## Memory

Measured on an M5 Max with 128 GB: a cold 50,000-token prompt plus 4,096
generated tokens peaked at 11.74 GiB physical memory. A 16 GB machine was
not tested; the memory guard of 14 is a starting ceiling, not a promise.
```

- [ ] **Step 4: Write docs/backends/ollama.md**

```markdown
# Backend: Ollama (not yet supported)

The recipe is backend-agnostic in principle: a prompt, seven tools, an
OpenAI-compatible endpoint, thinking on, and the sampling in the templates.
Nothing here has been run on Ollama. A port needs, in order:

1. A GGUF of `JetBrains/Mellum2.1-12B-A2.5B-Thinking` at a quantization
   that keeps the hybrid attention cache native. Note that an earlier
   llama.cpp run of the BF16 weights with thinking on exhausted a 4,096
   output cap without answering; the 16,384 cap is the first thing to set.
2. A Modelfile carrying the model's chat template, `num_ctx 56000`,
   `num_predict 16384`, temperature 1, top_p 0.95, top_k 20, and whatever
   Ollama's equivalent of forcing `enable_thinking` is at that time.
3. Confirmation that tool calls parse: a single `read` call round-trips
   through `/v1/chat/completions` with `tools` set.
4. A provider template per host pointing at `http://127.0.0.1:11434/v1`.
5. A rerun of the ladder from the `mellum-mlx` research repo against that
   endpoint, and the numbers added to the README's status table.

Until then the setup skill stops at preflight on anything but Apple
Silicon with oMLX.
```

- [ ] **Step 5: Write docs/recipe.md**

Copy `docs/mellum-worker.md` from `mellum-mlx` and edit it:

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
mkdir -p docs/backends
cp /Users/pauleveritt/projects/pauleveritt/mellum-mlx/docs/mellum-worker.md docs/recipe.md
```

Then make these edits in `docs/recipe.md` with the edit tool:

1. Under the title, add one line: `Installed from this repo; measured in [mellum-mlx](https://github.com/pauleveritt/mellum-mlx), where the ladder, fixtures, and every phase record live.`
2. Section 2: replace the sentence that begins "Serve `Mellum2.1-12B-A2.5B-Thinking-6bit` on oMLX 0.6.4 as in the main [README]" with "Serve it as described in [backends/omlx.md](backends/omlx.md)." Remove the paragraph starting "The oMLX admin API is at" and the sentence about `ladder/omlx_profiles.py`.
3. Section 3: change `.pi/agents/mellum-worker.md` to `~/.pi/agent/agents/mellum-worker.md` (written by the setup skill from `templates/pi/mellum-worker.agent.md`); change `.pi/mellum/mellum-guards.ts` to `extensions/mellum-guards.ts`; delete the "Try it safely" code block and replace it with "Try it safely: the setup skill's phase 7 copies a disposable fixture."
4. Section 4b: replace `pi -e .pi/mellum/mellum-mode.ts -e .pi/mellum/mellum-guards.ts` with "Mellum Mode loads with the package; no `-e` flags." Delete the caution about `-e` paths being relative to the repo root.
5. Section 5 (Measuring): replace the body with one paragraph: "Measurement lives in the research repo: `uv run python -m ladder.run_ladder` in mellum-mlx. This repo ships the result, not the ruler."
6. Every link of the form `research/ladder/...` or `../README.md`: rewrite to `https://github.com/pauleveritt/mellum-mlx/blob/main/docs/research/ladder/...` and `https://github.com/pauleveritt/mellum-mlx#readme`.

Run the docs link test after editing; it catches any relative link left behind.

- [ ] **Step 6: Write README.md**

```markdown
# mellum-worker

[JetBrains Mellum 2.1](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking),
a 12B-A2.5B thinking model, as a bounded coding worker for
[OpenCode](https://opencode.ai) and [Pi](https://pi.dev). It runs locally,
takes a precise brief, edits code, runs the tests until they pass, and
reports. Your main model stays in charge.

Measured, not guessed: every setting here was ablated in the
[mellum-mlx](https://github.com/pauleveritt/mellum-mlx) research repo.

## Install

OpenCode, in `~/.config/opencode/opencode.json`:

```json
{ "plugin": ["mellum-worker@git+https://github.com/pauleveritt/mellum-worker.git#v0.1.0"] }
```

Pi:

```bash
pi install git:github.com/pauleveritt/mellum-worker@v0.1.0
```

Then run the setup skill. In Pi: `/skill:mellum-setup`. In OpenCode: ask
"run the mellum-setup skill". It walks through weights, the oMLX server,
the provider entry, the agent file, optional delegation rules, and a smoke
test, checking each step and asking before it writes to a file you own.

## What you get

| Host | Deliverable | How to use it | Ladder result |
| --- | --- | --- | --- |
| Pi | Mellum Worker, a pi-subagents child | "Use mellum-worker to ..." | 15/15 |
| Pi | Mellum Mode, in your own session | `/mellum <task>`, `/mellum on`, `/mellum off` | 14/15 |
| OpenCode | Mellum Worker subagent | "Delegate to mellum-worker ..." | ported, unmeasured |

The ladder is five coding tasks run three times each, in
[mellum-mlx](https://github.com/pauleveritt/mellum-mlx/blob/main/docs/research/ladder/ablation-summary.md).
Bare Pi with Mellum as the primary agent scored 8/15 on the same tasks.

## Requirements (v1)

- Apple Silicon Mac, [oMLX](https://github.com/omlx-ai/omlx) 0.6.4 or newer, 9.9 GB for the weights
- Node 24 or newer
- Pi 1.0 or newer; Mellum Worker also needs
  [pi-subagents](https://github.com/nicobailon/pi-subagents)
- OpenCode 1.18 or newer

Other backends: see [docs/backends/ollama.md](docs/backends/ollama.md) for
what a port needs. Nothing but oMLX has been run.

## How it works

The worker is a 643-character prompt of facts about the test command, seven
file tools, and, in Pi, two guards: a nudge when a turn ends empty (at most
three) and a loop breaker. The prompt's default test commands are
`uv run --offline pytest -q` for a pyproject with pytest and
`node --test <file>` for a package.json with a test file; a command named
in the brief overrides them. Full detail: [docs/recipe.md](docs/recipe.md).

This package registers nothing at load time. OpenCode loads a one-hook
plugin that makes the skill discoverable; Pi loads Mellum Mode, dormant
until you type `/mellum`. The skill writes the provider, agent, and rules
into your own config files from [templates/](templates/).

## Layout

```
prompts/mellum-worker.md      the prompt, single source
extensions/                   Mellum Mode and the child guards (Pi)
opencode/plugin.js            skills-path hook (OpenCode)
skills/mellum-setup/          the guided installer
templates/                    agent files and provider fragments, per host
scripts/                      merge-json and render-agent, used by the skill
docs/                         recipe and backend guides
```

`npm test` runs the suite. `node build.mjs` regenerates the
agent templates after a prompt change.

## Releases

Pin a tag in both install lines. OpenCode treats an unpinned git spec as
"latest" and may refresh it under you. Tags follow semver; the package
version and the tag match, and a test checks it.
```

- [ ] **Step 7: Run the full suite**

Run: `node --test tests/`
Expected: all pass. If the link test reports a broken link in `docs/recipe.md`, fix that link and re-run.

- [ ] **Step 8: Commit**

```bash
git add README.md docs tests/docs.test.mjs
git commit -m "docs: README, recipe, and backend guides

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Publish, tag, and verify both installs

This task is outward-facing: it creates a public GitHub repo. Confirm with the user before Step 1 if they have not already said to publish.

**Files:** none new.

- [ ] **Step 1: Create the GitHub repo and push**

```bash
cd /Users/pauleveritt/projects/pauleveritt/mellum-worker
gh repo create pauleveritt/mellum-worker --public --source . --push --description "Mellum 2.1 as a bounded coding worker for OpenCode and Pi"
```

- [ ] **Step 2: Tag v0.1.0 and push the tag**

```bash
git tag -a v0.1.0 -m "v0.1.0: Mellum Worker and Mellum Mode for Pi, Mellum Worker for OpenCode, oMLX backend"
git push origin v0.1.0
node --test tests/manifest.test.mjs   # the version/tag test now runs for real
```

Expected: pass.

- [ ] **Step 3: Install into Pi from Git and confirm the skill and Mode load**

```bash
pi install git:github.com/pauleveritt/mellum-worker@v0.1.0
ls ~/.pi/agent/git/github.com/pauleveritt/mellum-worker/skills/mellum-setup/SKILL.md
```

Start `pi` in any directory, type `/skill:mellum-setup` and confirm the skill text appears, then `/mellum off` and confirm the reply "mellum-mode is not on" (proves the extension loaded). Quit.

- [ ] **Step 4: Install into OpenCode from Git and confirm the skill is listed**

Add to `~/.config/opencode/opencode.jsonc` `plugin` array (edit tool, keep comments):
`"mellum-worker@git+https://github.com/pauleveritt/mellum-worker.git#v0.1.0"`.

Then:

```bash
ls ~/.cache/opencode/packages/ | grep mellum-worker
opencode run --dir "$PWD" "List the skills available to you by name, nothing else."
```

Expected: the cache directory exists after the first start, and the reply names `mellum-setup`.

- [ ] **Step 5: Run the setup skill end to end in Pi on this machine**

The user's machine already has weights, server, and provider, so phases 1 to 4 should report "already done". Phase 5 writes `~/.pi/agent/agents/mellum-worker.md` (new; the old project-local one in mellum-mlx is untouched). Phase 6: decline. Phase 7: run the smoke test with Mellum Worker and confirm `node --test calculator.test.js` exits 0 in the temp copy.

Record the outcome in the task notes. If phase 7 fails, this is a bug in the package, not in the user's setup; fix and re-tag as v0.1.1.

- [ ] **Step 6: Run the setup skill in OpenCode on this machine**

Phase 4 should find the existing `omlx` provider and add nothing except possibly the `limit.output` change from 4,096 to 16,384 in the Mellum model entry; show it and apply with the user's yes. Phase 5 writes `~/.config/opencode/agents/mellum-worker.md` and finds the old `agent.mellum-worker` JSON block in the global config; recommend removing the JSON block and the now-unused `~/.config/opencode/prompts/mellum-worker.txt`. Phase 7: smoke test via delegation; record pass or fail. A fail here does not block the release (the port is documented as unmeasured) but is recorded in the README status table as "smoke failed on <date>" if it happens.

- [ ] **Step 7: Point the research repo at the new one**

In `mellum-mlx/README.md` (uncommitted, user-owned), do not edit. Instead tell the user: the "Using it as a coding agent" section should add one line, "Install it from https://github.com/pauleveritt/mellum-worker", and they can make that edit when they commit their README.

---

## Self-review notes

- Spec §2 layout: Tasks 2 to 9 create every listed path. `docs/recipe.md` is Task 9; `build.mjs` is Task 6; `tests/` accrue per task.
- Spec §3 skill phases 1 to 7: Task 8 reference files 01 to 07, with the per-host split for 4 and 5.
- Spec §4 Pi extension changes: Task 3 (`createGuardSet`), Task 4 (Mode owns guards, prompt path, header comment), Task 1 (commit handoff first). The Superpowers marker and env overrides are untouched, as the spec says.
- Spec §5 OpenCode: Task 5 plugin and test, Task 6 agent template with Pi-validated sampling and `steps: 40`, provider fragment; stated limits appear in reference/05-worker-opencode.md and README.
- Spec §6 docs, versioning, tests: Task 9 and Task 2's tag test; Task 10 tags.
- Review Focus 1 to 5 each have a named test: Task 6 (`substituteRoot`, provider fragment), Task 7 (merge by id, idempotence), Task 4 (model missing, fresh span).
- Names used across tasks: `createGuardSet`/`GuardSet` (Task 3, used in Task 4); `render`/`substituteRoot`/`PLACEHOLDER` (Task 6, used in Task 8's `render-agent.mjs` and tests); `mergeJson` (Task 7, used by Task 8's reference files via the CLI); `MellumWorkerPlugin` (Task 5).
