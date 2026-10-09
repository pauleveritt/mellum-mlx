# Mellum Worker distribution repo: design

Status: approved design, 2026-10-09. Implementation plan follows separately.

## 1. Purpose

Package the shipped "Mellum 2.1 as a bounded coding worker" recipe so that
other people can install it into OpenCode and Pi directly from a Git
repository, with no npm publish, and set it up through a guided skill.

The research, conversion script, ladder, fixtures, and ablation records stay
in `mellum-mlx`. The new repo ships only what a user needs to run the recipe.

Audience and scope decisions, in the order they were made:

- The long-term goal is non-MLX and non-Mac. Version 1 implements the oMLX
  backend on Apple Silicon, the only one measured. Ollama is a documented
  later phase.
- The package registers nothing at load time. It does not add a provider,
  agent, or default model. The skill writes those into the user's own files,
  visibly.
- Mac users download the published 6-bit quant from the Hub:
  `pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit`. No local conversion.
- Installing into Pi gives both Mellum Worker (a pi-subagents child agent)
  and Mellum Mode (the Pi-core `/mellum` extension). Installing into OpenCode
  gives Mellum Worker as a subagent only.

## 2. Repository layout and install contract

Repo: `github.com/pauleveritt/mellum-worker`. Tagged releases from `v0.1.0`.

Install lines:

```
OpenCode  "plugin": ["mellum-worker@git+https://github.com/pauleveritt/mellum-worker.git#v0.1.0"]
Pi        pi install git:github.com/pauleveritt/mellum-worker@v0.1.0
```

Layout:

```
package.json                  name, version, type: module,
                              main: ./opencode/plugin.js,
                              keywords: [pi-package],
                              pi: { extensions: [./extensions/mellum-mode.ts],
                                    skills: [./skills] }
opencode/plugin.js            config hook: append <pkg>/skills to skills.paths
extensions/mellum-mode.ts     Mellum Mode (moved from .pi/mellum)
extensions/mellum-guards.ts   guard functions and child-only extension (moved)
prompts/mellum-worker.md      prompt v5, the single source of truth
skills/mellum-setup/SKILL.md  guided installer, dispatcher only
skills/mellum-setup/reference/  one file per phase, loaded on demand,
                                plus the smoke-test fixture
templates/pi/mellum-worker.agent.md   Pi agent file, guards path placeholder
templates/pi/models.omlx.json         provider and model entry for models.json
templates/opencode/mellum-worker.md   OpenCode agent markdown
templates/opencode/provider.omlx.json omlx provider block
docs/recipe.md                the recipe, ladder material replaced by links
docs/backends/omlx.md         serve command, admin settings, weights
docs/backends/ollama.md       stub naming what a port needs
build.mjs                     regenerates agent templates from the prompt
tests/                        node --test
```

Contracts:

1. At load time the package only makes the skill discoverable (OpenCode)
   and loads Mellum Mode (Pi). It never writes the user's model default,
   provider list, or agent files.
2. Prompt v5 exists in one file. `build.mjs` embeds it into both agent
   templates. A test fails on drift.
3. The Pi `extensions` list is explicit, never a glob, so the guards file is
   not loaded as a package extension.

## 3. The setup skill

One skill, `mellum-setup`. Pi users run `/skill:mellum-setup`; OpenCode users
ask for it through the skill tool. The SKILL.md body is a dispatcher: detect
the host tool and the state of each phase, load the reference file for the
phase that needs work. Phases are idempotent and each ends with a check.

1. Preflight. Confirm Apple Silicon and oMLX. Any other backend is pointed at
   `docs/backends/ollama.md` and the skill stops. Record the host tool.
2. Weights. `hf download pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit`
   into the oMLX model directory. Check: both shards present.
3. Server. Start or verify oMLX on port 8001 with the recipe's serve flags
   and admin settings. The skill asks before changing admin settings because
   they apply to every model the user serves. Check: `GET /v1/models` lists
   the model id.
4. Provider. Pi: merge the template entry into `~/.pi/agent/models.json`,
   preserving other providers. OpenCode: merge the provider block into the
   global config. Check: the tool's model list shows the model.
5. Worker. Pi: copy the agent template to `~/.pi/agent/agents/mellum-worker.md`
   with the absolute clone path substituted into the guards line. If
   pi-subagents is absent, say so and skip; Mode still works. OpenCode: write
   `~/.config/opencode/agents/mellum-worker.md`. Check: the agent is listed.
6. Rules. Offer an AGENTS.md fragment telling the main model when to delegate
   to Mellum Worker. Always asks; project files belong to the user.
