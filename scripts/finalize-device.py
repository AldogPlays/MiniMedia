#!/usr/bin/env python3
"""Select MiniMedia Home and reversibly disable an explicit BOOMAIR app list."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

import boomair_device as device
from boomair_device import ROOT, SERIAL, HOME, STOCK, RECOVERY, RECOVERY_PACKAGE, STATE_COMMANDS, KEEP

DISABLE = (
    # Other user-facing streaming, VPN, downloader and game apps.
    'com.tailscale.ipn', 'com.wireguard.android', 'org.smarttube.beta', 'com.google.android.youtube.tv',
    'com.google.android.youtube.tvunplugged', 'com.google.android.youtube.tvmusic',
    'com.peacocktv.peacockandroid', 'com.amazon.amazonvideo.livingroom',
    'com.hulu.livingroomplus', 'tv.twitch.android.app', 'com.tubitv',
    'com.apple.atve.androidtv.appletv', 'com.google.android.play.games',
    'com.netflix.ninja', 'com.stremio.one', 'com.disney.disneyplus', 'com.esaba.downloader',
    # Freeview's content apps and tuner/catch-up integration.
    'uk.co.freeview.mdsclient', 'uk.co.freeview.amc_catchup', 'uk.co.freeview.onnow',
    'uk.co.freeview.sony_kids_vod', 'uk.co.freeview.uktv', 'uk.co.freeview.fvpconfigauth',
    'uk.co.freeview.bbc_sounds', 'uk.co.freeview.tifbridge', 'uk.co.freeview.explore',
    'uk.co.freeview.bbc', 'uk.co.freeview.ch5', 'uk.co.freeview.itv', 'uk.co.freeview.stv',
    'uk.co.freeview.amc_horror', 'uk.co.freeview.ch4_vod', 'com.mediatek.tv.freeviewplay',
    # Stock home/content discovery, Google casting/search, retail demo and feedback.
    'com.google.android.apps.tv.launcherx', 'com.google.android.apps.tv.dreamx',
    'com.google.android.tungsten.setupwraith',
    'com.google.android.katniss', 'com.google.android.apps.mediashell',
    'android.autoinstalls.config.google.gtvpai', 'fusion.android.tv.demo',
    'com.google.android.feedback', 'com.google.android.syncadapters.calendar',
    'com.android.printspooler', 'com.mediatek.android.leanbacklauncher.partnercustomizer',
)
assert not set(KEEP) & set(DISABLE)
assert len(DISABLE) == len(set(DISABLE))


def select_home(record, path):
    result = device.shell('cmd', 'package', 'set-home-activity', '--user', '0', HOME)
    print(f'Android set-home response: {result or "(no output)"}', flush=True)
    actual = device.resolve_home()
    record['home_response'] = result
    record['resolved_home_after_request'] = actual
    device.write_record(path, record)
    if actual.startswith('local.minimedia.home/'):
        return
    # BOOMAIR resolves its higher-priority stock activities even when ROLE_HOME
    # and preferred-activities correctly name MiniMedia. Verify the replacement
    # can launch before a narrowly scoped, journaled priority workaround.
    if not actual.startswith(STOCK + '/') or STOCK not in record['enabled_states']:
        raise RuntimeError(f'Home still resolves {actual}; nothing disabled. Recovery: {path}')
    candidates = device.shell('cmd', 'package', 'query-activities', '--brief', '--user', '0',
                       '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
    if not any(line.strip().startswith('local.minimedia.home/') for line in candidates.splitlines()):
        raise RuntimeError('MiniMedia absent from eligible Home activities; nothing disabled')
    launched = device.shell('am', 'start', '-W', '-n', HOME)
    if not re.search(r'^Status:\s*ok\s*$', launched, re.M):
        raise RuntimeError(f'MiniMedia launch could not be verified; nothing disabled: {launched}')
    print('Applying recorded BOOMAIR launcher-priority workaround...', flush=True)
    try:
        device.disable_package(STOCK, record, path)
        record['disabled'].append(STOCK)
        device.write_record(path, record)
        actual = device.resolve_home()
        if actual.startswith(RECOVERY_PACKAGE + '/'):
            if RECOVERY_PACKAGE not in record['enabled_states']:
                raise RuntimeError('Setup package state was not recorded')
            device.disable_package(RECOVERY_PACKAGE, record, path)
            record['disabled'].append(RECOVERY_PACKAGE)
            device.write_record(path, record)
        actual = device.resolve_home()
        if not actual.startswith('local.minimedia.home/'):
            raise RuntimeError(f'Home still resolves {actual}')
        launched = device.shell('am', 'start', '-W', '-a', 'android.intent.action.MAIN',
                         '-c', 'android.intent.category.HOME')
        if not re.search(r'^Activity:\s*local\.minimedia\.home/', launched, re.M):
            raise RuntimeError(f'Implicit Home launch was not MiniMedia: {launched}')
        record['resolved_home_after_workaround'] = actual
        device.write_record(path, record)
    except RuntimeError as error:
        rollback_failures = []
        for package in reversed(record['attempted']):
            try:
                prior = record['enabled_states'][package]
                if device.package_state(package) != prior:
                    device.shell('pm', STATE_COMMANDS[prior], '--user', '0', package)
                if device.package_state(package) != prior:
                    raise RuntimeError('Prior state was not restored')
            except RuntimeError as rollback_error:
                rollback_failures.append(package + ': ' + str(rollback_error))
        try:
            device.shell('cmd', 'package', 'set-home-activity', '--user', '0', record['previous_home'])
        except RuntimeError as rollback_error:
            rollback_failures.append('Home role: ' + str(rollback_error))
        record['rollback_failures'] = rollback_failures
        if rollback_failures:
            record['status'] = 'home-rollback-incomplete'
            device.write_record(path, record)
            raise RuntimeError(f'Home change failed: {error}; rollback needs attention: {rollback_failures}; record: {path}')
        record['status'] = 'home-workaround-rolled-back'
        record['home_failure'] = str(error)
        record['disabled'] = []
        device.write_record(path, record)
        raise RuntimeError(f'Home workaround rolled back: {error}. No other packages disabled. Recovery: {path}')


def apply():
    device.verify_device()
    installed = {line.removeprefix('package:') for line in device.shell('pm', 'list', 'packages', '--user', '0').splitlines()}
    for package in KEEP:
        if package not in installed or device.package_state(package) not in (0, 1):
            raise RuntimeError(f'Required app absent or disabled: {package}')
    previous_home = device.resolve_home()
    if previous_home.startswith('android/'):
        raise RuntimeError('Home currently resolves to a chooser; select a default before applying')
    states = {package: device.package_state(package) for package in DISABLE if package in installed}
    path = ROOT / 'private/device-changes' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    record = dict(serial=SERIAL, model='BOOMAIR', previous_home=previous_home,
                  enabled_states=states, attempted=[], disabled=[], failures={}, status='prepared')
    record['component_states'] = {}
    record['attempted_components'] = []
    device.write_record(path, record)
    print(f'Recovery record: {path}', flush=True)
    select_home(record, path)
    record['status'] = 'home-selected'
    device.write_record(path, record)
    for package, state in states.items():
        if package in record['disabled']:
            continue
        if state not in (0, 1):
            print(f'Already disabled; unchanged: {package}', flush=True)
            continue
        try:
            device.disable_package(package, record, path)
            record['disabled'].append(package)
            print(f'Disabled: {package}', flush=True)
        except RuntimeError as error:
            record['failures'][package] = str(error)
            print(f'Could not disable {package}: {error}', file=sys.stderr, flush=True)
        device.write_record(path, record)
    for package in KEEP:
        if device.package_state(package) not in (0, 1):
            raise RuntimeError(f'Required app unexpectedly disabled: {package}; recovery: {path}')
    if not device.resolve_home().startswith('local.minimedia.home/'):
        raise RuntimeError(f'Default Home verification failed; recovery: {path}')
    # The owner has imported and verified this tunnel. Remove only its temporary
    # shared-storage export; preserve WireGuard's imported copy and host original.
    device.shell('rm', '-f', '/sdcard/Download/wireguard-peer.conf')
    device.shell('am', 'start', '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
    record['status'] = 'complete' if not record['failures'] else 'complete-with-failures'
    device.write_record(path, record)
    print(f'\nMiniMedia is default Home. Disabled {len(record["disabled"])} packages; {len(record["failures"])} failures.')
    print('App data and system APKs retained. No reboot, system settings or hardware services changed.')
    print(f'Restore: python3 scripts/finalize-device.py --restore {path}')
    return bool(record['failures'])


def restore(path):
    device.verify_device()
    record = json.loads(path.read_text())
    if record.get('serial') != SERIAL or not isinstance(record.get('attempted'), list):
        raise RuntimeError('Not a recovery record for this device')
    for component in record.get('attempted_components', []):
        if component != RECOVERY:
            raise RuntimeError('Recovery record contains an unexpected component')
        state = record['component_states'][component]
        if device.component_state(component) != state:
            device.shell('pm', STATE_COMMANDS[state], '--user', '0', component)
        if device.component_state(component) != state:
            raise RuntimeError(f'Could not restore enabled state for {component}')
        print(f'Restored: {component}', flush=True)
    for package in record['attempted']:
        if package not in DISABLE:
            raise RuntimeError('Recovery record contains an unexpected package')
        state = record['enabled_states'][package]
        device.restore_package(package, state)
        print(f'Restored: {package}', flush=True)
    component = record['previous_home']
    if not re.fullmatch(r'[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+', component):
        raise RuntimeError('Invalid recovery Home component')
    device.shell('cmd', 'package', 'set-home-activity', '--user', '0', component)
    if device.resolve_home() != component:
        raise RuntimeError('Restored packages, but original Home verification failed')
    device.shell('am', 'start', '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
    print('Restored the original package states and Home selection. Certificate trust is unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true')
    group.add_argument('--restore', type=Path)
    group.add_argument('--diagnose-home', action='store_true', help='Read-only Home/role/preference diagnostics')
    args = parser.parse_args()
    if args.apply:
        return apply()
    if args.restore:
        return restore(args.restore)
    if args.diagnose_home:
        device.verify_device()
        for label, command in (
            ('Resolved Home', ('cmd', 'package', 'resolve-activity', '--brief', '--user', '0',
                               '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')),
            ('Eligible Home activities', ('cmd', 'package', 'query-activities', '--brief', '--user', '0',
                                         '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')),
            ('Android roles', ('dumpsys', 'role')),
            ('Preferred Home rules', ('dumpsys', 'package', 'preferred-xml', '--full')),
        ):
            print(f'\n{label}:', flush=True)
            try: print(device.shell(*command), flush=True)
            except RuntimeError as error: print(str(error), flush=True)
        print('\nRead-only diagnostics complete; no device changes made.')
        return
    print(f'Device: {SERIAL or "(not configured)"} (BOOMAIR, Android user 0)\nDefault Home: {HOME}')
    print('\nKeep apps: ' + ', '.join(KEEP))
    print('\nDisable packages (preserve app data; restore from recorded prior states):')
    print('\n'.join(DISABLE))
    print('\nRetain Android/Google core, Play Store, WebView, keyboard, accessibility, certificates,')
    print('network/Bluetooth/VPN, remote, projector/HDMI, audio, hardware and update components.')
    print('\nNo device changes made. Use --apply to perform this plan.')


if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        sys.exit(f'Error: {error}')
