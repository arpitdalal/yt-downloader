# Release versioning

Release tag, app bundle version, and website downloads must stay aligned.

Canonical version files:

- `package.json`
- `src-tauri/tauri.conf.json`
- `src-tauri/Cargo.toml`
- `src-tauri/linux/com.ytdownloader.app.metainfo.xml`

What broke before:

- Git tag moved to `v2.2.0`.
- Tauri/package metadata still said `2.0.0`.
- Release workflow built `2.0.0`-named binaries, uploaded them to release `v2.2.0`.
- Website correctly rendered release `v2.2.0`, but asset filenames still showed `2.0.0`.

Guardrail:

- `pnpm release:check-version` validates all version files match.
- In tag builds, it also validates `RELEASE_TAG === v<version>`.
- `tauri-release.yml` runs this before any platform build uploads artifacts.
- `pnpm release:check-pushed-tags` reads refs from Git's `pre-push` hook and blocks local pushes of `v*` tags that do not match the checked-out release version.
- `lefthook.yml` runs that local guard automatically on every push.

Release steps:

1. Bump all canonical version files.
2. Run `pnpm release:check-version`.
3. Commit and merge.
4. Create a new tag matching the version, eg `v2.2.2`.
5. Let release workflow build and upload assets.
6. Let website deploy render that release.

Important:

- Re-running GitHub Pages alone cannot fix wrong asset filenames.
- Pages only renders whatever asset names already exist on the GitHub release.
- If assets were built with the wrong app version, rebuild and publish corrected assets under a corrected release.
