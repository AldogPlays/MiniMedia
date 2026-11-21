"""BOOMAIR user-0 transport, state interpretation and journaled package changes.

Workflow allowlists and failure policies belong to their callers. Test adapters
replace adb (raw command responses), leaving parsers and verification in use.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def configured_serial():
    """Prefer an explicit environment override to ignored owner configuration."""
    value = os.environ.get('MINIMEDIA_SERIAL')
    if value is None:
        path = ROOT / 'private/device.json'
        value = json.loads(path.read_text()).get('serial', '') if path.is_file() else ''
    return value


SERIAL = configured_serial()
HOME = 'local.minimedia.home/.HomeActivity'
STOCK = 'com.google.android.apps.tv.launcherx'
RECOVERY = 'com.google.android.tungsten.setupwraith/.RecoveryActivity'
RECOVERY_PACKAGE = RECOVERY.split('/')[0]
STATE_COMMANDS = {0: 'default-state', 1: 'enable', 2: 'disable', 3: 'disable-user', 4: 'disable-until-used'}
KEEP = ('local.minimedia.home', 'local.minimedia.youtube', 'org.jellyfin.androidtv',
        'com.limelight', 'local.minimedia.sdmcw', 'me.zhanghai.android.files')
MIC = 'android.permission.RECORD_AUDIO'


def adb(*args):
    if not SERIAL:
        raise RuntimeError('Set MINIMEDIA_SERIAL or private/device.json before accessing a device')
    if not isinstance(SERIAL, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]*', SERIAL):
        raise RuntimeError('Invalid device serial in MINIMEDIA_SERIAL or private/device.json')
    result = subprocess.run(['adb', '-s', SERIAL, *args], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f'adb exited {result.returncode}')
    return result.stdout.strip()


def shell(*args):
    # All arguments are fixed tokens/package names. Never pass credentials or arbitrary shell text.
    return adb('shell', *args)


def package_state(package):
    output = shell('dumpsys', 'package', package)
    match = re.search(r'^\s*User 0:.*?\benabled=(\d+)\b', output, re.M)
    if not match:
        raise RuntimeError(f'Cannot establish user-0 enabled state for {package}')
    return int(match[1])


def component_state(component):
    package, activity = component.split('/')
    full_name = package + activity if activity.startswith('.') else activity
    output = shell('dumpsys', 'package', package)
    match = re.search(r'^\s*User 0:.*?(?=^\s*User \d+:|\Z)', output, re.M | re.S)
    if not match:
        raise RuntimeError(f'Cannot establish user-0 component state for {component}')
    for section, state in (('enabledComponents', 1), ('disabledComponents', 2)):
        indent = None
        for line in match[0].splitlines():
            if line.strip() == section + ':':
                indent = len(line) - len(line.lstrip())
                continue
            if indent is not None:
                if line.strip() and len(line) - len(line.lstrip()) <= indent:
                    break
                if line.strip() == full_name:
                    return state
    return 0


def resolve_home():
    output = shell('cmd', 'package', 'resolve-activity', '--brief', '--user', '0',
                   '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
    components = [line.strip() for line in output.splitlines()
                  if re.fullmatch(r'[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+', line.strip())]
    if len(components) != 1:
        raise RuntimeError(f'Cannot establish the current Home component: {output}')
    return components[0]


def write_record(path, record):
    """Replace a recovery record only after its complete contents reach disk."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            json.dump(record, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_device():
    if adb('get-state') != 'device':
        raise RuntimeError('Expected the authorized BOOMAIR device')
    if shell('getprop', 'ro.product.model') != 'BOOMAIR':
        raise RuntimeError('This script is scoped to the BOOMAIR projector')
    if shell('am', 'get-current-user') != '0':
        raise RuntimeError('Expected foreground Android user 0; no changes made')


def mic_granted(package):
    output = shell('dumpsys', 'package', package)
    user = re.search(r'^\s*User 0:.*?(?=^\s*User \d+:|\Z)', output, re.M | re.S)
    match = re.search(re.escape(MIC) + r': granted=(true|false)', user[0] if user else '')
    if not match:
        raise RuntimeError('Cannot establish microphone permission for ' + package)
    return match[1] == 'true'


def reconnect():
    # adbd can become visible before USB re-enumeration has fully settled.
    deadline = time.monotonic() + 20
    stable_since = None
    while time.monotonic() < deadline:
        try:
            verify_device()
            if stable_since is None:
                stable_since = time.monotonic()
            if time.monotonic() - stable_since >= 1.5:
                return
        except (RuntimeError, OSError):
            stable_since = None
        time.sleep(0.5)
    raise RuntimeError('USB device did not reconnect stably within 20 seconds')


def restart_adb(*args):
    try:
        adb(*args)
    except RuntimeError:
        pass  # A successful daemon restart can interrupt its own response.
    reconnect()
    actual = shell('getprop', 'service.adb.tcp.port')
    expected = ('-1', '0') if args[0] == 'usb' else (args[1],)
    if actual not in expected:
        raise RuntimeError('ADB mode change could not be verified')



def disable_package(package, record, path, *, attempts="attempted"):
    """Persist intent before changing a package, then verify the resulting state.

    The two legacy record formats name their attempt lists differently. Keep
    those schemas intact so existing --restore records continue to work.
    """
    record[attempts].append(package)
    write_record(path, record)
    shell('pm', 'disable-user', '--user', '0', package)
    if package_state(package) != 3:
        raise RuntimeError('Package did not enter disabled-user state: ' + package)


def restore_package(package, state):
    if state not in STATE_COMMANDS:
        raise RuntimeError('Invalid prior package state')
    shell('pm', STATE_COMMANDS[state], '--user', '0', package)
    if package_state(package) != state:
        raise RuntimeError('Package restoration failed: ' + package)
