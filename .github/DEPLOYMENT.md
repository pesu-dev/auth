# Render deployments

Staging and production are Git-backed Docker web services connected through Render's GitHub integration to
`pesu-dev/auth`. Render builds the existing `Dockerfile` for each selected commit. GitHub Actions controls deployment
timing; publishing a registry image does not deploy either service.

| Setting               | Staging                                    | Production      |
| --------------------- | ------------------------------------------ | --------------- |
| Linked branch         | `dev`                                      | `main`          |
| Runtime               | Docker                                     | Docker          |
| Dockerfile path       | `./Dockerfile`                             | `./Dockerfile`  |
| Docker build context  | Repository root                            | Repository root |
| Auto-Deploy           | Off                                        | Off             |
| Health check path     | `/health`                                  | `/health`       |
| Pull Request Previews | Automatic, or Manual with `render-preview` | Disabled        |

Keep each service's existing region, compute plan, environment variables, and custom domains. The application reads
Render's `PORT` environment variable. Use the Dockerfile's default command.

## Workflow configuration

The GitHub environments `staging` and `production` each provide the `RENDER_SERVICE_ID` variable and
`RENDER_API_KEY` secret. The
`promote-gate` environment retains its required reviewers. The release GitHub App retains its existing permissions
and credentials for advancing `main` and creating releases. No deploy-hook secret is required.

## Staging and previews

A successful push CI run on `dev` triggers `deploy_staging.yml`. It skips a validated commit if `dev` has advanced,
publishes the commit's multi-architecture GHCR image, deploys the exact SHA through Render's API, waits until the deploy
is live, and then updates the registry's `staging` tag. Manual staging runs must target `dev`.

Render manages PR previews independently of the base service's Auto-Deploy setting. Automatic previews apply to PRs
targeting `dev`; Manual previews require the `render-preview` label or `[render preview]` in the PR title. New commits
update the preview, and closing or merging the PR deletes it.

Previews inherit staging configuration, including environment variables. Review that configuration before enabling
previews for contributor PRs; do not provide production credentials to preview builds. Paid previews are billed at
the base service's rate, prorated per second. Free previews consume shared Free instance hours while running, along
with build and bandwidth allowances.

## Production promotion

`deploy_prod.yml` resolves one `dev` commit and project version for the whole run. After the `promote-gate` approval,
the release App fast-forwards `main` to that selected SHA, following the original branch-based promotion order.
The workflow rejects a conflicting version tag or a promotion that cannot fast-forward. It publishes the selected commit's multi-architecture GHCR image and deploys the selected SHA
to staging and waits for it to become live before deploying that same SHA to production. Both deployments use the
existing shared Render action. Later changes to `dev` do not change this run's selected commit.

After production is live, the workflow publishes version/latest/prod image tags and the GitHub release for that SHA.
The production workflow publishes its commit image before deployment so release tagging does not depend on another
staging run having finished.

Before advancing `main`, the workflow records its most recent reachable version-tagged commit as the rollback SHA,
falling back to the previous `main` SHA if no version tag exists. If production deployment fails, the shared Render
action rebuilds and redeploys that rollback SHA and waits for it to become live. This uses the same deployment tooling;
there is no separate Render API helper or retained-artifact rollback. The workflow remains failed even if rollback
succeeds. Rollback does not rewind `main` or create a release. If there is no prior version tag, or tags do not represent
successful releases, a maintainer must verify the rollback target before retrying a failed promotion. A failed staging
deployment prevents production deployment and leaves `main` at the selected commit.

Git-backed staging and production build separately. Their source commit matches, but their container artifacts need
not be byte-for-byte identical, especially when upstream base-image tags change.

## Migration from image-backed services

1. Prepare the service settings above and confirm access to `pesu-dev/auth` through Render's GitHub integration.
   Check whether each existing service permits changing its source. If a replacement is necessary, plan its URL/domain
   and monitoring cutover before deleting the original service.
1. Coordinate the service-source switch with the workflow PR. During the cutover, prevent old image-based deployment
   workflows from running; their `image_url` requests do not match the new Git-backed services. A maintainer can disable
   the deployment workflows temporarily, then re-enable them after both sides are configured.
1. Configure staging with `dev` and production with `main`, Docker runtime, `/health`, and Auto-Deploy Off. If new
   services were created, update the respective environment's `RENDER_SERVICE_ID`. Keep credentials out of PRs and logs.
1. Confirm production is running the intended stable version and its version tag identifies that commit.
   Confirm health, environment variables, and domains.
1. Enable staging PR previews after reviewing inherited environment variables. Verify a contributor PR gets a preview
   and closing it removes the preview.
1. Once the workflow changes are merged and deployment workflows re-enabled, run staging for the current `dev` SHA,
   confirm its version, and perform a production promotion through the approval gate. Verify the deployed commit,
   image tags, release, and `main` all agree.
   For the first promotion, select `dev` in GitHub Actions' **Run workflow** branch selector: `main` still contains
   the old image-based workflow until that promotion advances it. Continue selecting `dev` if the first promotion
   stops before updating `main`.

References: [Docker on Render](https://render.com/docs/docker),
[deployment controls](https://render.com/docs/deploys),
[service previews](https://render.com/docs/service-previews),
[Free usage limits](https://render.com/docs/free), and [rollbacks](https://render.com/docs/rollbacks).
