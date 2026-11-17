# PLUTO vProctor — Zoho Catalyst Cost Control Guide

> Updated: 2026-11-17

---

## 1. What You Are Allowed to Use (Free Tier)

| Resource | Free Allowance | Verified? | Notes |
|---|---|---|---|
| AppSail — compute | 900 GB-minutes/month | ✅ Documented | 2048 MB × 450 minutes = 900 GB-min |
| Web Client Hosting — bandwidth | 1 GB/month | ✅ Documented | Static frontend assets |
| Web Client Hosting — requests | 1M requests/month | ✅ Documented | — |
| Catalyst Data Store — reads | 1M reads/month | ✅ Documented | Not currently used |
| Catalyst Data Store — writes | 500K writes/month | ✅ Documented | Not currently used |
| Functions invocations | 500K/month | ✅ Documented | Not currently used |
| **Zoho Store wallet credit** | Unknown | ❌ UNVERIFIED | Do NOT assume this applies to Catalyst billing without checking |

> [!WARNING]
> The Zoho Store wallet balance shown in your account may be **store credit**, not Catalyst billing credit. Verify this in the **Catalyst Console → Billing** section before relying on it.

---

## 2. Free Tier Exhaustion Scenarios

| Scenario | Daily Use | Monthly Compute | Fits Free Tier? |
|---|---|---|---|
| Demos only (8 hrs/day, idle otherwise) | 8 hrs × 60 min × 2 GB = 960 GB-min | 960 × 30 = 28,800 GB-min | ❌ Over limit |
| **On-demand only (scale-to-zero)** | Active ~30 min/day | 30 × 2 GB × 30 days = 1,800 GB-min | ❌ Over limit |
| **Minimal demo days (5 min active/day)** | 5 × 2 × 30 = 300 GB-min | 300 GB-min | ✅ Within limit |
| AppSail min-instances=0, invoked only during demos | ~10 demos × 10 min | 200 GB-min | ✅ Within limit |

> [!TIP]
> Keep AppSail at **min-instances=0**. The backend scales to zero when idle. The free 900 GB-min/month is enough for approximately 7.5 hours of active backend runtime at 2048 MB.

---

## 3. Sandbox vs Pay-As-You-Go

| Setting | Sandbox | Pay-As-You-Go |
|---|---|---|
| Billing risk | None — hard quota stop | Charges accumulate beyond free tier |
| Resource limits | Hard cap per tier | Soft cap with billing |
| Best for | Development and demos | Production traffic |
| **Recommendation** | ✅ Use Sandbox for college demo | — |

> [!IMPORTANT]
> Stay in **Sandbox** mode for the college demo. If Catalyst prompts you to upgrade to Pay-As-You-Go, **decline** unless you have confirmed billing credit available.

---

## 4. Budget Alerts Setup

Even in Sandbox, set up budget alerts so you are notified before approaching limits:

1. Open **Catalyst Console → Billing → Budget Alerts**
2. Set an alert at **70% of the free tier compute limit** (630 GB-minutes)
3. Set a second alert at **90%** (810 GB-minutes)
4. Email notifications go to your registered Zoho account

> [!NOTE]
> Catalyst Sandbox does **not** have an auto-shutoff feature. Budget alerts are notification-only. If you exceed the quota in Sandbox, services stop until the next billing cycle. No charge.

---

## 5. What Must NOT Be Activated

| Resource | Risk | Action |
|---|---|---|
| Pay-As-You-Go upgrade | Unexpected charges | Do NOT upgrade |
| AppSail min-instances=1 (always-on) | 730 hr × 2 GB = 1,460 GB-min/month — over free tier | Keep at min-instances=0 |
| External paid database (RDS, Supabase) | Real money | Do NOT provision |
| Catalyst QuickML (hosted inference) | Credit consumption unknown | Do NOT activate without verifying eligibility |
| Additional Zoho paid services | Real money | Do NOT activate |
| Payment method attachment | Enables real billing | Do NOT attach without approval |

---

## 6. Actual Cost If Free Tier Is Exceeded (Pay-As-You-Go Reference)

If you ever move to Pay-As-You-Go (not recommended for demo):

| Resource | Rate (approximate) |
|---|---|
| AppSail compute (beyond free tier) | \$0.00002/GB-second ≈ \$0.07/GB-hour |
| Web Client Hosting (beyond 1 GB bandwidth) | \$0.08/GB |
| Catalyst Data Store (beyond free tier) | \$0.0004/1K reads |
| Minimum monthly project fee | \$5.00/month |

For the college demo use case with on-demand scaling, real costs beyond the minimum fee would be **under \$5/month** if the backend runs fewer than 100 hours per month.

---

## 7. Zero-Cost Operating Checklist

- [ ] Catalyst plan: Sandbox (not Pay-As-You-Go)
- [ ] No payment method attached
- [ ] AppSail min-instances=0
- [ ] Budget alert at 70% free tier
- [ ] Web Client Hosting: static assets only (no CDN overage)
- [ ] No QuickML, no Catalyst Data Store writes beyond demo data
- [ ] Backend stopped manually after each demo session when possible
