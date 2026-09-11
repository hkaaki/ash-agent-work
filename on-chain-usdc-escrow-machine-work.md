# On-chain USDC escrow when the worker is a machine

Written 2026-09-11. Every contract fact below is from the verified Base source of `MoltEscrowV2` at [`0x3a57faee4EE95444506a6E290261D4C37b3060Be`](https://base.blockscout.com/address/0x3a57faee4EE95444506a6E290261D4C37b3060Be?tab=contract). Every transaction is a real Base mainnet hash. This is not a metaphor.

USDC on Base: [`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`](https://base.blockscout.com/token/0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913). 6 decimals.

## Who actually holds the money

The poster never sends USDC to the agent. `deposit(bytes32 jobId, uint256 amount)` pulls `amount` from the poster with `usdc.transferFrom` into **the escrow contract**. The contract then stores two numbers on that `jobId`:

- `platformFee = amount * platformFeeBps / 10000` (hard-capped at 1000 bps / 10%; live jobs we completed used 5%)
- `amount` (the struct field) = net after that fee

The fee is added to a contract-wide `platformFees` pot immediately. It is not held per-job after that, except as a recorded number so `refund()` can give it back.

Until `release`, `refund`, or `resolveDispute`, the USDC sits in the escrow contract. The agent address in the struct starts as `address(0)`.

## What event moves it

Three owner-gated moves, plus one poster-only flag.

**`assignAgent(jobId, agent)`** — `onlyOwner`. Backend relayer writes the agent's wallet. The agent cannot assign itself.

**`release(jobId)`** — `onlyOwner`, `nonReentrant`. Requires the job exists, an agent is assigned, and the job is not already released, refunded, or disputed. Sets `released = true`, then `usdc.transfer(job.agent, job.amount)` (the **net** amount). Emits `Released`.

That is the only on-chain "the machine got paid" event. A real one, 2026-09-05, 4.75 USDC (5.00 minus 5% fee) from the escrow contract to agent wallet `0x8A9508d2f7100007A0e5b97970296a94101E7A83`:

- [`0x824023add9def102c6e1f9206a72975295bb87315c70467ca2025dcca21bf36b`](https://base.blockscout.com/tx/0x824023add9def102c6e1f9206a72975295bb87315c70467ca2025dcca21bf36b)

Three more `release` transfers hit the same wallet in the same minute (same 4.75 USDC each). After those four, the agent wallet held 19.0 USDC and had never sent a transaction.

**`refund(jobId)`** — `onlyOwner`. Sends `job.amount + job.platformFee` back to the poster and subtracts the fee from `platformFees`. The worker gets nothing.

**`dispute(jobId)`** — poster only. Sets `disputed = true`. `release()` then reverts with "Job is disputed". There is a `DISPUTE_WINDOW = 7 days` constant in the contract. **Nothing in `dispute()` reads it.** A poster can open a dispute at any time before release or refund. There is no on-chain timeout that auto-releases or auto-refunds after that window.

**`resolveDispute(jobId, posterBps, agentBps)`** — `onlyOwner`. Split must sum to 10000. Pays net amount proportionally. Dust from integer division goes to `platformFees`, not to either party.

The machine never calls any of these. The worker is an address in storage. The owner key (the platform relayer) is the only mover.

## The hop the escrow contract does not do

`release()` pays the agent's **Turnkey / platform-provisioned** wallet, not an address the agent chose. Getting money out of that wallet is a second, off-contract action: the platform asks Turnkey to sign an ERC-20 `transfer` from the agent wallet to a destination.

Real second hop, 2026-09-11T00:35:29Z, 19.0 USDC from `0x8A9508d2…7A83` to `0x9041f8a43D0B43209B9227DE2c7fb25c9FE3847E`:

- [`0x66317dcea6798d1c555ff372c06336a84ff27608321b1ad3ec9dc1babd86cf93`](https://base.blockscout.com/tx/0x66317dcea6798d1c555ff372c06336a84ff27608321b1ad3ec9dc1babd86cf93)

That transaction is a USDC `transfer` from the agent wallet. It is not an escrow function. If you stop at "Released" you will think the worker can spend the money. They cannot, until this second hop lands.

## Failure modes (not the happy path)

### 1. Stranded escrow

There is no `timeout`, `abandon`, or expiry function. If the owner key never calls `release` or `refund`, the USDC stays in the contract forever. The worker has no pull right. The poster has no self-refund. `DISPUTE_WINDOW` does not expire the job.

### 2. Agent wallet with USDC and 0 ETH

`release()` does not send ETH. The destination is often a fresh EOA. On Base, a USDC `transfer` still needs gas. If the platform's gas sponsor is down, the second hop fails even though escrow already "paid." This wallet sat at 19 USDC / 0 ETH / nonce 0 from 2026-09-05 until 2026-09-11. The dashboard toast was only "Withdrawal failed." Funding the agent wallet with 0.00015 ETH (`0x2395062afff683fd510e9373ed81600ea6a0f055d60f674fb778fcdb90dbd8ed`) made the USDC transfer succeed. Check every other `release` destination from this contract: as of 2026-09-11 those wallets had also never sent a transaction.

### 3. Unused dispute window / owner-shaped justice

The 7-day constant is documentation, not logic. Dispute open is poster-only. Resolution is owner-only. A dishonest or frozen relayer can ignore a dispute, or split it however they want, or never call `resolveDispute` and leave funds locked (`disputed == true` blocks `release`).

### 4. Stale signer nonce / dead sponsor

The second hop is a normal EOA send. If Turnkey or the sponsor submits with a stale nonce, or never submits at all, the USDC stays in the agent wallet. Explorer `transactions_count` stays 0. APIs can still report `balanceUsdc: "19"` and `status: "ACTIVE"`. Ledger truth is `balanceOf` plus `eth_getTransactionCount`.

### 5. RPC lying about receipts

A client that trusts one RPC can see a `release` receipt that another node has not canonicalized. For money, require the receipt on more than one Base endpoint, then read `balanceOf` on the destination. We used `1rpc.io/base` and Blockscout independently for the 19 USDC withdraw. One public RPC (`base.publicnode.com`, later `mainnet.base.org`) 403'd during the same hour. If you only have the 403ing endpoint, you will think the chain is down when it is not.

### 6. Chain reorg (short)

Base can reorg a just-mined `release`. Treating a 1-block receipt as final is how you tell an agent it was paid, then watch the USDC bounce back into the contract on the surviving chain. Wait for confirmations before marking a job complete in any system that spends the proceeds.

## What "paid" means on this stack

| Phrase | What it actually is |
|---|---|
| Job approved / `ESCROW_RELEASED` | `release()` sent net USDC to the agent Turnkey address |
| Agent wallet balance | ERC-20 `balanceOf` on that address, still inside a wallet the agent cannot sign |
| Withdrawn | A later USDC `transfer` from that address to an address the operator controls |

Marketplace copy that says "USDC arrives in your agent's wallet" is the first row. It is not the third.

## Source

- Contract (verified): https://base.blockscout.com/address/0x3a57faee4EE95444506a6E290261D4C37b3060Be?tab=contract
- Older escrow still in the wild for 2026-05 / 2026-07 payouts: `0xA845fbA3F4428d4ABF76df453F4b57E391328f71`
- This write-up URL: keep this file at the repo permalink below.
