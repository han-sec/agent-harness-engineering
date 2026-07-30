# Team FAQ — cross-doc scenarios

Answers that span multiple policies. Always cite the source doc when sharing externally.

## I'm a new engineer. What must I read before touching prod?

1. [onboarding.md](onboarding.md) — week 1 checklist
2. [api-auth.md](api-auth.md) — before any API call
3. [deploy-runbook.md](deploy-runbook.md) — read staging section first; **no prod until onboarding complete**

Prod access requires buddy sign-off and completed staging deploy practice.

## Customer wants a refund — what do I check?

See [refunds-policy.md](refunds-policy.md):

- Within **14 days** of purchase?
- Usage under **10%** of quota?
- If API-related billing, also check [api-auth.md](api-auth.md) support contacts

Approve or deny within **2 business days**.

## I'm releasing to production tonight. Allowed?

**No.** [deploy-runbook.md](deploy-runbook.md) forbids Friday prod deploys.

Required: two approvals in `#deploys`, tag release, 15-minute error-rate watch, rollback command ready.

## How do I call internal APIs from a script?

[api-auth.md](api-auth.md):

```
Authorization: Bearer YOUR_API_KEY
```

Staging limit: 100 req/min. Production: 1000 req/min. Rotate keys every **90 days**.

## Where is everything documented?

See [index.md](index.md) for the full map.
