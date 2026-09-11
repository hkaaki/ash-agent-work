# CRM cleanup delivery report (Frantic #79)

Published `hkaaki/crm-cleanup@0.2.0` from PR head `cbbbb45fdc60d050ad402a0b515a3b930b7dc0ab` and dogfooded the installed registry package against a live CRM JSON URL.

## Why an operator would install this

- It reads current CRM records from a real source handle at run time (`web_fetch`, `read_projection`, or `connector_export`), not a pasted fixture.
- It proposes allowlisted field updates only when a verbatim transcript quote supports them, then executes those updates through `mock-crm.v1` in the same sealed run.
- A no-op transcript executes nothing (`write_result.executed=false`) instead of inventing work. Fields outside `crm_schema.allowed_fields` are rejected with a named reason.
- The hosted registry already reran the harness: 4 of 4 passed.

## Same revision everywhere

- Package name: `crm-cleanup`
- Publisher owner: `hkaaki`
- Document version in X.yaml: `0.2.0`
- Live registry version: `0.2.0`
- Source revision: `cbbbb45fdc60d050ad402a0b515a3b930b7dc0ab`
- PR: https://github.com/runxhq/runx/pull/459
- Source tree: https://github.com/hkaaki/runx/tree/cbbbb45fdc60d050ad402a0b515a3b930b7dc0ab/skills/crm-cleanup
- Raw X.yaml: https://raw.githubusercontent.com/hkaaki/runx/cbbbb45fdc60d050ad402a0b515a3b930b7dc0ab/skills/crm-cleanup/X.yaml
- Raw SKILL.md: https://raw.githubusercontent.com/hkaaki/runx/cbbbb45fdc60d050ad402a0b515a3b930b7dc0ab/skills/crm-cleanup/SKILL.md
- Registry listing: https://runx.ai/x/hkaaki/crm-cleanup@0.2.0
- Digest: `sha256:11541e15a7d15d9e4b3dc958f930a55a23eef05f49a1d23edb0834e5fc508498`

## CLI

- `runx --version` printed `runx-cli 0.9.0`
- Publish: `runx login --provider github --for publish --from-gh` then `runx registry publish /tmp/runx-crm-cleanup/skills/crm-cleanup/SKILL.md --registry=https://api.runx.ai --version 0.2.0`
- Install: `runx add hkaaki/crm-cleanup@0.2.0 --registry https://api.runx.ai`
- Local harness before publish: `runx harness ./skills/crm-cleanup` passed 4/4
- Hosted harness after publish: passed 4/4
- Dogfood: `runx skill hkaaki/crm-cleanup@0.2.0 --registry https://api.runx.ai --inputs input.json --json --receipt-dir receipts`
- Verify: `runx verify --receipt receipts/sha256-c554a805b1ae0d0a689f3338a21f53ee70f2468a0a491034f53b12111258e368.json --allow-local-development-signatures --json` verdict `valid=true`

## Harness cases

- `crm-cleanup-applies-traced-updates`: sealed (2 traced updates + executed write)
- `crm-cleanup-noop-executes-nothing`: sealed (`decision=no_action`, `executed=false`)
- `crm-cleanup-rejects-unlisted-field`: sealed (owner rejected as outside allowlist, no write)
- `crm-cleanup-needs-transcript`: failure (expected; transcript is required)

## Dogfood observations

- Source read: `web_fetch` of `https://raw.githubusercontent.com/hkaaki/ash-agent-work/2de5fbbc757fdd07835d5affe674ef1c45bf8afa/frantic-79-crm-cleanup/globex.json` (count 1). Records were not passed as a fixture argument.
- Field updates: `acct-globex.account_status` healthy to at_risk; `acct-globex.next_action` none to send the Q3 usage report by Friday. Each line carries a verbatim transcript quote.
- Write result: `mock-crm.v1` `executed=true` with sealed before/after snapshots.
- Decision: `applied`. Rejected updates: none.
- Receipt id: `sha256:c554a805b1ae0d0a689f3338a21f53ee70f2468a0a491034f53b12111258e368`
- Receipt ref: `runx:receipt:sha256:c554a805b1ae0d0a689f3338a21f53ee70f2468a0a491034f53b12111258e368`

## New user, no private context

- Install with `runx add hkaaki/crm-cleanup@0.2.0 --registry https://api.runx.ai`
- Write `input.json` with `crm_source` (kind, url, allowlist), `transcript`, and `crm_schema.allowed_fields`
- Run `runx skill hkaaki/crm-cleanup@0.2.0 --registry https://api.runx.ai --inputs input.json --json --receipt-dir receipts`
- Verify the sealed receipt with `runx verify --receipt <receipt.json> --allow-local-development-signatures --json`
- Inspect the public listing at https://runx.ai/x/hkaaki/crm-cleanup@0.2.0 and the PR at https://github.com/runxhq/runx/pull/459
