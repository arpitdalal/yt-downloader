# Cross-platform device pairing and secret storage

## Decision

Use a local, per-device cryptographic identity and an accountless server-side trust group. Pair devices through a single-use, high-entropy QR/copy link and a vetted authenticated handshake. Store long-lived secrets behind the operating system credential store, with Tauri Stronghold as the encrypted application vault. Treat a short numeric pairing code as a later feature that requires a PAKE prototype; never pad or hash a short code and use it as a Noise pre-shared key.

Windows must pass the complete host-role flow first. macOS should use the same model. Linux is supportable, but its credential service is not guaranteed to exist or be unlocked, so the app needs an explicit capability check and a passphrase fallback or an actionable unsupported-state screen.

## Recommended model

### Separate the credentials

Each device should have distinct, versioned credentials with distinct jobs:

1. A long-lived Ed25519 device signing key identifies the installation and proves possession. Ed25519 is a specified signature scheme with compact keys and signatures; the private key never leaves local secure storage ([RFC 8032](https://www.rfc-editor.org/rfc/rfc8032.html)).
2. A fresh 32-byte pairing secret authenticates one pairing ceremony. It expires quickly, is accepted once, and is deleted at both endpoints.
3. A rotating refresh token authorizes the device to the hosted rendezvous/relay service. It is bound to the device key rather than usable as an unbound bearer token.
4. Short-lived access tokens authenticate relay connections. They contain only the trust-group id, device id, role/capabilities, audience, and expiry.
5. Any device-to-device transport keys are separate again. Their exact lifecycle belongs to the transport decision, not the pairing bootstrap.

Do not derive all of these from one root secret. Separation permits server-token rotation or device-to-device rekeying without changing the stable device identity.

### Accountless trust group

The first installation creates an opaque random trust-group id and becomes its first active device. The backend stores only group membership and security metadata: device public keys, user-chosen device names, capabilities, membership version, revocation state, and token records. It does not need an email address, password, browser cookies, filesystem paths, or video data.

An active paired device can create an invitation and authorize a new device key. For the initial owner-only product, every active device may invite or revoke another device. This avoids inventing an administrator hierarchy before there is evidence one is needed. A device must not authorize itself merely by knowing a group id.

Device identity is the registered public key, not a mutable device name or a bearer token. A stable device id can be a domain-separated hash of that public key. Every enrollment grant, relay authentication proof, and revocation request must include a protocol version and operation-specific domain separator so a signature cannot be replayed for another purpose.

### Pairing ceremony

Recommended first-release flow:

1. Both installations generate their device identity locally before pairing.
2. An already paired device requests an opaque rendezvous id, locally generates a cryptographically random 32-byte secret, and displays a `yt-downloader` pairing URI as QR plus a copyable full link/code. The hosted service sees the rendezvous id but not the secret.
3. The new device imports that URI. Through the relay, the devices run a vetted Noise handshake that mixes the 32-byte secret into the transcript, such as `Noise_XXpsk3_25519_ChaChaPoly_SHA256`. Noise `XX` exchanges static keys with mutual authentication, and the specification defines `XXpsk3`; it requires PSKs to have 256 bits of entropy ([Noise Protocol Framework, Sections 7 and 9](https://noiseprotocol.org/noise.html)).
4. The handshake transcript binds the rendezvous id, expiry, protocol version, both device public keys, claimed roles/capabilities, and trust-group id. The existing device explicitly confirms the new device before signing an enrollment grant.
5. The server validates the existing device's proof and grant, adds the new public key, increments the membership version, and issues device-bound tokens. The invitation then becomes unusable. Both apps erase the pairing secret and temporary handshake state.

The invitation should expire after a few minutes, permit one successful claim, and be cancelled when the initiating screen closes. Server-side rate limits and generic errors still matter, but possession of the high-entropy secret is the cryptographic authorization.

The QR is a transport for the full secret, not a security protocol. A user without a camera can copy the full pairing link/code. Keep the rendezvous id and secret in the URI fragment where practical so browsers and intermediary HTTP servers do not receive the secret.

### Short manual code

A six- or eight-digit code is low entropy and cannot be substituted for the Noise PSK: Noise explicitly requires a 32-byte PSK with 256 bits of entropy ([Noise security considerations](https://noiseprotocol.org/noise.html#security-considerations)). Hashing a short code does not add entropy.

If a short-code workflow is later required, use an audited password-authenticated key exchange. SPAKE2 is specified to let two parties sharing a password derive a strong shared key without disclosing the password, but its specification requires identities to be bound to the transcript and mandatory key confirmation to avoid unknown-key-share failures ([RFC 9382](https://www.rfc-editor.org/rfc/rfc9382.html)). The rendezvous service must also rate-limit attempts, enforce a short expiry, and invalidate the code after success. Library maturity, crash recovery, simultaneous claims, and UI error behavior need a prototype before committing to this path.

Do not invent a custom exchange from hashes, encrypted public keys, or unauthenticated Diffie-Hellman.

## Local secret storage

### Portable vault plus native wrapping

Use Tauri Stronghold as the application vault. The official plugin supports Windows, Linux, and macOS, requires a password-derived 32-byte key, and exposes Ed25519 key generation/signing procedures ([Tauri Stronghold guide](https://v2.tauri.app/plugin/stronghold/), [Stronghold API](https://v2.tauri.app/reference/javascript/stronghold/)). Store the device private key in a Stronghold vault and perform signing there. Store rotating server credentials in a separate Stronghold record.

Generate a random Stronghold unlock secret on first run and save only that small secret in the native OS credential store. Open Stronghold from Rust, not the webview; expose narrow commands such as `sign_device_challenge`, never raw key or token reads. Tauri blocks potentially dangerous Stronghold commands until capabilities grant them, so the frontend should not receive broad Stronghold permissions ([Tauri Stronghold permissions](https://v2.tauri.app/plugin/stronghold/#permissions)).

This layering gives the app one cross-platform encrypted snapshot format while making a copied application-data directory insufficient to unlock it. It does not protect against malware already running as the same unlocked user; no desktop software vault can make that claim.

Never fall back to plaintext config, Tauri Store, browser local storage, environment variables, logs, or command-line arguments. If secure storage cannot be opened, the device is unpaired/unavailable until the owner repairs or unlocks it.

### Platform behavior

| Platform | Native wrapping store | Required behavior |
| --- | --- | --- |
| Windows | Credential Manager or user-scoped DPAPI. `CryptProtectData` normally limits decryption to the same user on the same computer; `CredWrite`/`CredRead` manage credentials in the user's credential set ([Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata), [Windows Credential APIs](https://learn.microsoft.com/en-us/windows/win32/api/wincred/)). | Mandatory first release gate. Use current-user scope, never machine scope. Verify install, upgrade, uninstall/reinstall, Windows password change/reset, and multiple Windows users. |
| macOS | Keychain Services. Apple documents the keychain as encrypted storage for small secrets and keys; macOS ACLs control which applications can use a protected item ([Apple Keychain Services](https://developer.apple.com/documentation/security/keychain-services/), [macOS keychain ACLs](https://developer.apple.com/documentation/security/access-control-lists)). | Store a local, non-synchronizing application item. Verify signed/notarized upgrades keep access without surprising prompts, and revocation/reset deletes the item. |
| Linux | Freedesktop Secret Service through a maintained Rust adapter. The API stores secrets in a service in the user's login session; collections may be locked and operations may require a user prompt ([Secret Service specification](https://specifications.freedesktop.org/secret-service/latest-single/)). The Rust `keyring` crate exposes macOS, Windows, and D-Bus Secret Service backends ([keyring crate](https://docs.rs/keyring/latest/keyring/)). | At startup, perform a non-destructive create/read/delete capability check. If no D-Bus service exists or it stays locked, offer a user-entered Stronghold passphrase for that session or clearly disable pairing/host availability. Never silently weaken storage. Test GNOME Keyring and KWallet separately. |

Stronghold's cross-platform support does not remove the Linux unlock problem: Stronghold itself requires a password. An embedded constant or a password stored beside the snapshot defeats the intended boundary. A passphrase fallback means the app cannot auto-start as an available host until the owner unlocks it; that is preferable to insecure unattended storage.

## Relay authentication, token rotation, and revocation

All service connections use current TLS 1.3 with ordinary server-certificate validation. TLS provides authenticated, confidential, integrity-protected client/server transport, but application protocols must still define client identity verification ([RFC 9846](https://www.rfc-editor.org/rfc/rfc9846.html)). Do not disable certificate verification or rely on a trust-on-first-use server certificate.

Bind each server token to the device public key. DPoP is the established HTTP pattern: a request-specific signed proof demonstrates possession of a private key, and the authorization server binds access and refresh tokens to that key ([RFC 9449](https://www.rfc-editor.org/rfc/rfc9449.html)). If the backend adopts OAuth-shaped token endpoints, implement DPoP directly. If it does not, retain the same properties in the relay protocol and have the security design reviewed rather than calling an ad-hoc signature header "DPoP."

The service should issue short-lived, audience-restricted access tokens and either sender-constrain refresh tokens or rotate them on every use. OAuth Security Best Current Practice requires one of those replay defenses for public clients and explains refresh-token-family reuse detection ([RFC 9700, Sections 2.2.2 and 4.14](https://www.rfc-editor.org/rfc/rfc9700.html)). Use both where practical: proof binding prevents use without the device key; rotation detects copied-token reuse.

Revocation is server state, not successful deletion from a possibly compromised device:

1. Any remaining active device can revoke a target device.
2. The server marks the device key revoked, invalidates its refresh-token family and active relay sessions, and increments the trust group's monotonic membership version.
3. Before a download host advertises availability or accepts a new command after reconnect, it fetches and applies the latest membership version. This is feasible because offline hosts already reject work rather than queueing it.
4. The host deletes pairwise/session material for the revoked device. Deletion is hygiene; the server and host allowlists enforce the revocation.
5. A removed device must complete a new in-person pairing ceremony to return.

If every paired device is lost or all secure storage becomes unrecoverable, there is deliberately no server-side identity recovery. The owner resets local pairing state on a device they still control and creates a new trust group, invalidating the old group. Recovery based only on an email, support request, device name, or short code would quietly introduce an account-recovery trust model. An optional printable high-entropy recovery key could be a separate future decision.

## Threat boundaries

This design addresses network attackers, relay database disclosure of tokens, copied app-data directories, replayed invitations, and stale/revoked devices. It keeps browser cookies and download files outside the hosted service.

It does not defend a device after malware controls the same unlocked OS user, an attacker can operate an already unlocked app, or the owner approves the wrong device during pairing. Device display names are untrusted metadata. The product should show platform, approximate creation time, and a short public-key fingerprint at confirmation and in device settings.

The relay can still observe timing, IP addresses, group/device identifiers, and ciphertext sizes unless later transport work deliberately minimizes that metadata. Pairing authentication does not by itself make relay commands end-to-end confidential; that is a separate transport requirement.

## Prototypes required before implementation planning

1. **Windows secure-storage gate:** In a signed Windows build, prove Credential Manager/DPAPI wrapping plus Stronghold create, unlock, Ed25519 sign, token update, revoke, app upgrade, uninstall/reinstall, password change/reset, and two-Windows-user behavior. Windows host support is mandatory, so failure here changes the storage design.
2. **macOS and Linux storage matrix:** Repeat lifecycle tests for signed/notarized macOS builds, GNOME Keyring, and KWallet. Exercise locked login keyrings, missing Secret Service, cancellation of unlock prompts, and passphrase fallback. Confirm secrets never cross the Tauri webview IPC boundary.
3. **High-entropy pairing handshake:** Build a throwaway two-client relay harness using a maintained Noise implementation. Verify transcript binding, invitation expiry, single-use races, cancellation, replay rejection, reconnect after each handshake message, and deletion of temporary state. Have the exact pattern and payload binding reviewed before production use.
4. **Short-code PAKE:** Only if product requirements reject QR/full-copy-code pairing, compare maintained SPAKE2 implementations and prototype two honest clients plus a malicious relay, online guesses, simultaneous claimers, mandatory key confirmation, and crash recovery.
5. **Proof-bound relay session:** Prove DPoP-bound access/refresh tokens through the intended HTTP/WebSocket stack, including refresh rotation, reuse detection, relay reconnect, clock skew, nonce handling, immediate session termination after revocation, and proxy/CDN compatibility.
6. **Recovery/reset UX:** Prototype the destructive "reset all pairing" path and make its consequence explicit: old devices and trust group become inaccessible, while downloaded files remain untouched.

## Decisions made possible by this research

- Pairing can remain accountless; an existing paired device is the trust anchor.
- First release should use a 32-byte single-use QR/copy-link secret with an authenticated Noise handshake.
- A short numeric code is not part of the first release unless the PAKE prototype succeeds.
- Device identity is a local signing key; mutable names and server bearer tokens are not identity.
- Tauri Stronghold holds application secrets, unlocked by a random secret wrapped by the native OS credential store.
- Windows secure-storage and host-role lifecycle tests are mandatory release gates.
- Linux support must detect Secret Service availability and must fail closed or require a session passphrase.
- Revocation is enforced by server membership state plus host allowlists; local deletion alone is insufficient.
- Losing every paired device has no cloud recovery in this accountless model; recovery is a full trust-group reset.
