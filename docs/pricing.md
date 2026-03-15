# Pricing Strategy

All prices in AUD. Payments via Stripe.

## Credit System

| Action | Credits | Our cost (USD) |
|--------|---------|----------------|
| CV generation | 1 credit | ~$0.25 |
| CV refinement | 0.5 credit | ~$0.05 |

## Alpha — First 100 Users (Founders Cohort)

| | Details |
|--|--------|
| Price | **$9.99 AUD** |
| Credits | **15** |
| Per credit | $0.67 |
| Stripe product | `quillcv_alpha_15` |

- One-time purchase, no subscription
- Best per-credit value across all packs (founders reward)
- Goal: validate demand, collect feedback, fund initial compliance

## Credit Packs (Post-Alpha)

Available from day one alongside alpha. These are the standard pricing tiers.

| Pack | Price (AUD) | Credits | Per credit | Stripe product |
|------|-------------|---------|------------|----------------|
| Starter | $15 | 15 | $1.00 | `quillcv_starter_15` |
| Standard | $29 | 35 | $0.83 | `quillcv_standard_35` |
| Pro | $49 | 65 | $0.75 | `quillcv_pro_65` |

- One-time purchases, no expiry on credits
- Volume discount ladder (Starter → Pro)
- All packs more expensive per-credit than alpha (founders genuinely got a deal)

## Future: Subscriptions (3-6 months post-launch)

Design based on real usage data from alpha + credit pack purchases.

| Tier | Price (AUD/mo) | Monthly credits | Target |
|------|----------------|-----------------|--------|
| Personal | $19/mo | 25 | Active job seekers |
| Professional | $39/mo | 60 | Career changers, frequent users |
| Team/Business | TBD | TBD | Recruiters, career coaches |

- Unused credits roll over (1 month max)
- Top-up packs available for subscribers at Standard pricing
- Implement only after usage patterns are clear

## Stripe Implementation

### Products to create

```
quillcv_alpha_15      — Alpha Pack (15 credits, $9.99 AUD) — one-time
quillcv_starter_15    — Starter Pack (15 credits, $15 AUD) — one-time
quillcv_standard_35   — Standard Pack (35 credits, $29 AUD) — one-time
quillcv_pro_65        — Pro Pack (65 credits, $49 AUD) — one-time
```

### Checkout flow

1. User selects pack → Stripe Checkout session
2. Stripe webhook `checkout.session.completed` → credit user account
3. Credits stored in DB, decremented on generation/refinement
4. Low credit warning at 5 remaining
5. Zero credits → prompt to purchase pack

### Webhook events to handle

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Add credits to user account |
| `payment_intent.payment_failed` | Log, notify user |
| `charge.refunded` | Deduct credits (if unused) or flag account |

## Unit Economics

### Margin per pack

| Pack | Revenue (USD~) | Max cost (all gens) | Gross margin |
|------|---------------|---------------------|-------------|
| Alpha (15) | ~$6.40 | $3.75 | ~41% |
| Starter (15) | ~$9.60 | $3.75 | ~61% |
| Standard (35) | ~$18.50 | $8.75 | ~53% |
| Pro (65) | ~$31.30 | $16.25 | ~48% |

### Break-even for infrastructure

- Estimated hosting (Digital Ocean): ~$40/mo
- At alpha margin (~$2.65/pack): ~16 packs/month to cover infra
- At standard margin (~$9.75/pack): ~4 packs/month to cover infra

### Compliance budget (funded by margins)

| Requirement | Estimated cost | Priority |
|-------------|---------------|----------|
| GDPR (EU/UK/AU/NZ) | $2-5K | P0 — launch blocker |
| Privacy policy + ToS (multi-jurisdiction) | $3-8K | P0 — launch blocker |
| PCI DSS | Handled by Stripe | N/A |
| SOC 2 Type I | $10-20K | P1 — post-alpha |
| APPI (Japan) | $2-3K | P2 — market expansion |
| LGPD (Brazil) | $2-3K | P2 — market expansion |

## Naming Candidates

Top picks (domain not yet purchased — verify availability):

| Name         | Domain          | Notes                          |
|--------------|-----------------|--------------------------------|
| tailor.cv    | `tailor.cv`     | Top pick — .cv TLD, perfect fit|
| sharp.cv     | `sharp.cv`      | Short, punchy                  |
| craft.cv     | `craft.cv`      | Clean, professional            |
| CVForge      | `cvforge.com`   | No active site found           |
| Resumatch    | `resumatch.com` | No active site found           |

## Competitors

| Competitor   | Free tier       | Paid          |
|-------------|-----------------|---------------|
| Kickresume  | Yes (no AI)     | $8-24/mo      |
| Rezi        | Limited          | $29/mo        |
| Novoresume  | Yes              | $20/mo        |
| Teal        | Yes (limited)    | $13/week      |
| Resume.io   | 1 CV free        | ~$17/mo       |
