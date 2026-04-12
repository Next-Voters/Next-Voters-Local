---
description: Create commits and push changes to the repository
---

# Commit Message Convention

Use one of these prefixes in the commit message:

- `feat:` — new feature
- `fix:` — bug fix
- `chore:` — maintenance task
- `docs:` — documentation-only change

# Rules

- Write clear, concise commit messages describing the change.
- Keep each commit focused on a single logical change.
- Never push to the remote without human approval.

# Releasing to Docker Hub

When the user wants to release / deploy changes to the Docker container:

1. Check the latest existing tag: `git tag --sort=-v:refname | head -1`
2. Determine the next version using semver based on the changes since the last tag:
   - **Major** (`vX.0.0`): breaking changes (e.g. removed features, changed APIs, restructured pipeline)
   - **Minor** (`vX.Y.0`): new features, new integrations, new pipeline nodes
   - **Patch** (`vX.Y.Z`): bug fixes, dependency updates, config tweaks, doc changes
3. If no tags exist yet, start at `v1.0.0`.
4. Review the commits since the last tag with `git log <last_tag>..HEAD --oneline` to inform the version bump.
5. Create and push the tag:
   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
6. This triggers the GitHub Actions workflow at `.github/workflows/push-container-to-azure.yml` which builds and pushes the image to Docker Hub.