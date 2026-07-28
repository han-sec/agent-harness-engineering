**Answer**
To gain production access and perform a deployment, you must complete specific onboarding requirements, practice in staging, and follow strict approval protocols.

**Details**
*   **Onboarding & Training:**
    *   Complete the onboarding checklist in `docs/onboarding.md`.
    *   Read `docs/api-auth.md` before making any internal API calls.
    *   Complete a staging deployment practice as outlined in `docs/deploy-runbook.md` (note: you are never allowed to deploy to production on your first day).
*   **Access Requirements:**
    *   You must obtain a buddy sign-off and complete the staging deployment practice before production access is granted.
*   **Deployment Rules & Process:**
    *   **Restrictions:** Production deployments are strictly forbidden on Fridays.
    *   **Approvals:** You must obtain two approvals in the `#deploys` channel.
    *   **Execution:** Tag the release using `git tag vX.Y.Z && git push --tags` and run `./scripts/deploy.sh production`.
    *   **Safety:** Have the rollback command (`./scripts/deploy.sh production --rollback`) ready during the deployment.
    *   **Post-Deployment:** Monitor the error rate in the logs for 15 minutes after a production deploy.

**Sources**
docs/onboarding.md
docs/api-auth.md
docs/deploy-runbook.md
docs/team-faq.md