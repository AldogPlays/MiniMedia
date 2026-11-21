# Temporary VPN resilience test

Build only: `python3 scripts/build-vpn-pressure-test.py`.

This disposable Android activity holds touched memory blocks to exercise the
vendor's 450 MiB cleanup threshold. It has no network, VPN or storage permissions.
It caps allocations at the smaller of 512 MiB or the application heap limit less
64 MiB, stops on pause or after 45 seconds, and releases early if available
memory drops below 300 MiB. Allocation failure is caught and releases the list.

Run only in a coordinated test window: the vendor cleanup force-stops other
applications. Use the specifically connected BOOMAIR serial:

```bash
adb -s "$MINIMEDIA_SERIAL" install build/vpn-pressure/test.apk
adb -s "$MINIMEDIA_SERIAL" shell am start -W -n local.minimedia.sdmcpressure/.PressureActivity
```

Observe memory and logs; when available memory is below 450 MiB, the vendor's
existing callback can be exercised with:

```bash
adb -s "$MINIMEDIA_SERIAL" shell am send-trim-memory com.sdmc.service RUNNING_LOW
```

Confirm a vendor sweep actually occurred, compare VPN PIDs across the sweep,
and test private-network traffic. Then uninstall the helper:

```bash
adb -s "$MINIMEDIA_SERIAL" uninstall local.minimedia.sdmcpressure
```

The initial deployed test reached 374 MiB available. It hit its application heap
limit and released allocations normally; a vendor sweep followed, stopped stock
WireGuard and other non-exempt apps, and left compatible WireGuard PID 3272
unchanged with private-network pings working. The source now reserves 64 MiB of
heap headroom to avoid that expected allocation-failure path in future runs.
