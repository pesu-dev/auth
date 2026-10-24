# Deployment

There are two environments, both hosted on Render:

- **Staging**: https://pesuauth-dev.onrender.com - [Status Page](https://6ns95sgb.status.cron-job.org/)
- **Production**: https://pesuauth.onrender.com - [Status Page](https://xzlk85cp.status.cron-job.org/)

Both deploy workflows only run on `dev`, so always pick `dev` when starting one by hand.

## Staging

Every merge to `dev` is deployed to staging automatically, once CI passes. If newer commits have landed on `dev` in the
meantime, only the newest one is deployed. You can also deploy the latest `dev` by hand.

## Production

Maintainers release to production by hand. A release always deploys the latest commit on `dev`:

1. **Checks.** CI must have passed on that commit, and its version must be newer than the last release.
1. **Approval.** A member of `auth-maintainers` approves the release.
1. **Deploy.** The commit is deployed to production. If the deploy fails, production is rolled back to the commit it
   was running before.
1. **Release.** The Docker image is published to Docker Hub and GHCR, tagged `vX.Y.Z`, `latest` and `prod`, and a
   GitHub Release is created.
1. **Update `main`.** `main` is moved to the released commit, so it always matches production.

If a run fails after the deploy, production is already running the new version. Fix the problem and use **Re-run
failed jobs** to finish the release.

Don't cancel a run while it is deploying: the deploy keeps going on Render without being released or rolled back. If
that happens, roll back from the Render dashboard, or start a new run.
