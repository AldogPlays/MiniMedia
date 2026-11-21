# WireGuard reliability investigation

Investigated November 19, 2026. Subsequent deployment uses the shorter package
`local.minimedia.sdmcw`; see [the compatible build and recovery](wireguard-compat.md).
The findings below describe the research that led to that implementation.

## Confirmed cause on this projector

`com.sdmc.service` runs as Android UID 1000. Its installed APK is
`/system/app/SdmcServiceManager/SdmcServiceManager.apk`, version
`tag347.2025.03.06.10066`, SHA-256
`9c6932e603dba4a808afbd9521b7f68af1d29c966e6c3af61b31fc0da293dc1b`.
The inspected APK, manifest and DEX disassembly are saved under ignored
`private/privacy-audit/`.

ActivityManager logs attribute the WireGuard force-stop to PID 1753, which
`ps` identifies as `com.sdmc.service`. Repeated force-stops were observed, not
just an isolated connection failure. The same sweep also stops MiniMedia and
other third-party applications.

The DEX has two direct calls to `ActivityManager.forceStopPackage`, in
`killBackgroundProcess` and `killthirdApp`. Both consult `isWhitePackages`.
The latter enumerates installed non-system apps, skips a foreground process
or an exempt package, and force-stops the rest. Consequently, being a VPN
foreground service alone does not protect WireGuard from this routine.

The cleanup is called from a recurring handler and `onTrimMemory` when Android
reports less than 450 MiB available memory. `getAvailiableMemory` divides
`ActivityManager.MemoryInfo.availMem` by 1,048,576. This threshold and the
exemption predicate are constants in code; no configurable exemption list was
found in these call paths.

`isWhitePackages` returns false for the three exact packages
`com.sdmc.implayer`, `com.sdmc.bluetoothspeaker`, and `com.sdmc.sdmcfactory`.
After those special cases, it accepts strings containing `google`, `sdmc`,
`cts`, `android.app`, and several other specific package names. This is a
package-name test, not a signing-certificate or UID test.

## Options

| Option | Assessment on this BOOMAIR |
| --- | --- |
| Build WireGuard with an exempt, locally owned application ID | Best first experiment for keeping the VPN on the projector. Leaves hardware service and firmware intact. Requires custom updates and tunnel migration. Static code supports the approach; runtime survival is not yet tested. |
| Device-owner protection for stock WireGuard | Android 11 has a genuine force-stop protection policy. More invasive provisioning and management privileges; current additional user and account are obstacles. Keep as a second route. |
| Disable the whole vendor package | Removes the observed caller but also removes its power, brightness, remote, and battery/temperature-warning behavior. Hardware dependencies are not sufficiently established. |
| Patch the vendor APK or hook its cleanup methods | Precise in principle, but the package shares `android.uid.system`; a normally signed replacement cannot join that identity. Requires a vendor-signed update or privileged system modification. |
| Run connectivity policy on OpenWrt | Strong alternative when access to home services is the goal. At home, narrowly scoped IoT-to-server firewall rules may eliminate the local tunnel requirement; away from home, a WireGuard-capable gateway can own the tunnel. This changes where the tunnel ends. |
| Watchdog, battery exemption, or keepalive alone | Does not prevent the observed force-stop. A watchdog can only repair after an outage and can itself be stopped. Keepalive addresses idle NAT mappings, not process termination. |

### Recommended custom WireGuard experiment

Use official WireGuard source matching the installed release, `1.0.20260315`.
Candidate application ID: `local.minimedia.sdmccompat.wireguard`.
It contains `sdmc` and reaches the true branch of the inspected exemption
predicate, without claiming a vendor-owned package or Android system identity.
The app would retain an ordinary application UID and our own signature.
This avoids changing the vendor APK; it is not a new exemption added to it.

Upstream's build uses `wireguardPackageName` for both its namespace and
application ID. An implementation must distinguish the installed application
ID from source/generated-code namespaces, and inspect merged component names,
provider authorities, custom tunnel-control permission and native package/path
constants. Merely editing one string or renaming an APK is insufficient.

Upstream's release updater explicitly rejects package names outside
`com.wireguard.*`. A local fork must remove/replace its updater integration and
remove the app-install permission, preserving license notices and WireGuard
cryptography. It must not fetch official APK updates that cannot update our
package/signature. Record pinned source/submodule versions and build hashes.

Migration would install alongside stock WireGuard first. Re-import the
**corrected split-tunnel** profile; do not silently reuse the original full-tunnel
Downloads export. Keep credentials out of logs. Only one copy should have its
tunnel enabled. After consent and successful connectivity checks, point Android
always-on at the new package, update MiniMedia's WireGuard launch target, then
disable the stock copy without erasing its recovery data. Preserve lockdown=0.

Acceptance checks must cover a cold boot with working time synchronization,
sleep/wake, Wi-Fi disconnect/reconnect, normal internet and private-network
reachability, and the *actual vendor cleanup trigger*. Seeing the app running
at idle is insufficient. Any induced memory pressure/trim test should happen
in a coordinated test window because the vendor sweep can stop other apps.
Finish with a sustained playback/overnight soak. Static exemption is not a
promise of continuous connectivity: OS memory pressure, firmware updates,
network outages and power state still matter.

### Device-owner protection

Android 11 `DevicePolicyManager.setUserControlDisabledPackages` requires a
device owner in that release. AOSP's `ActivityManagerService.forceStopPackage`
checks `isPackageStateProtected` and returns before stopping protected packages.
This could protect the official app against the exact API the vendor calls,
subject to verifying this firmware retains that behavior.

The projector currently has no device owner, setup is complete, users 0 and 10
exist, and user 0 has an account. AOSP's post-setup ADB provisioning checks
normally reject additional users and incompatible accounts. Do not delete
accounts/users or reset the projector as an investigative step. Device-owner
management also gives the management application substantial authority and
requires an explicit provisioning/recovery design.

### Firmware/root and recovery limits

Read-only checks report verified boot `green`, vbmeta device state `locked`,
`ro.debuggable=0`, and no `su` found on the shell PATH. These observations do
not prove unlocking/root is impossible, but no verified BOOMAIR procedure or
recovery image was established. Do not unlock, flash, disable verification or
experiment with generic projector firmware on this evidence.

## Sources

- [WireGuard release source](https://github.com/WireGuard/wireguard-android/tree/1.0.20260315)
- [WireGuard application build configuration](https://github.com/WireGuard/wireguard-android/blob/1.0.20260315/ui/build.gradle.kts)
- [WireGuard updater](https://github.com/WireGuard/wireguard-android/blob/1.0.20260315/ui/src/main/java/com/wireguard/android/updater/Updater.kt)
- [Android 11 force-stop implementation](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/services/core/java/com/android/server/am/ActivityManagerService.java#L4455)
- [Android 11 device-policy implementation and provisioning checks](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/services/devicepolicy/java/com/android/server/devicepolicy/DevicePolicyManagerService.java)
- [Device-policy API reference](https://developer.android.com/reference/android/app/admin/DevicePolicyManager#setUserControlDisabledPackages(android.content.ComponentName,%20java.util.List))
- [Android 11 VPN implementation](https://android.googlesource.com/platform/frameworks/base/+/android11-release/services/core/java/com/android/server/connectivity/Vpn.java)
- [Android shared-user certificate requirements](https://developer.android.com/guide/topics/manifest/manifest-element#uid)
- [OpenWrt WireGuard routing](https://openwrt.org/docs/guide-user/services/vpn/wireguard/extras)
- [Aurzen BOOM air support](https://aurzen.com/pages/aurzen-boom-air-projector-help-center)
