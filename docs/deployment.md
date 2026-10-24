# Deployment

We maintain two deployment environments, both Docker services on Render that build the image from the commit they are
given:

- **Staging**: https://pesuauth-dev.onrender.com - [Status Page](https://6ns95sgb.status.cron-job.org/)
- **Production**: https://pesuauth.onrender.com - [Status Page](https://xzlk85cp.status.cron-job.org/)

Both workflows can only be started on `dev`: always select `dev` in the Run workflow branch selector, since the
deployment environments allow no other branch.

## Staging

`deploy_staging.yml` runs after CI Checks passes on a push to `dev`, which is every merged pull request, and deploys
that commit. If `dev` has already moved past it, the deploy is skipped, and the newer commit's own CI run deploys that
one. Started by hand, it deploys the latest commit on `dev`.

Staging builds and publishes no image: Docker Hub and GHCR images come only from production releases.

## Production

`deploy_prod.yml` is started by hand and releases the latest commit on `dev`:

1. Before anything changes, it stops unless CI Checks passed on that commit, its version is newer than the latest
   release, and the Docker Hub credentials are configured.
1. It waits for approval on the `promote-gate` environment, from a member of `auth-maintainers`.
1. It records the commit currently live on production, to roll back to.
1. It builds the commit's image for `linux/amd64` and `linux/arm64` and pushes it to GHCR, tagged with the commit SHA.
1. It deploys the commit to production. If the deploy fails, it redeploys the recorded commit, and the run is still
   marked failed.
1. It tags the image `vX.Y.Z`, `latest` and `prod` on GHCR and Docker Hub, and creates the git tag and GitHub Release.
1. Only then does it fast-forward `main` to the released commit.

If the release or the fast-forward of `main` fails, production already runs the new commit: fix the cause and use
**Re-run failed jobs**. Cancelling the run while it waits on the deploy does not stop the Render deploy or roll it back,
so production may switch to the new commit with nothing released: roll back from the Render dashboard, or start a new
run to release it.
