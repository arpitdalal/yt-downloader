# Desktop host presence and lifecycle constraints

Research for [Research desktop host presence and lifecycle constraints](https://github.com/arpitdalal/yt-downloader/issues/73), 2026-08-30.

## Recommendation

Run the remote-download host as the existing per-user Tauri desktop application, with its window hidden and a tray/menu-bar affordance. Do not turn it into a system service. Offer opt-in launch at user login on Windows, macOS, and supported Linux desktops. Closing the window should hide it; an explicit **Quit** should stop the host.

Treat host presence as a short-lived, server-observed lease, not a durable boolean:

- `available`: the host has an authenticated relay connection, a fresh lease, and most recently declared itself eligible.
- `unavailable`: the lease is stale, the connection closed, or the host declared itself ineligible because the session is locked, suspend is starting, shutdown/quit is starting, or required local configuration is invalid.
- A request is accepted only after the currently connected host rechecks eligibility and returns a live acknowledgement. Cached presence may enable UI, but must never accept work by itself.
- The relay must not queue a request for later delivery. If no live acknowledgement arrives before a short deadline, reject it as host unavailable. A late or duplicated request must be harmless through a request id/idempotency rule, to be specified with the transport protocol.

This model makes sudden sleep, connectivity loss, crashes, forced termination, and power loss safe even when no final lifecycle callback is delivered. A graceful “unavailable” update improves latency and reason display; lease expiry is the correctness mechanism.

Windows is the normative host platform. macOS can target the same contract. Linux should enable the host role only for an explicitly tested session stack where lock and suspend state can be observed; otherwise fail closed for remote hosting while retaining requester functionality.

## Why a hidden Tauri app is sufficient

Tauri separates window visibility from application exit. Its `Window.hide()` operation only sets visibility to false, while its app event loop has distinct `ExitRequested` and `Exit` events. A close request can be intercepted, and the app can remain alive with a tray icon. ([Tauri window `hide`](https://v2.tauri.app/reference/javascript/api/namespacewindow/#hide), [Tauri `RunEvent`](https://docs.rs/tauri/latest/tauri/enum.RunEvent.html), [Tauri `WindowEvent`](https://docs.rs/tauri/latest/tauri/enum.WindowEvent.html))

The host connection, lease timer, lifecycle state, and job acceptance must live in the Rust core, not in React. Window focus is not session lock, and a hidden or destroyed webview must not control host presence. Tauri's documented `RunEvent` and `WindowEvent` variants contain no desktop session-lock or system-suspend event; `RunEvent::Resumed` is only documented as the event loop being resumed, not as a cross-platform wake signal. Platform adapters are therefore required. ([Tauri `RunEvent`](https://docs.rs/tauri/latest/tauri/enum.RunEvent.html), [Tauri `WindowEvent`](https://docs.rs/tauri/latest/tauri/enum.WindowEvent.html))

The official Tauri autostart plugin supports Windows, macOS, and Linux and can pass an argument such as `--autostart` so launch can suppress the main window. It is a user-session mechanism, not boot-time service availability. Windows `Run` entries execute when a user logs on and may be delayed; a macOS LaunchAgent belongs to a logged-in user and stops at logout; the XDG autostart specification launches applications after desktop login. ([Tauri autostart](https://v2.tauri.app/plugin/autostart/), [Windows `Run` keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys), [Apple LaunchAgents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html), [XDG autostart](https://zbrown.pages.freedesktop.org/xdg-specs/autostart-spec/latest/ar01s02.html))

Consequences:

- Before login, after logout, and after explicit quit, the host is unavailable.
- “Launch at startup” should be named **Launch at login** in product copy.
- Closing the last window and quitting must be different actions.
- The host does not need administrator/root installation or a privileged service.

## Lifecycle contract

| Situation | What the app can rely on | Required host behavior |
|---|---|---|
| Window hidden/minimized | Rust process and event loop remain alive if close is intercepted rather than exiting. | Continue relay connection, leases, accepted downloads, progress, and cancellation. |
| Session locks | Windows exposes explicit lock/unlock session messages. macOS exposes user-session active/inactive notifications, but public documentation does not state that they cover every lock path. systemd exposes a desktop-supplied `LockedHint`, not an independently authoritative lock detector. | Immediately declare ineligible when a supported adapter reports lock; reject races during host-side acceptance. Do not infer lock from window focus. |
| Normal suspend begins | All three OS families expose pre-suspend notifications through platform APIs, with caveats. | Mark ineligible, best-effort flush state/update relay, then stop accepting. Correctness still depends on lease expiry. |
| Computer is asleep/hibernating | User application execution and network reachability cannot be assumed. | No new work. Never model sleep as a background execution state. |
| Wake/resume | Resume notification is available through platform APIs, but old network connections may be dead. | Re-read lock/configuration state, establish a fresh authenticated connection/session, then become eligible. Never reuse cached availability. |
| Network path changes | OS connectivity indicators are hints and can be stale, disabled, proxy-specific, or unrelated to reachability of this relay. | Use them only to accelerate reconnect. Relay connection health plus application heartbeat/lease is authoritative. |
| Graceful quit/logout/shutdown | A callback may provide a short cleanup opportunity, but shutdown cannot be indefinitely delayed. | First become ineligible; terminate or deliberately hand off any child job; close the connection; persist durable state. |
| Crash, force-kill, power loss, critical suspend | No cleanup callback is guaranteed. Windows explicitly may omit pre-suspend notification during critical suspension. | Lease expires to unavailable; unacknowledged requests fail; recovery reconciles durable job state. |

### Windows (mandatory)

- `WTSRegisterSessionNotification` registers a window for `WM_WTSSESSION_CHANGE`; `WTS_SESSION_LOCK` and `WTS_SESSION_UNLOCK` explicitly identify session lock transitions. Registration can initially fail if Remote Desktop Services dependencies are not ready, so startup must retry or verify registration rather than assuming success. ([registration](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/nf-wtsapi32-wtsregistersessionnotification), [session messages](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change))
- `WM_POWERBROADCAST` reports `PBT_APMSUSPEND`, `PBT_APMRESUMEAUTOMATIC`, and user-triggered `PBT_APMRESUMESUSPEND`. Normal suspend gives applications a short preparation window; critical suspension may provide no notification. ([power messages](https://learn.microsoft.com/en-us/windows/win32/power/wm-powerbroadcast), [sleep criteria](https://learn.microsoft.com/en-us/windows/win32/power/system-sleep-criteria))
- Windows can prevent idle sleep temporarily with `SetThreadExecutionState(ES_SYSTEM_REQUIRED)`, but Microsoft warns against holding it indefinitely, especially on Modern Standby, and it cannot override user-initiated sleep. That is an optional active-download policy, not a presence primitive. ([`SetThreadExecutionState`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate), [sleep criteria](https://learn.microsoft.com/en-us/windows/win32/power/system-sleep-criteria))
- Windows NCSI is useful as a reconnect hint, but Microsoft says not to rely on its indicator alone because a failed probe does not necessarily mean the application lacks Internet access. ([NCSI guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/troubleshoot-ncsi-guidance))

Prototype the native-message hook against a hidden Tauri window on supported Windows versions. The acceptance test must cover local lock/unlock, Remote Desktop connect/disconnect and lock, normal sleep/wake, critical/forced sleep behavior where practical, network transitions, app close-to-tray, explicit quit, and autostart after login.

### macOS

- `NSWorkspace` posts `willSleep` and `didWake`, plus `willPowerOff`. These must be observed through `NSWorkspace.notificationCenter`. ([`NSWorkspace`](https://developer.apple.com/documentation/appkit/nsworkspace), [`didWakeNotification`](https://developer.apple.com/documentation/appkit/nsworkspace/didwakenotification))
- `sessionDidResignActive` and `sessionDidBecomeActive` report a user session switching out/in. Apple's public wording does not promise that these notifications are an exact screen-lock API, so lock coverage must be proven rather than assumed. ([`sessionDidResignActiveNotification`](https://developer.apple.com/documentation/appkit/nsworkspace/sessiondidresignactivenotification))
- A power assertion can prevent idle sleep, but Apple describes assertions as suggestions and notes that low-power or thermal conditions can still force sleep. A user-idle sleep assertion also does not override lid close, explicit sleep, or low battery. ([prevent system sleep](https://developer.apple.com/documentation/iokit/kiopmassertiontypepreventsystemsleep), [prevent user-idle sleep](https://developer.apple.com/documentation/iokit/kiopmassertiontypepreventuseridlesystemsleep))
- `NWPathMonitor` reports available path changes; it should accelerate reconnection, while actual relay liveness remains authoritative. ([`NWPathMonitor`](https://developer.apple.com/documentation/network/nwpathmonitor))

Prototype the exact public, App-Store-safe lock detector. If no supported API reliably distinguishes lock from ordinary session/app inactivity, do not enable the remote host role until the product either accepts that limitation explicitly or adopts a supported helper design.

### Linux

- On systemd systems, `org.freedesktop.login1.Manager.PrepareForSleep(true/false)` reports the transition into and out of suspend/hibernate. systemd warns that reacting without a delay inhibitor is racy; normal user processes are frozen during the sleep transition. ([login1 interface](https://github.com/systemd/systemd/blob/main/man/org.freedesktop.login1.xml), [inhibitor guidance](https://github.com/systemd/systemd/blob/main/docs/INHIBITOR_LOCKS.md), [systemd suspend behavior](https://man7.org/linux/man-pages/man8/systemd-suspend.service.8.html))
- The login1 session `LockedHint` is explicitly a hint set by the desktop environment through `SetLockedHint`; it is not an OS-derived guarantee. The `Lock`/`Unlock` signals mean the session was *asked* to lock/unlock, not confirmation that it did. ([login1 session interface](https://raw.githubusercontent.com/systemd/systemd/main/man/org.freedesktop.login1.xml))
- NetworkManager exposes network and optional connectivity state, but connectivity checking can be disabled or unconfigured. Use its D-Bus changes only as reconnect hints. ([NetworkManager state](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.html), [connectivity configuration](https://www.networkmanager.dev/docs/api/latest/NetworkManager.conf.html))
- XDG autostart begins after desktop login, not at machine boot. ([XDG autostart](https://zbrown.pages.freedesktop.org/xdg-specs/autostart-spec/latest/ar01s02.html))

There is no single reliable desktop-lock contract across all Linux distributions, init systems, display managers, and desktop environments in the sources reviewed. Define a supported matrix (for example, specific systemd + desktop-environment versions), test `LockedHint` behavior end to end, and disable hosting when the required provider is absent or inconclusive.

## Presence and reconnect state machine

Recommended local states:

1. `starting`: load identity, validate destination, register lifecycle adapters; reject work.
2. `connecting`: session is unlocked and locally eligible, but no authenticated relay session; reject work.
3. `available`: fresh authenticated relay session and host has published eligible; requests may enter live acceptance.
4. `ineligible(reason)`: locked, suspending, destination invalid, shutting down, or another local policy failure; keep or close transport as appropriate, but reject work.
5. `offline`: transport absent or process stopped; represented remotely by lease expiry, not a trusted final message.

Transitions must be monotonic within a connection epoch. Every reconnect creates a new epoch and supersedes prior leases and acceptances. After wake or connectivity recovery, start at `connecting`, re-register/verify lifecycle sources if necessary, re-read lock state and destination validity, and only then publish `available`.

WebSocket ping/pong may verify that an endpoint is responsive, but abnormal transport loss still requires reconnect logic. RFC 6455 recommends randomized delay before reconnecting after abnormal closure to avoid a reconnect storm. ([RFC 6455](https://datatracker.ietf.org/doc/html/rfc6455))

Do not expose platform guesses as stronger truth than the protocol has. Remotely, `locked` or `sleeping` can be a best-effort reason while a lease is fresh; after it expires, display the generic `unavailable`/`last seen` state.

## Existing process-lifecycle hazard

The current Rust core stores the active Python downloader as `std::process::Child` and polls it, but has no app-exit lifecycle handler. Rust deliberately does not kill a child when its handle is dropped, so a Tauri crash or exit can leave the downloader running without its controlling host. ([current process tracking](https://github.com/arpitdalal/yt-downloader/blob/main/src-tauri/src/lib.rs), [`std::process::Child`](https://doc.rust-lang.org/std/process/struct.Child.html))

Before remote hosting ships, define and implement a process-tree ownership contract that works on Windows as well as Unix. Graceful quit should either cancel and reap the full download process tree or explicitly persist and reattach/reconcile it. Crash containment may require Windows Job Objects and Unix process groups; that implementation choice needs a prototype.

## Decisions established

- Use a per-user hidden/tray Tauri process, not a privileged system service.
- Offer opt-in **Launch at login** on all supported host platforms; the machine is not a host before user login or after logout.
- Keep lifecycle, transport, leases, and request acceptance in Rust, independent of React/window visibility.
- Define availability as fresh server-observed presence plus host-declared eligibility; always require a live host acknowledgement before accepting a job.
- Never queue work for an unavailable host.
- Treat graceful lifecycle signals and network-path notifications as latency/UX optimizations. Lease expiry and live acknowledgement provide correctness.
- Reconnect into a new connection epoch, revalidate local state, and use randomized backoff.
- Windows is mandatory and normative. Linux hosting is capability-gated to tested environments; unsupported/inconclusive lock detection fails closed.
- Do not prevent system sleep merely to stay available. Whether an already accepted download may temporarily inhibit *idle* sleep is a separate product decision.

## Newly sharp decisions and prototype needs

1. **Active-download power policy:** should an accepted download continue while the session locks, and should it temporarily inhibit idle sleep? User-initiated sleep/lid close must still win.
2. **Interrupted-job semantics:** after sleep, app restart, crash, or network loss, does an accepted job resume, restart, fail, or require user action? This must align with durable job state and idempotency.
3. **Process-tree ownership prototype:** prove clean cancellation/reaping on Windows, macOS, and Linux, including app crash and updater-driven restart.
4. **Windows lifecycle prototype:** prove WTS and power messages reach a hidden Tauri app and survive close-to-tray, Remote Desktop transitions, autostart, suspend, and reconnect.
5. **macOS lock prototype:** identify and verify an officially supported lock-state mechanism. Session-active notifications alone are insufficiently explicit in public documentation.
6. **Linux support matrix prototype:** choose desktop environments/distributions, prove `LockedHint` and `PrepareForSleep`, and define the UI/error when hosting capability is absent.
7. **Presence protocol constants:** choose heartbeat/lease/acceptance deadlines, connection-epoch representation, and idempotency behavior alongside the relay transport decision.
