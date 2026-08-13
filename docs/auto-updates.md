# Automatic updates

The desktop app checks GitHub Releases once at startup. When a newer signed release exists, it shows a dismissible update prompt. Dismissal lasts for the current app session; the update is offered again after the next launch.

## Security model

Tauri updater signatures are separate from platform code signing.

- The updater public key is committed in `src-tauri/tauri.conf.json`. It verifies downloaded updates and is safe to publish.
- The updater private key and password must only exist in secure maintainer storage and the encrypted GitHub Actions secrets `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`.
- Never add the private key, password, or a `.env` containing either value to this repository.
- Back up the private key and password securely. Losing them prevents installed copies from trusting future updates.

Generate a replacement keypair only before shipping the first updater-enabled release:

```bash
pnpm tauri signer generate -w ~/.tauri/yt-downloader-updater.key
```

The generated `.key.pub` content belongs in `plugins.updater.pubkey`. Add the private key and password through GitHub repository settings or `gh secret set`; do not paste them into workflow YAML.

## Release pipeline

`tauri-release.yml` supplies the private signing values to Tauri from GitHub Actions secrets. Each platform build produces an updater artifact and signature:

- macOS arm64: `.app.tar.gz` and `.app.tar.gz.sig`
- Windows x64: NSIS `.exe` and `.exe.sig`
- Linux x64: `.AppImage` and `.AppImage.sig`

The publish job refuses to continue unless all three signed artifacts exist. It generates `latest.json` with immutable, tag-specific download URLs and publishes it with the release assets. Installed apps read:

```text
https://github.com/arpitdalal/yt-downloader/releases/latest/download/latest.json
```

The updater applies directly to macOS, Windows, and AppImage installations. Linux `.deb` and `.rpm` installations should continue to update through their package installation flow.

The in-app feed is stable-only. Release validation rejects prerelease versions; supporting beta releases requires a separate updater endpoint and opt-in channel.

## First release limitation

Versions shipped before the updater plugin was added cannot discover updates. Users must manually install the first updater-enabled release. Updates after that release can use the in-app prompt.
