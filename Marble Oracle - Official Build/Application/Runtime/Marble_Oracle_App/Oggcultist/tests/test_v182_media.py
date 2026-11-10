"""v1.8.2: media buttons (Bluetooth headsets, media keys) control Oggcultist.

- Windows: the hotkey thread is driven by a fake user32, so registration, a key already
  owned by another program, message handling and clean-up are checked on any OS.
- Linux: a private D-Bus daemon is started and the MPRIS player object is called exactly
  as a desktop / BlueZ headset bridge would (needs dbus-daemon and jeepney).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

import pytest

from oggcultist.gui import media_keys
from oggcultist.gui.media_keys import (BUS_NAME, OBJECT_PATH, PLAYER_IFACE, PROPS_IFACE, WM_HOTKEY,
                                       MprisService, WindowsMediaKeys)


# ---------------------------------------------------------------------------- Windows
class FakeUser32:
    def __init__(self, taken=()):
        self.taken = set(taken)
        self.registered, self.unregistered, self.posted = {}, [], []

    def RegisterHotKey(self, hwnd, number, modifiers, vk):
        assert hwnd is None and modifiers & 0x4000            # thread queue, no auto-repeat
        if vk in self.taken:
            return 0
        self.registered[number] = vk
        return 1

    def UnregisterHotKey(self, hwnd, number):
        self.unregistered.append(number)
        return 1

    def PostThreadMessageW(self, thread_id, message, wparam, lparam):
        self.posted.append((thread_id, message))
        return 1


class FakeKernel32:
    def GetCurrentThreadId(self):
        return 4242


def test_windows_hotkeys_register_dispatch_and_clean_up():
    user32 = FakeUser32(taken={0xB2})                          # Stop is owned by another program
    emitted = []
    keys = WindowsMediaKeys(emitted.append, user32=user32, kernel32=FakeKernel32())
    messages = iter([None])

    def feed():
        return next(messages)
    # register first, then feed the hotkey messages Windows would post
    keys._libraries = lambda: (user32, FakeKernel32())
    original = keys._run

    def run():
        nonlocal messages
        messages = iter([(WM_HOTKEY, 1), (0x0200, 0), (WM_HOTKEY, 2), (WM_HOTKEY, 3), (WM_HOTKEY, 99), None])
        original(get_message=feed)
    run()
    assert keys.registered == ['play_pause', 'next', 'previous'] and keys.failed == ['stop']
    assert emitted == ['play_pause', 'next', 'previous']        # unknown ids and other messages ignored
    assert sorted(user32.unregistered) == sorted(user32.registered)   # hotkeys released on exit
    keys.stop()
    assert user32.posted == [(4242, 0x0012)]                    # WM_QUIT ends the loop


# ---------------------------------------------------------------------------- Linux MPRIS
jeepney = pytest.importorskip('jeepney') if shutil.which('dbus-daemon') else None
needs_dbus = pytest.mark.skipif(not shutil.which('dbus-daemon') or jeepney is None, reason='needs dbus-daemon and jeepney')


@pytest.fixture
def session_bus(monkeypatch):
    daemon = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                              stdout=subprocess.PIPE, text=True)
    address = daemon.stdout.readline().strip()
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', address)
    yield address
    daemon.terminate()
    daemon.wait(timeout=5)


def _call(connection, interface, member, signature=None, body=()):
    from jeepney import DBusAddress, new_method_call
    address = DBusAddress(OBJECT_PATH, bus_name=BUS_NAME, interface=interface)
    reply = connection.send_and_get_reply(new_method_call(address, member, signature, body), timeout=3)
    return reply.body


@needs_dbus
def test_mpris_player_receives_headset_commands_and_publishes_state(session_bus):
    from jeepney.io.blocking import open_dbus_connection
    emitted = []
    service = MprisService(emitted.append).start()
    assert not service.error and service.thread.is_alive()
    client = open_dbus_connection(bus='SESSION')
    try:
        for member in ('PlayPause', 'Next', 'Previous', 'Pause', 'Play', 'Stop'):
            _call(client, PLAYER_IFACE, member)
        assert emitted == ['play_pause', 'next', 'previous', 'pause', 'play', 'stop']
        assert _call(client, PROPS_IFACE, 'Get', 'ss', (PLAYER_IFACE, 'PlaybackStatus')) == (('s', 'Stopped'),)
        service.update(status='Playing', title='Gulls', artist='Harbour Lights', album='Morning Tide',
                       length_us=4_000_000, track=7, loop='Track', shuffle=True, position_us=1_000_000)
        props = _call(client, PROPS_IFACE, 'GetAll', 's', (PLAYER_IFACE,))[0]
        assert props['PlaybackStatus'] == ('s', 'Playing') and props['LoopStatus'] == ('s', 'Track')
        assert props['Shuffle'] == ('b', True) and props['CanControl'] == ('b', True)
        metadata = props['Metadata'][1]
        assert metadata['xesam:title'] == ('s', 'Gulls') and metadata['xesam:artist'] == ('as', ['Harbour Lights'])
        assert metadata['mpris:length'] == ('x', 4_000_000)
        assert props['Position'][1] >= 1_000_000
        root = _call(client, PROPS_IFACE, 'GetAll', 's', ('org.mpris.MediaPlayer2',))[0]
        assert root['Identity'] == ('s', 'Oggcultist') and root['CanRaise'] == ('b', True)
        assert 'org.mpris.MediaPlayer2.Player' in _call(client, 'org.freedesktop.DBus.Introspectable', 'Introspect')[0]
        _call(client, 'org.mpris.MediaPlayer2', 'Raise')
        assert emitted[-1] == 'raise'
    finally:
        client.close()
        service.stop()
        service.thread.join(3)


@needs_dbus
def test_mpris_announces_changes_with_properties_changed(session_bus):
    from jeepney import MatchRule
    from jeepney.bus_messages import message_bus
    from jeepney.io.blocking import open_dbus_connection
    service = MprisService(lambda action: None).start()
    client = open_dbus_connection(bus='SESSION')
    try:
        rule = MatchRule(type='signal', interface=PROPS_IFACE, member='PropertiesChanged', path=OBJECT_PATH)
        client.send_and_get_reply(message_bus.AddMatch(rule), timeout=3)
        service.update(status='Paused', title='Salt Road', album='Morning Tide')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            message = client.receive(timeout=1)
            if message.header.fields.get(3) == 'PropertiesChanged':
                interface, changed, _ = message.body
                assert interface == PLAYER_IFACE
                assert changed['PlaybackStatus'] == ('s', 'Paused')
                assert changed['Metadata'][1]['xesam:title'] == ('s', 'Salt Road')
                break
        else:
            pytest.fail('no PropertiesChanged signal')
    finally:
        client.close()
        service.stop()
        service.thread.join(3)


@needs_dbus
def test_dbus_send_from_the_command_line_controls_the_player(session_bus):
    """The same route a desktop or `playerctl` / BlueZ mpris-proxy uses."""
    emitted = []
    service = MprisService(emitted.append).start()
    try:
        for member in ('PlayPause', 'Next'):
            subprocess.run(['dbus-send', '--session', '--print-reply', f'--dest={BUS_NAME}', OBJECT_PATH,
                            f'{PLAYER_IFACE}.{member}'], check=True, capture_output=True, timeout=5,
                           env=dict(os.environ))
        assert emitted == ['play_pause', 'next']
    finally:
        service.stop()
        service.thread.join(3)


def test_without_a_session_bus_media_buttons_stay_off_quietly(monkeypatch):
    if not media_keys.mpris_available():
        pytest.skip('jeepney not installed')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/nonexistent/oggcultist-test-bus')
    service = MprisService(lambda action: None).start()
    assert service.error and not service.thread.is_alive()
