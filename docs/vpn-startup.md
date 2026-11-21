# WireGuard startup

> Public-source note: device serials are configured locally; network addresses
> below are illustrative replacements. See [local setup](local-setup.md).

**Current application:** [the compatible WireGuard derivative](wireguard-compat.md)
uses package `local.minimedia.sdmcw` to survive the observed vendor memory
cleanup. Stock WireGuard was repeatedly force-stopped despite always-on being
enabled. See [the investigation and options](vpn-reliability-options.md).

BOOMAIR runs Android 11 and supports Android's always-on VPN mechanism. Its TV
Settings app does not resolve `android.settings.VPN_SETTINGS`, so the persistent
user-0 settings are configured through ADB:

```bash
adb -s "$MINIMEDIA_SERIAL" shell settings --user 0 put secure always_on_vpn_app local.minimedia.sdmcw
adb -s "$MINIMEDIA_SERIAL" shell settings --user 0 put secure always_on_vpn_lockdown 0
```

Android 11 loads these settings when creating the user's VPN manager at system
startup. Writing the keys alone does not update its current in-memory state.
WireGuard's userspace backend restores saved tunnels when Android starts it as
an always-on VPN. The imported tunnel must have been configured and brought up
at least once; no profile export, private-key copying or replacement app is needed.

Lockdown remains off. The existing split-tunnel routes `192.0.2.0/24` and
`198.51.100.0/24` are unchanged; ordinary Internet access stays outside the tunnel.
This setting keeps the VPN service available, while reachability still depends
on Wi-Fi, the endpoint and the home router.

The initial stock-app settings and reboot verification are recorded in
`private/device-changes/20261120T030322429883Z-always-on-vpn.json`.
Both keys were absent before that initial change. To restore the original startup
configuration, delete the two keys and restart the projector:

```bash
adb -s "$MINIMEDIA_SERIAL" shell settings --user 0 delete secure always_on_vpn_app
adb -s "$MINIMEDIA_SERIAL" shell settings --user 0 delete secure always_on_vpn_lockdown
```

Sources:
- [Android always-on VPN](https://developer.android.com/develop/connectivity/vpn#always-on)
- [Android 11 VPN manager](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/services/core/java/com/android/server/connectivity/Vpn.java)
- [WireGuard always-on callback](https://github.com/WireGuard/wireguard-android/blob/1.0.20260315/ui/src/main/java/com/wireguard/android/Application.kt)

## Boot-time clock bootstrap

The first boot test launched WireGuard automatically, but the device's clock
had reset to May 26, 2025. Handshakes retried without responses. Correcting the
clock from the host immediately restored private-network reachability. WireGuard
rejects replayed handshake timestamps; the observed backward clock explains
this failure ([protocol](https://www.wireguard.com/protocol/)).

Android automatic time was already enabled, but its NTP cache remained empty
until the VPN connected. To remove the dependency on the tunnel's private DNS,
`settings global ntp_server` is now `216.239.35.0`, the IPv4 address resolved for
Google Public NTP's `time.google.com` during setup. Automatic time remains on.
The selected address and original setting are journaled with the VPN change.
No VPN private key, peer, DNS setting or routing prefix was changed.

The original `ntp_server` value was absent. To restore its firmware default:

```bash
adb -s "$MINIMEDIA_SERIAL" shell settings delete global ntp_server
```

[Google Public NTP](https://developers.google.com/time/faq) is the configured
clock source; this is a fixed service IP rather than a hostname lookup at boot.

## Verified result

A second reboot completed without manually opening WireGuard or setting the
clock. Android's NTP cache populated, the clock matched the host, WireGuard
logged an always-on service start and a handshake response, and `192.0.2.1`
answered through the tunnel. Lockdown remained `0`. MiniMedia remained Home.

The reboot test also established that the firmware reopens TCP ADB port 5555 at
startup. USB-only mode was reapplied after verification. This remains a separate
firmware/privacy limitation; always-on VPN does not suppress that listener.
