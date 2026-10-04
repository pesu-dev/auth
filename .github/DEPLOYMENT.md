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
`RENDER_API_KEY` secret. These credentials are also used by the deployment checks and rollback helper. The
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
it verifies that staging is live at that exact commit and captures production's current live deployment for rollback.
Production must already have a successful live deployment before using this workflow.

The release App fast-forwards `main` to the selected SHA before production deployment, following the original
branch-based promotion order. The workflow rejects a conflicting version tag or a promotion that cannot fast-forward.
It deploys that same SHA, waits for Render to report it live, and then publishes version/latest/prod image tags and
the GitHub release for that SHA. Later changes to `dev` do not change this run's selected commit.

If production deployment fails, the workflow requests a rollback to the captured Render deployment and waits for it
to become live. The workflow remains failed even if rollback succeeds. A rollback restores the runtime; it does not
rewind `main` or create a release. A maintainer must resolve the failed promotion before the next release. Render can
only roll back to artifacts it still retains, so rollback can also fail and requires manual investigation.

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
1. Establish a successful production deployment of the intended stable `main` commit so the first promotion has a
   rollback target. Confirm health, version, environment variables, and domains.
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
