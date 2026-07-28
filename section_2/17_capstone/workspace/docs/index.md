# Internal documentation index

Start here. All paths are relative to `workspace/docs/`.

## By topic

| Topic | Doc | Use when |
|-------|-----|----------|
| New hire checklist | [onboarding.md](onboarding.md) | First 30 days, required reading |
| Refunds & billing | [refunds-policy.md](refunds-policy.md) | Customer refund eligibility |
| Deployments | [deploy-runbook.md](deploy-runbook.md) | Staging/prod releases, rollback |
| API access | [api-auth.md](api-auth.md) | Tokens, rate limits, key rotation |
| Common scenarios | [team-faq.md](team-faq.md) | Cross-doc answers, “what do I need?” |

## Quick facts

- Refund window: **14 days** (see refunds-policy.md)
- API auth: **Bearer token** in Authorization header (see api-auth.md)
- Prod deploys: **never on Fridays**, two approvals required (see deploy-runbook.md)
- New hires: read **api-auth.md** before any internal API call (see onboarding.md)

## How to ask this assistant

Good questions name a topic or outcome:

- “Summarize onboarding for week 1”
- “Compare refund rules vs API billing disputes”
- “I'm deploying to production — what approvals and docs apply?”
- “Give me an overview of all internal docs”

Type `help` in the chat for capabilities (handled by Python, no LLM).
