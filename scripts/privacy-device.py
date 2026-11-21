#!/usr/bin/env python3
"""Apply the narrow, reversible BOOMAIR privacy pass; no app data is deleted."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

import boomair_device as base
PACKAGES = ('com.google.android.apps.nbu.smartconnect.tv',
            'com.google.android.sss.authbridge', 'com.google.android.partnersetup')
SETTINGS = {'ble_scan_always_enabled': '0', 'send_action_app_error': '0'}
MIC_PACKAGES = ('local.minimedia.youtube', 'com.google.android.inputmethod.latin')
MIC = base.MIC


def restore_setting(key, value):
    if key not in SETTINGS:
        raise RuntimeError('Unexpected setting in recovery record')
    if value == 'null':
        base.shell('settings', 'delete', 'global', key)
    else:
        if not re.fullmatch(r'-?\d+', value):
            raise RuntimeError('Unexpected prior setting value')
        base.shell('settings', 'put', 'global', key, value)
    if base.shell('settings', 'get', 'global', key) != value:
        raise RuntimeError('Could not restore ' + key)


def verify_applied(record):
    base.verify_device()
    for package in PACKAGES:
        if base.package_state(package) not in (2, 3, 4):
            raise RuntimeError('Package not disabled: ' + package)
    for key, value in SETTINGS.items():
        if base.shell('settings', 'get', 'global', key) != value:
            raise RuntimeError('Setting not applied: ' + key)
    for package in record['microphones_before']:
        if base.mic_granted(package):
            raise RuntimeError('Microphone still granted: ' + package)
    if record['usb_attempted'] and base.shell('getprop', 'service.adb.tcp.port') not in ('-1', '0'):
        raise RuntimeError('TCP debugging still enabled')
    if not base.resolve_home().startswith('local.minimedia.home/'):
        raise RuntimeError('Default Home changed unexpectedly')
    for package in base.KEEP:
        if base.package_state(package) not in (0, 1):
            raise RuntimeError('Required app disabled: ' + package)


def rollback(record):
    failures = []
    actions = []
    if record.get('usb_attempted'):
        port = record['tcp_port_before']
        if not str(port).isdigit() or not 1 <= int(port) <= 65535:
            raise RuntimeError('Invalid prior TCP debugging port')
        actions.append(('TCP debugging', lambda: base.restart_adb('tcpip', port)))
    for package in reversed(record['microphones_attempted']):
        if package not in MIC_PACKAGES:
            raise RuntimeError('Unexpected microphone package')
        def permission_action(p=package):
            prior = record['microphones_before'][p]
            if not isinstance(prior, bool):
                raise RuntimeError('Invalid prior permission state')
            base.shell('pm', 'grant' if prior else 'revoke', '--user', '0', p, MIC)
            if base.mic_granted(p) != prior:
                raise RuntimeError('Permission restoration failed')
        actions.append((package + ' microphone', permission_action))
    for key in reversed(record['settings_attempted']):
        actions.append((key, lambda k=key: restore_setting(k, record['settings_before'][k])))
    for package in reversed(record['packages_attempted']):
        if package not in PACKAGES:
            raise RuntimeError('Unexpected package in recovery record')
        def package_action(p=package):
            prior = record['packages_before'][p]
            if prior not in base.STATE_COMMANDS:
                raise RuntimeError('Invalid prior package state')
            base.restore_package(p, prior)
        actions.append((package, package_action))
    for label, action in actions:
        try:
            action()
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            failures.append(label + ': ' + str(error))
    return failures


def apply(no_microphone):
    base.verify_device()
    if not base.resolve_home().startswith('local.minimedia.home/'):
        raise RuntimeError('Expected MiniMedia as default Home')
    for package in base.KEEP:
        if base.package_state(package) not in (0, 1):
            raise RuntimeError('Required app disabled: ' + package)
    tcp_port = base.shell('getprop', 'service.adb.tcp.port')
    if tcp_port.isdigit() and int(tcp_port) > 0:
        device = next((line for line in base.adb('devices', '-l').splitlines()
                       if line.startswith(base.SERIAL + ' ')), '')
        if 'usb:' not in device:
            raise RuntimeError('USB transport required before disabling TCP debugging')
    record = dict(kind='minimedia-privacy-v1', serial=base.SERIAL, status='prepared',
                  packages_before={p: base.package_state(p) for p in PACKAGES},
                  settings_before={k: base.shell('settings', 'get', 'global', k) for k in SETTINGS},
                  microphones_before={p: base.mic_granted(p) for p in MIC_PACKAGES} if no_microphone else {},
                  tcp_port_before=tcp_port, packages_attempted=[], settings_attempted=[],
                  microphones_attempted=[], usb_attempted=False)
    path = base.ROOT / 'private/device-changes' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-privacy.json')
    base.write_record(path, record)
    print('Recovery record:', path, flush=True)
    try:
        for package, prior in record['packages_before'].items():
            if prior not in (0, 1):
                continue
            base.disable_package(package, record, path, attempts='packages_attempted')
            print('Disabled:', package, flush=True)
        for key, value in SETTINGS.items():
            if record['settings_before'][key] == value:
                continue
            record['settings_attempted'].append(key)
            base.write_record(path, record)
            base.shell('settings', 'put', 'global', key, value)
            if base.shell('settings', 'get', 'global', key) != value:
                raise RuntimeError('Setting failed: ' + key)
            print('Set:', key, '=', value, flush=True)
        for package, prior in record['microphones_before'].items():
            if not prior:
                continue
            record['microphones_attempted'].append(package)
            base.write_record(path, record)
            base.shell('pm', 'revoke', '--user', '0', package, MIC)
            if base.mic_granted(package):
                raise RuntimeError('Microphone revoke failed: ' + package)
            print('Microphone revoked:', package, flush=True)
        if tcp_port.isdigit() and int(tcp_port) > 0:
            record['usb_attempted'] = True
            base.write_record(path, record)
            base.restart_adb('usb')
            print('ADB changed to USB-only', flush=True)
        verify_applied(record)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        record['failure'] = str(error)
        record['rollback_failures'] = rollback(record)
        record['status'] = 'rollback-incomplete' if record['rollback_failures'] else 'rolled-back'
        base.write_record(path, record)
        raise RuntimeError(f'Privacy pass failed: {error}. Recovery: {path}; {record["status"]}')
    record['status'] = 'complete'
    base.write_record(path, record)
    print('Privacy pass complete. App data, VPN profile, certificate trust and hardware services retained.')
    print('Restore: python3 scripts/privacy-device.py --restore', path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true')
    group.add_argument('--restore', type=Path)
    parser.add_argument('--no-microphone', action='store_true', help='Revoke YouTube and keyboard microphone access')
    args = parser.parse_args()
    if args.apply:
        apply(args.no_microphone)
    elif args.restore:
        base.verify_device()
        record = json.loads(args.restore.read_text())
        if record.get('kind') != 'minimedia-privacy-v1' or record.get('serial') != base.SERIAL:
            raise RuntimeError('Not a privacy record for this device')
        failures = rollback(record)
        if failures:
            raise RuntimeError('Restore failures: ' + '; '.join(failures))
        print('Restored recorded package, settings, microphone and TCP-debugging states.')
    else:
        print('Disable:', ', '.join(PACKAGES))
        print('Disable always-on BLE scans and the Android crash-report action; switch network ADB to USB-only.')
        print('Optional --no-microphone: revoke microphone access for YouTube and TV keyboard.')
        print('No changes made. Use --apply. All mutations journaled; --restore restores exact prior states.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        sys.exit('Error: ' + str(error))
