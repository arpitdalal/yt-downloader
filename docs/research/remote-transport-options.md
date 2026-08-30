# Cross-network transport options for remote downloads

Research date: 2026-08-30

Question: how should a requesting device reach a download host behind NAT without sending video bytes, browser cookies, or filesystem contents through the hosted service?

## Recommendation

Use a **hosted control relay over outbound secure WebSocket connections**, with both desktop apps connecting outward to the same service. Relay only small, end-to-end-encrypted command/status envelopes. The download host fetches video directly from the video provider, reads its own cookies locally, and resolves the configured destination locally. The service routes opaque envelopes and presence only; it never receives video bytes, cookies, paths, or file contents.

This is the best default. It gives the product one install-and-pair flow on Windows, macOS, and Linux. NAT/firewall behavior is predictable, host presence is immediate, and the hosted service stays small. WebSocket is a full-duplex protocol over one TCP connection. Its standard explicitly covers randomized reconnect delay and increasing backoff after abnormal closure ([RFC 6455](https://www.rfc-editor.org/rfc/rfc6455.html#section-1.1), [RFC 6455 §7.2.3](https://www.rfc-editor.org/rfc/rfc6455.html#section-7.2.3)).

Do **not** make WebRTC the first transport. It needs a separate signaling service and ICE server configuration, and reliable reachability still requires TURN fallback ([WebRTC peer-connection guide](https://webrtc.org/getting-started/peer-connections)). That complexity buys little when the peer traffic is only commands and progress, not the downloaded media.

Do **not** require a user-managed overlay network. Tailscale can be an opt-in expert path, but requiring a second app, account, tailnet, policy, and service listener makes it unsuitable for the default consumer flow. Tailscale itself notes that it only supplies connectivity. The destination still needs a separately running service ([connect-to-devices documentation](https://tailscale.com/docs/how-to/connect-to-devices)).

## Non-negotiable boundary

`wss://` protects each device-to-service hop; it does not keep plaintext from the service endpoint. Therefore payload encryption must be end-to-end between paired devices, above WebSocket. The relay may necessarily observe account/device routing identifiers, source IPs, connection times, and envelope sizes. It should not receive plaintext URLs, download options, progress details, filenames, or paths.

The protocol should use authenticated device identities, per-pair keys, authenticated encryption, replay protection, explicit revocation, and versioned envelopes. Choosing the exact key agreement and envelope construction is a separate security decision; it should use a reviewed protocol/library rather than custom cryptography.

## Comparison

| Criterion | Outbound persistent relay | WebRTC direct + TURN fallback | User-managed overlay (Tailscale) |
|---|---|---|---|
| NAT/firewall reachability | Predictable: both apps initiate normal outbound connections to one public service. | ICE tries candidate paths; a separate signaling channel exchanges candidates, and TURN is required when direct paths fail. | Tailscale starts relayed, attempts direct UDP, then retains peer/DERP relay fallback when direct connectivity is unavailable ([connection types](https://tailscale.com/docs/reference/connection-types)). |
| Windows/macOS/Linux | WebSocket protocol is portable; this app can own one Rust-side implementation across its existing targets. | The standards are portable, but native library/bundling risk remains. `libdatachannel` claims GNU/Linux, macOS, and Windows support ([project README](https://github.com/paullouisageneau/libdatachannel)); Rust integration and packaged binaries still need proof. | Official clients/install paths exist for Linux, macOS, and Windows ([install documentation](https://tailscale.com/docs/install)); current Windows client requires Windows 10 or Server 2016+ ([Windows install documentation](https://tailscale.com/docs/install/windows)). |
| Recovery | App-owned. Reconnect with jitter/backoff, reauthenticate, publish presence, and reconcile acknowledgements. WebSocket alone has no durable resume or exactly-once delivery. | ICE can re-establish paths, but signaling, application session recovery, acknowledgements, and deduplication remain app-owned. The W3C API exposes connection/ICE state, while a closed data transport closes its data channel ([WebRTC Recommendation](https://www.w3.org/TR/webrtc/)). | Tailscale monitors health, migrates connections, and implements failover ([control/data planes](https://tailscale.com/docs/concepts/control-data-planes)); the application still owns command acknowledgements and reconnect behavior. |
| Privacy/security boundary | Best fit only with application E2EE. Relay sees routing/traffic metadata but opaque payloads. No media, cookies, or filesystem data enter the channel. | Data channels are DTLS-protected; all WebRTC data channels must be secured by DTLS ([RFC 8827 §5.5](https://www.rfc-editor.org/rfc/rfc8827.html#section-5.5)). TURN relays encrypted peer traffic, but signaling metadata remains service-visible unless separately protected. | WireGuard encrypts device traffic end to end; DERP forwards already-encrypted packets and cannot decrypt them ([Tailscale encryption](https://tailscale.com/docs/concepts/tailscale-encryption)). Its coordination service still records device metadata including IPs, client versions, public keys, location, and OS ([control/data planes](https://tailscale.com/docs/concepts/control-data-planes)). |
| Hosted components | Relay/presence endpoint, authentication, device registry, revocation, and minimal connection state. No media relay. | Signaling/auth/device registry plus STUN and a production TURN fleet. Coturn exposes UDP/TCP/TLS listeners and a broad relay port range, illustrating the extra network operations ([coturn README](https://github.com/coturn/coturn)). | No project-operated NAT traversal or relay if Tailscale SaaS is accepted. App must expose and secure a local service on the tailnet. |
| Product UX | One app, one pairing flow; no router changes or extra network account. | Can be invisible to users, but failure modes and time-to-connect are more complex. | Highest setup burden and support surface; tailnet policy mistakes can expose or block the app service. |
| Likely operating cost | Low because only tiny control messages traverse the service. | Signaling is cheap; TURN egress is also small for this control-only workload, but fixed operations and abuse protection cost more than bandwidth. | $0 project infrastructure for users eligible for Tailscale Personal; current Personal pricing is free for up to six users with unlimited user devices ([pricing](https://tailscale.com/pricing), [free-plan documentation](https://tailscale.com/docs/reference/free-plans-discounts)). This is a third-party dependency and eligibility/terms can change. |

## Reliability contract for the recommended relay

The service should report a host as available only while it has a live authenticated connection, with a short grace/TTL for transient loss. Because the product explicitly rejects cloud queuing while the host is offline, job submission should fail promptly when presence is absent.

Every message should carry a pair-scoped sequence or unique command ID. The requester retains an unacknowledged command locally and may resend after reconnect; the host durably records enough recent IDs to deduplicate. Status updates should carry a monotonic revision so stale updates can be ignored. This yields at-least-once transport with idempotent command handling rather than pretending WebSocket provides exactly-once delivery.

Managed services show that persistent control channels are cheap, but they also force reconnect behavior. In API Gateway's published US example, WebSocket traffic costs $1 per million messages and $0.25 per million connection-minutes ([AWS pricing example](https://aws.amazon.com/api-gateway/pricing/)). Two continuously connected devices consume about 86,400 connection-minutes/month, roughly **$0.022/month** before message, compute, storage, logging, and transfer charges. API Gateway also imposes a two-hour maximum connection duration and ten-minute idle timeout ([AWS quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-execution-service-websocket-limits-table.html)), so it would require heartbeat/reconnect logic. Cloudflare Durable Objects are another implementation example. Their WebSocket Hibernation API avoids idle duration charges, with published free/paid request and compute allowances ([Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)). These prices show that control traffic itself will be cheap. They do not choose a vendor.

## Why direct P2P is not the default

WebRTC provides reliable, ordered data channels when configured without lifetime/retransmit limits ([W3C WebRTC Recommendation](https://www.w3.org/TR/webrtc/#datachannel)). Its data channels require DTLS. But the application must still provide out-of-band signaling, identity binding, reconnection/reconciliation, STUN, and TURN. A native cross-platform implementation adds packaging risk. The actively developed pure-Rust `webrtc` stack exists ([official repository](https://github.com/webrtc-rs/webrtc)). The established cross-platform `libdatachannel` path introduces C/C++ and Rust-FFI build artifacts. Neither removes the hosted signaling dependency.

If a future destination includes high-bandwidth device-to-device file transfer, revisit WebRTC or another direct transport: avoiding relay egress would then have material value. That is outside this map's current destination.

## Why an overlay is still useful as an expert option

Tailscale's data plane directly connects devices where possible and falls back to end-to-end-encrypted DERP relays where necessary ([device connectivity](https://tailscale.com/docs/reference/device-connectivity), [DERP documentation](https://tailscale.com/docs/reference/derp-servers)). It already solves cross-platform installation, NAT traversal, device identity, key distribution, and connection migration. It is technically the lowest-infrastructure option.

The tradeoff is product ownership. Users must install and authenticate Tailscale on every device, keep both devices in a tailnet, and maintain grants/ACLs. The app must bind a local listener safely and authenticate the calling device at the application layer; membership in a private network is not sufficient authorization for auto-starting downloads. Tailscale's control plane also remains a dependency for new connection establishment, although established connections and cached policy can survive a control-plane outage ([control/data planes](https://tailscale.com/docs/concepts/control-data-planes)).

## Prototype facts still required

1. Verify that a Rust-side WebSocket reconnects correctly after Windows sleep, network changes, captive portals, service-enforced idle closure, and app resume. Repeat on macOS and Linux, but Windows is the release gate.
2. Test `wss://` over TCP 443 through representative home, corporate, VPN, IPv4-only, IPv6-only, and proxy networks. Confirm DNS/TLS/proxy behavior and measure reconnect time.
3. Force disconnects at every command/ack/status boundary. Prove that a reconnect cannot start a duplicate download or lose a cancellation, status stays monotonic, and an offline host rejects work without a cloud queue.
4. Prototype pairing, key storage, key rotation/revocation, multi-host routing, replay rejection, and recovery after reinstall. Run a focused security review before fixing the E2EE envelope protocol.
5. Benchmark one candidate service's connection limits, presence model, observability redaction, regional latency, and full cost including authentication, storage, compute, logs, and abuse controls. Do not select from message pricing alone.

## Decisions enabled by this research

- Default topology: outbound hosted control relay, not direct P2P or a required overlay.
- Data boundary: opaque E2EE commands/status only; media, cookies, paths, and file contents stay local to the download host.
- Delivery semantics: explicit at-least-once delivery with IDs, acknowledgements, deduplication, and revisioned status; no server-side offline job queue.
- Platform gate: Windows host/requester behavior must pass the lifecycle and restricted-network prototype before implementation architecture is locked.
- Future boundary: reconsider P2P only if high-bandwidth device-to-device transfer enters scope.