7. Smoke test. Run one bounded task on a throwaway fixture bundled under the
   skill's reference folder, shaped like the ladder's smallest rung.

The skill prints a summary before writing to any file that already exists.
Mode needs no phase; the skill only tells the user the `/mellum` commands.

## 4. Pi extensions as a package

Problem: whatever `pi.extensions` lists loads in every Pi session, parent and
child. Today the guards load only into the child (via the agent file) or
alongside Mode (via a second `-e`).

Changes:

- Only `mellum-mode.ts` is a package extension.
- `mellum-guards.ts` stays a standalone extension loaded into the child by
  absolute path from the agent file. It is never loaded by the package.
- Mode imports the pure guard functions from the guards file and wires them
  into its own hooks, active only between `/mellum on` and `/mellum off` or
  during a one-shot. `/mellum` therefore works from a bare install.
- Prompt path becomes `../prompts/mellum-worker.md` relative to the
  extension. The clone is whole, so the path holds under
  `~/.pi/agent/git/github.com/pauleveritt/mellum-worker/`.
- The Pi agent template's guards line holds a placeholder. The skill writes
  the absolute clone path, which is stable across `pi update` because Pi
  keys clones by owner and repo.
- The Superpowers bootstrap marker stays a constant; it is a no-op when
  Superpowers is absent.
- Model and provider overrides stay as the existing environment variables.
- The uncommitted handoff-collapse change is committed in `mellum-mlx`
  first, then the file is copied, so the new repo starts from the measured
  version plus that feature.

Tests: existing guard and Mode Node tests move over, plus one test that
Mode's guard hooks are inert while Mode is off.

## 5. OpenCode side

Plugin: `opencode/plugin.js`, no dependencies. A named async export returning
a `config` hook that appends `<package>/skills` to `skills.paths` when
absent, plus a default export with an id and the same function for the V2
host. One test calls the hook twice on an empty config and checks the path
appears once.

Agent template `templates/opencode/mellum-worker.md`: `mode: subagent`, the
omlx model, a `steps` cap, the six tools turned off (skill, task, todowrite,
todoread, webfetch, websearch), allow permissions for read, grep, glob, list,
edit, bash, and the thinking kwargs under `options`. Body is prompt v5.

Sampling decision: ship the Pi-validated numbers in OpenCode too, so both
tools run one recipe. Temperature 1, top-p 0.95, top-k 20, output limit
16,384, context 56,000. The older global OpenCode block used greedy sampling
with a 4,096 limit; that predates the ladder and the finding that 4,096 cut a
run off. The OpenCode port is unmeasured either way and the README says so.

Provider template: openai-compatible adapter, local base URL, model entry
with context 56,000, output 16,384, reasoning on, tool calls on, reasoning
content interleaved.

Stated limits: OpenCode has no Mode and no guards, because it has no hook
that rewrites the outgoing payload or nudges an empty final turn. The `steps`
cap is the only guard. OpenCode injects global and project AGENTS.md into
subagents; Pi's `inheritProjectContext: false` avoids that. Adding an
OpenCode harness to the ladder stays a future-work item in `mellum-mlx`.

## 6. Docs, backends, versioning, testing

README: the two install lines, "run the setup skill", what each tool gets,
and a status table: Pi Worker 15/15, Pi Mode 14/15, OpenCode ported and
unmeasured. It states that prompt v5's default test commands assume
uv/pytest or a Node test file, and that a command named in the task
overrides them.

`docs/recipe.md`: the current recipe with ladder and ablation sections
replaced by links to `mellum-mlx`. `docs/backends/omlx.md`: serve command,
admin settings, weights. `docs/backends/ollama.md`: a stub naming what a
port needs: a GGUF of the Thinking model, a Modelfile with chat template and
sampling params, confirmed tool-call parsing, and a ladder rerun.

Backends in the skill: preflight branches on a backend name; oMLX is the only
implemented branch. Adding Ollama means one reference file and one provider
template per tool, no dispatcher change.

Versioning: semantic tags, pinned in both install lines. package.json
version matches the tag, checked by a test, because OpenCode treats a bare
git spec as latest and may refresh it.

Tests, all `node --test`, no build step:

- guards and Mode tests, plus Mode-off inertness
- plugin config-hook idempotence
- prompt v5 matches both agent template bodies
- every path in the `pi` key and `main` exists
- package.json version matches the latest tag

The skill's smoke test is the only thing that touches a live server and is
not part of the suite.

## 7. Out of scope for v1

- Any backend other than oMLX.
- Measuring the OpenCode port.
- A pi-subagents replacement or lighter delegation package.
- Publishing to npm.
