# Deploy runbook

## Staging deploy

```bash
git pull origin main
python3 -m pytest tests/   # if present
./scripts/deploy.sh staging
```

Wait for the health check at `https://staging.example.com/health` to return `200`.

## Production deploy

**Never deploy on Fridays.** Require two approvals in `#deploys`.

1. Tag release: `git tag vX.Y.Z && git push --tags`
2. Run `./scripts/deploy.sh production`
3. Watch error rate in logs for 15 minutes.

Rollback: `./scripts/deploy.sh production --rollback`

New engineers should complete onboarding in `docs/onboarding.md` before prod access.
