# Bookkeeper delivery report (Frantic #89)

Published `hkaaki/bookkeeper@sha-67b50fed5091` from PR head `cde68bc6960baf37f9a13b47a7c38a0c0e0fcf26` and dogfooded the installed registry package.

## Why an operator would install this

- It maps a bounded `transactions[]` batch onto a supplied `chart_of_accounts` and returns categorized lines, anomalies, and reconciliation counts.
- It refuses to guess when two chart accounts share the same keywords, and it returns `needs_review` instead of inventing a GL account.
- It is read-only: `ledger_mutation` is false, `write_count` is 0, and there are no file, network, or journal effects.
- The hosted registry already reran the harness: 4 of 4 passed.

## Same revision everywhere

- Package name: `bookkeeper`
- Publisher owner: `hkaaki`
- Document version in X.yaml: `0.1.0`
- Live registry version: `sha-67b50fed5091`
- Source revision: `cde68bc6960baf37f9a13b47a7c38a0c0e0fcf26`
- PR: https://github.com/runxhq/runx/pull/458
- Source tree: https://github.com/hkaaki/runx/tree/cde68bc6960baf37f9a13b47a7c38a0c0e0fcf26/skills/bookkeeper
- Raw X.yaml: https://raw.githubusercontent.com/hkaaki/runx/cde68bc6960baf37f9a13b47a7c38a0c0e0fcf26/skills/bookkeeper/X.yaml
- Raw SKILL.md: https://raw.githubusercontent.com/hkaaki/runx/cde68bc6960baf37f9a13b47a7c38a0c0e0fcf26/skills/bookkeeper/SKILL.md
- Registry listing: https://runx.ai/x/hkaaki/bookkeeper@sha-67b50fed5091
- Digest: `sha256:33ff95d73aff1a5a73f8a0a1e0d4ac9a11f6e2fc9010dd8358b888972d413444`

## CLI

- `runx --version` printed `runx-cli 0.9.0`
- Publish: `runx login --provider github --for publish --from-gh` then `runx registry publish /tmp/runx-bookkeeper/skills/bookkeeper/SKILL.md --registry=https://api.runx.ai`
- Install: `runx add hkaaki/bookkeeper@sha-67b50fed5091 --registry https://api.runx.ai`
- Local harness before publish: `runx harness ./skills/bookkeeper` passed 4/4
- Hosted harness after publish: passed 4/4
- Dogfood: `runx skill hkaaki/bookkeeper@sha-67b50fed5091 --registry https://api.runx.ai --inputs input.json --json --receipt-dir receipts`
- Verify: `runx verify --receipt receipts/sha256-1da25f975eebf5901f70bdb53cc18071385257f83f7f11f8fd8a8276de443aac.json --allow-local-development-signatures --json` verdict `valid=true`

## Harness cases

- `sealed_clean_batch_reconciles_read_only`: sealed
- `refused_ambiguous_transactions_return_needs_review`: refused (`needs_review` / `ambiguous_account_match`)
- `bookkeeper-clean-batch`: sealed
- `bookkeeper-ambiguous-needs-review`: refused (`needs_review` / `ambiguous_account_match`)

## Dogfood observations

- Categorized count: 3
- Anomaly count: 1
- Reconciliation totals: matched 3, unmatched 0, status `needs_review`
- needs_review reason: `0 unmatched transaction(s) and 1 anomaly finding(s) require review` because Staples `2026-06-28` is outside `2026-07-01` through `2026-07-31`
- Receipt id: `sha256:1da25f975eebf5901f70bdb53cc18071385257f83f7f11f8fd8a8276de443aac`
- Receipt ref: `runx:receipt:sha256:1da25f975eebf5901f70bdb53cc18071385257f83f7f11f8fd8a8276de443aac`
- Each categorized line binds to an existing chart account (`6100`, `4000`, `6200`) with confidence and reason
- No ledger mutation

## New user, no private context

- Install with `runx add hkaaki/bookkeeper@sha-67b50fed5091 --registry https://api.runx.ai`
- Write `input.json` with `transactions`, `chart_of_accounts`, and `prior_period`
- Run `runx skill hkaaki/bookkeeper@sha-67b50fed5091 --registry https://api.runx.ai --inputs input.json --json --receipt-dir receipts`
- Verify the sealed receipt with `runx verify --receipt <receipt.json> --allow-local-development-signatures --json`
- Inspect the public listing at https://runx.ai/x/hkaaki/bookkeeper@sha-67b50fed5091 and the PR at https://github.com/runxhq/runx/pull/458
