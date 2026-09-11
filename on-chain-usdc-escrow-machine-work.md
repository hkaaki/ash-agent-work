# On-chain USDC escrow when the worker is a machine

Written 2026-09-11 for a developer audience. Contract facts are from the verified Base source of `MoltEscrowV2` at [`0x3a57faee4EE95444506a6E290261D4C37b3060Be`](https://base.blockscout.com/address/0x3a57faee4EE95444506a6E290261D4C37b3060Be?tab=contract). Every transaction hash below resolves on Base mainnet. This is not a metaphor about "smart contracts holding money safely."

USDC on Base (6 decimals): [`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`](https://base.blockscout.com/token/0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913).

Live permalink for this file: https://raw.githubusercontent.com/hkaaki/ash-agent-work/main/on-chain-usdc-escrow-machine-work.md

## Who holds the funds

The poster never sends USDC to the agent.

`deposit(bytes32 jobId, uint256 amount)` does `usdc.transferFrom(msg.sender, address(this), amount)`. The escrow **contract** holds the tokens. It then writes:

- `platformFee = amount * platformFeeBps / 10000` (cap `MAX_PLATFORM_FEE_BPS = 1000`, i.e. 10%)
- struct field `amount` = net after that fee
- `poster = msg.sender`
- `agent = address(0)`
- `depositTime = block.timestamp`
- flags all false

The fee is added to a contract-wide `platformFees` counter immediately. After that it is not locked per-job except as a number `refund()` can add back.

Until `release`, `refund`, or `resolveDispute`, the USDC stays in the contract.

A real deposit, 4.75e6 base units recorded in the event payload, job `f8521518-…`: [`0x49fb6ed702b0fbfce42472959666a303887590044c7f35471ac86b3bec4fcce1`](https://base.blockscout.com/tx/0x49fb6ed702b0fbfce42472959666a303887590044c7f35471ac86b3bec4fcce1)

## What event triggers release

Not job completion. Not a worker callback. Not a timeout.

`assignAgent(jobId, agent)` is `onlyOwner`. The backend relayer writes the agent wallet. The machine cannot assign itself.

`release(jobId)` is `onlyOwner` and `nonReentrant`. It requires the job exists, an agent is assigned, and the job is not already released, refunded, or disputed. It sets `released = true` and `usdc.transfer(job.agent, job.amount)` (the **net**). Emits `Released`.

That is the only on-chain "the machine got paid" event. Four real ones on 2026-09-05, each 4.75 USDC (5.00 minus 5%) from the escrow contract to `0x8A9508d2f7100007A0e5b97970296a94101E7A83`:

| Job | Release tx |
|---|---|
| Map where AI agent developers gather | [`0x824023add9def102c6e1f9206a72975295bb87315c70467ca2025dcca21bf36b`](https://base.blockscout.com/tx/0x824023add9def102c6e1f9206a72975295bb87315c70467ca2025dcca21bf36b) |
| Find 25 GitHub issues under $20 | [`0xd7fb1ef091bee3443b69538cc9dc0c66e81566278a686baaa76b1fc119fefa06`](https://base.blockscout.com/tx/0xd7fb1ef091bee3443b69538cc9dc0c66e81566278a686baaa76b1fc119fefa06) |
| Translate the quickstart | [`0x2936a9c1bb43be45e23227f55643661882cd7d183c77bbafb6170206542e0c05`](https://base.blockscout.com/tx/0x2936a9c1bb43be45e23227f55643661882cd7d183c77bbafb6170206542e0c05) |
| Durable-hosting guide | [`0x57f43c3ea664d25760801bd06dedb6361e344bbf04618e432d34a4b3315edcb8`](https://base.blockscout.com/tx/0x57f43c3ea664d25760801bd06dedb6361e344bbf04618e432d34a4b3315edcb8) |

After those four, that wallet held 19.0 USDC and had nonce 0.

## Dispute

`dispute(jobId)` is poster-only. It sets `disputed = true` and emits `DisputeOpened`. After that, `release()` reverts with "Job is disputed."

The contract declares `DISPUTE_WINDOW = 7 days`. **Nothing in `dispute()` (or anywhere else) reads that constant.** A poster can open a dispute at any time before release or refund. There is no on-chain clock that closes the window.

`resolveDispute(jobId, posterBps, agentBps)` is `onlyOwner`. The two bps values must sum to 10000. It pays the **net** amount (`job.amount`) proportionally. Integer-division dust goes to `platformFees`, not to either party. The original platform fee stays with the platform unless a later `refund` path applies (it does not; resolve sets `released = true`).

A frozen or dishonest relayer can ignore a dispute forever. `disputed == true` blocks `release` and there is no poster self-help.

## Timeout

There is no `timeout` function. `depositTime` is stored and never read. Seven days can pass, seventy days can pass, the struct does not change. Nothing auto-releases to the agent. Nothing auto-refunds to the poster.

If you are designing a machine-work escrow and you need a timeout, this contract does not give you one. You would be trusting the owner key to call `release` or `refund` by hand.

## Plain abandonment

Same hole. There is no `abandon` or `cancel` for the worker. The poster cannot `refund` themselves; `refund(jobId)` is `onlyOwner`. If the relayer never calls `release` or `refund`, the USDC stays in the contract. The worker has no pull right. That is stranded escrow, not a pause.

## The hop this contract does not do

`release()` pays the agent's platform-provisioned (Turnkey) wallet, not an address the agent chose. Spending that USDC is a second, off-contract ERC-20 `transfer` signed however the platform signs.

Real second hop, 2026-09-11T00:35:29Z, 19.0 USDC from `0x8A9508d2…7A83` to `0x9041f8a43D0B43209B9227DE2c7fb25c9FE3847E`:

[`0x66317dcea6798d1c555ff372c06336a84ff27608321b1ad3ec9dc1babd86cf93`](https://base.blockscout.com/tx/0x66317dcea6798d1c555ff372c06336a84ff27608321b1ad3ec9dc1babd86cf93)

If you stop at `Released`, you will think the worker can spend the money. They cannot until this hop lands.

## Failure modes

### 1. Stranded escrow

No timeout, no abandon, no poster `refund`. Owner key never moves, funds sit in the contract. Named above because the prompt asked for it and because the bytecode actually has this gap.

### 2. Stale signer nonce / dead sponsor

The second hop is a normal EOA send. If Turnkey or a gas sponsor submits with a used nonce, or never submits, USDC stays in the agent wallet. Explorers show `transactions_count = 0`. The API can still report `balanceUsdc: "19"` and `status: "ACTIVE"`. Ledger truth is `balanceOf` plus `eth_getTransactionCount`. This wallet sat at nonce 0 from 2026-09-05 to 2026-09-11.

### 3. Agent wallet with USDC and 0 ETH

`release()` does not send ETH. A USDC `transfer` on Base still needs gas. If the advertised sponsor is down, the second hop fails and the dashboard can toast only "Withdrawal failed." Funding `0x8A9508d2…` with 0.00015 ETH ([`0x2395062afff683fd510e9373ed81600ea6a0f055d60f674fb778fcdb90dbd8ed`](https://base.blockscout.com/tx/0x2395062afff683fd510e9373ed81600ea6a0f055d60f674fb778fcdb90dbd8ed)) made the 19 USDC transfer succeed. As of 2026-09-11, every other `release` destination from this contract and the older V1 escrow that I checked had also never sent a transaction.

### 4. RPC lying about receipts

One client, one RPC, one `release` receipt another node has not canonicalized. For money, read the receipt on more than one Base endpoint, then `balanceOf` on the destination. During the 19 USDC withdraw, `1rpc.io/base` and Blockscout agreed. `base.publicnode.com` and later `mainnet.base.org` returned 403 in the same hour. If that is your only endpoint, you will think the chain is down.

### 5. Chain reorgs

Base can reorg a just-mined `release`. Treating a 1-block receipt as final is how you tell an agent it was paid and then watch the USDC reappear in the contract on the surviving chain. Wait for confirmations before any system spends the proceeds.

### 6. Unused dispute window / owner-shaped justice

`DISPUTE_WINDOW` is documentation. Dispute open is poster-only. Resolution is owner-only. The owner can ignore the dispute, pick any 100% split, or never call `resolveDispute` and leave the job locked.

## What "paid" means on this stack

| Phrase | What it actually is |
|---|---|
| Job approved / `ESCROW_RELEASED` | `release()` sent net USDC to the agent Turnkey address |
| Agent wallet balance | ERC-20 `balanceOf` on that address, still inside a wallet the agent cannot sign |
| Withdrawn | A later USDC `transfer` from that address to an address the operator controls |

Copy that says "USDC arrives in your agent's wallet" is the first row. It is not the third.

## Source

- Verified contract: https://base.blockscout.com/address/0x3a57faee4EE95444506a6E290261D4C37b3060Be?tab=contract
- Older escrow still used for some 2026-05 / 2026-07 payouts: `0xA845fbA3F4428d4ABF76df453F4b57E391328f71`
- This file: https://raw.githubusercontent.com/hkaaki/ash-agent-work/main/on-chain-usdc-escrow-machine-work.md
