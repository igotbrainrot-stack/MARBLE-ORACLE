"""Media buttons: Bluetooth headsets, keyboard media keys and desktop media controls.

Headset buttons (play/pause, next, previous) reach programs the same way keyboard media
keys do, so Oggcultist listens for those:

- **Windows** — the media keys are registered as system-wide hotkeys (``RegisterHotKey``
  on a small background thread). Windows turns Bluetooth headset (AVRCP) buttons into
  these same keys, so they work while Oggcultist is in the background. No extra software.
- **Linux** — Oggcultist appears as a standard MPRIS media player on D-Bus
  (``org.mpris.MediaPlayer2.oggcultist``). Desktops, BlueZ/PipeWire (headset buttons) and
  media widgets send commands that way, and can show what is playing. Needs the small
  pure-Python ``jeepney`` package; without it this part is simply skipped.
- **Any platform** — while the window has focus, Tk's media key events also work.

Commands arrive on background threads and are handed to Tk through a queue, so the
player is only ever touched from the GUI thread.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from typing import Callable

ACTIONS = ('play_pause', 'play', 'pause', 'next', 'previous', 'stop', 'raise')


# --------------------------------------------------------------------------- Windows
VK_MEDIA = {0xB3: 'play_pause', 0xB0: 'next', 0xB1: 'previous', 0xB2: 'stop'}
WM_HOTKEY, WM_QUIT, MOD_NOREPEAT = 0x0312, 0x0012, 0x4000


class WindowsMediaKeys:
    """System-wide media-key hotkeys on a thread with its own message loop."""

    def __init__(self, emit: Callable[[str], None], user32=None, kernel32=None):
        self.emit = emit
        self._user32, self._kernel32 = user32, kernel32
        self.thread_id = None
        self.registered: list[str] = []
        self.failed: list[str] = []
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name='media-keys')

    def start(self) -> 'WindowsMediaKeys':
        self.thread.start()
        self.ready.wait(2)
        return self

    def _libraries(self):
        if self._user32 is None:
            import ctypes
            self._user32 = ctypes.WinDLL('user32', use_last_error=True)
            self._kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        return self._user32, self._kernel32

    def _get_message(self, user32):
        """Next (message, wParam) for this thread, or None when the loop should end."""
        import ctypes
        from ctypes import wintypes
        msg = wintypes.MSG()
        if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) <= 0:
            return None
        return msg.message, msg.wParam

    def _run(self, get_message=None) -> None:
        user32, kernel32 = self._libraries()
        get_message = get_message or (lambda: self._get_message(user32))
        self.thread_id = kernel32.GetCurrentThreadId()
        ids = {}
        for number, (vk, action) in enumerate(VK_MEDIA.items(), start=1):
            # hWnd None: WM_HOTKEY goes to this thread's message queue
            if user32.RegisterHotKey(None, number, MOD_NOREPEAT, vk):
                ids[number] = action
                self.registered.append(action)
            else:
                self.failed.append(action)        # another program already owns this key
        self.ready.set()
        try:
            while True:
                message = get_message()
                if message is None:
                    break
                kind, wparam = message
                if kind == WM_HOTKEY and wparam in ids:
                    self.emit(ids[wparam])
        finally:
            for number in ids:
                user32.UnregisterHotKey(None, number)

    def stop(self) -> None:
        if self.thread_id is not None and self._user32 is not None:
            self._user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


# --------------------------------------------------------------------------- Linux (MPRIS)
BUS_NAME = 'org.mpris.MediaPlayer2.oggcultist'
OBJECT_PATH = '/org/mpris/MediaPlayer2'
ROOT_IFACE = 'org.mpris.MediaPlayer2'
PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'
PROPS_IFACE = 'org.freedesktop.DBus.Properties'

INTROSPECTION = f'''<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="org.freedesktop.DBus.Introspectable">
    <method name="Introspect"><arg name="xml" type="s" direction="out"/></method>
  </interface>
  <interface name="{PROPS_IFACE}">
    <method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
    <method name="GetAll"><arg type="s" direction="in"/><arg type="a{{sv}}" direction="out"/></method>
    <method name="Set"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/></method>
    <signal name="PropertiesChanged"><arg type="s"/><arg type="a{{sv}}"/><arg type="as"/></signal>
  </interface>
  <interface name="{ROOT_IFACE}">
    <method name="Raise"/><method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/><property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/><property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="{PLAYER_IFACE}">
    <method name="Next"/><method name="Previous"/><method name="Pause"/><method name="PlayPause"/>
    <method name="Stop"/><method name="Play"/>
    <method name="Seek"><arg type="x" direction="in"/></method>
    <method name="SetPosition"><arg type="o" direction="in"/><arg type="x" direction="in"/></method>
    <method name="OpenUri"><arg type="s" direction="in"/></method>
    <property name="PlaybackStatus" type="s" access="read"/><property name="LoopStatus" type="s" access="read"/>
    <property name="Rate" type="d" access="read"/><property name="Shuffle" type="b" access="read"/>
    <property name="Metadata" type="a{{sv}}" access="read"/><property name="Volume" type="d" access="read"/>
    <property name="Position" type="x" access="read"/><property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/><property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/><property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/><property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>'''

PLAYER_METHODS = {'PlayPause': 'play_pause', 'Play': 'play', 'Pause': 'pause', 'Next': 'next',
                  'Previous': 'previous', 'Stop': 'stop'}


def mpris_available() -> bool:
    try:
        import jeepney  # noqa: F401
        return True
    except ImportError:
        return False


class MprisService:
    """A minimal MPRIS player object on the session bus, served from one thread."""

    def __init__(self, emit: Callable[[str], None], bus: str = 'SESSION'):
        self.emit = emit
        self.bus = bus
        self.state = {'status': 'Stopped', 'title': '', 'artist': '', 'album': '', 'length_us': 0,
                      'track': 0, 'loop': 'None', 'shuffle': False, 'volume': 0.8,
                      'position_us': 0, 'position_at': time.monotonic()}
        self._lock = threading.Lock()
        self._outgoing: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self.ready = threading.Event()
        self.error = ''
        self.thread = threading.Thread(target=self._run, daemon=True, name='mpris')

    def start(self) -> 'MprisService':
        self.thread.start()
        self.ready.wait(3)
        return self

    def stop(self) -> None:
        self._stop.set()

    # ---------------------------------------------------------------- state from the GUI
    def update(self, **changes) -> None:
        """Called from the GUI thread; emits PropertiesChanged for what changed."""
        with self._lock:
            before = dict(self.state)
            self.state.update(changes)
            if 'position_us' in changes:
                self.state['position_at'] = time.monotonic()
            after = dict(self.state)
        changed = {}
        if before['status'] != after['status']:
            changed['PlaybackStatus'] = ('s', after['status'])
        if any(before[k] != after[k] for k in ('title', 'artist', 'album', 'length_us', 'track')):
            changed['Metadata'] = ('a{sv}', self._metadata(after))
        if before['loop'] != after['loop']:
            changed['LoopStatus'] = ('s', after['loop'])
        if before['shuffle'] != after['shuffle']:
            changed['Shuffle'] = ('b', after['shuffle'])
        if before['volume'] != after['volume']:
            changed['Volume'] = ('d', float(after['volume']))
        if changed:
            self._outgoing.put(changed)

    @staticmethod
    def _metadata(state) -> dict:
        if not state['title']:
            return {'mpris:trackid': ('o', '/org/mpris/MediaPlayer2/TrackList/NoTrack')}
        return {'mpris:trackid': ('o', f'/org/oggcultist/track/{state["track"]}'),
                'xesam:title': ('s', state['title']),
                'xesam:artist': ('as', [state['artist']] if state['artist'] else []),
                'xesam:album': ('s', state['album']),
                'mpris:length': ('x', int(state['length_us']))}

    def _properties(self, interface: str) -> dict:
        with self._lock:
            state = dict(self.state)
        if interface == ROOT_IFACE:
            return {'CanQuit': ('b', False), 'CanRaise': ('b', True), 'HasTrackList': ('b', False),
                    'Identity': ('s', 'Oggcultist'), 'DesktopEntry': ('s', 'oggcultist'),
                    'SupportedUriSchemes': ('as', []), 'SupportedMimeTypes': ('as', [])}
        if interface == PLAYER_IFACE:
            position = state['position_us']
            if state['status'] == 'Playing':
                position += int((time.monotonic() - state['position_at']) * 1_000_000)
            has_song = bool(state['title'])
            return {'PlaybackStatus': ('s', state['status']), 'LoopStatus': ('s', state['loop']),
                    'Rate': ('d', 1.0), 'Shuffle': ('b', bool(state['shuffle'])),
                    'Metadata': ('a{sv}', self._metadata(state)), 'Volume': ('d', float(state['volume'])),
                    'Position': ('x', int(position)), 'MinimumRate': ('d', 1.0), 'MaximumRate': ('d', 1.0),
                    'CanGoNext': ('b', True), 'CanGoPrevious': ('b', True), 'CanPlay': ('b', True),
                    'CanPause': ('b', has_song), 'CanSeek': ('b', False), 'CanControl': ('b', True)}
        return {}

    # ---------------------------------------------------------------- D-Bus thread
    def _run(self) -> None:
        try:
            from jeepney import DBusAddress, MessageType, new_error, new_method_return, new_signal
            from jeepney.bus_messages import message_bus
            from jeepney.io.blocking import open_dbus_connection
        except ImportError:
            self.error = 'jeepney is not installed'
            self.ready.set()
            return
        try:
            connection = open_dbus_connection(bus=self.bus)
            reply = connection.send_and_get_reply(message_bus.RequestName(BUS_NAME, 4), timeout=3)
            if reply.body[0] not in (1, 4):                    # primary owner / already owner
                self.error = 'another Oggcultist already owns the media controls'
                self.ready.set()
                connection.close()
                return
        except Exception as exc:  # noqa: BLE001 - no session bus etc.: media buttons just stay off
            self.error = f'no D-Bus session bus ({exc})'
            self.ready.set()
            return
        self.ready.set()
        emitter = DBusAddress(OBJECT_PATH, interface=PROPS_IFACE)
        try:
            while not self._stop.is_set():
                while True:
                    try:
                        changed = self._outgoing.get_nowait()
                    except queue.Empty:
                        break
                    connection.send(new_signal(emitter, 'PropertiesChanged', 'sa{sv}as',
                                               (PLAYER_IFACE, changed, [])))
                try:
                    message = connection.receive(timeout=0.2)
                except TimeoutError:
                    continue
                header = message.header
                if header.message_type != MessageType.method_call:
                    continue
                fields = header.fields
                path = fields.get(1)
                interface = fields.get(2)
                member = fields.get(3)
                if path != OBJECT_PATH:
                    connection.send(new_error(message, 'org.freedesktop.DBus.Error.UnknownObject'))
                    continue
                if member == 'Introspect':
                    connection.send(new_method_return(message, 's', (INTROSPECTION,)))
                elif interface == PROPS_IFACE and member == 'Get':
                    iface, name = message.body
                    value = self._properties(iface).get(name)
                    if value is None:
                        connection.send(new_error(message, 'org.freedesktop.DBus.Error.UnknownProperty'))
                    else:
                        connection.send(new_method_return(message, 'v', (value,)))
                elif interface == PROPS_IFACE and member == 'GetAll':
                    connection.send(new_method_return(message, 'a{sv}', (self._properties(message.body[0]),)))
                elif interface == PROPS_IFACE and member == 'Set':
                    connection.send(new_error(message, 'org.freedesktop.DBus.Error.PropertyReadOnly'))
                elif member in PLAYER_METHODS and interface in (PLAYER_IFACE, None):
                    self.emit(PLAYER_METHODS[member])
                    connection.send(new_method_return(message))
                elif member == 'Raise' and interface in (ROOT_IFACE, None):
                    self.emit('raise')
                    connection.send(new_method_return(message))
                elif member in ('Quit', 'Seek', 'SetPosition', 'OpenUri'):
                    connection.send(new_method_return(message))          # accepted, not supported
                else:
                    connection.send(new_error(message, 'org.freedesktop.DBus.Error.UnknownMethod'))
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass


# --------------------------------------------------------------------------- glue for the app
TK_KEYS = {'<XF86AudioPlay>': 'play_pause', '<XF86AudioPause>': 'pause', '<XF86AudioNext>': 'next',
           '<XF86AudioPrev>': 'previous', '<XF86AudioStop>': 'stop'}


class MediaControls:
    """Starts the platform backend and runs its commands on the Tk thread."""

    def __init__(self, app):
        self.app = app
        self.commands: queue.Queue = queue.Queue()
        self.windows: WindowsMediaKeys | None = None
        self.mpris: MprisService | None = None
        self.status = 'off'
        self._stopped = False
        self._poll_job = None

    def start(self) -> 'MediaControls':
        for sequence, action in TK_KEYS.items():
            try:
                self.app.bind_all(sequence, lambda _e, a=action: self.commands.put(a))
            except Exception:  # noqa: BLE001 - keysym unknown on this platform
                pass
        if sys.platform == 'win32':
            try:
                self.windows = WindowsMediaKeys(self.commands.put).start()
                self.status = ('on: ' + ', '.join(self.windows.registered)) if self.windows.registered else 'unavailable'
            except Exception as exc:  # noqa: BLE001
                self.status = f'unavailable ({exc})'
        elif sys.platform.startswith('linux') and mpris_available():
            self.mpris = MprisService(self.commands.put).start()
            self.status = 'on (MPRIS)' if not self.mpris.error else f'unavailable ({self.mpris.error})'
        self._poll_job = self.app.after(60, self._poll)
        return self

    def _poll(self) -> None:
        self._poll_job = None
        if self._stopped:
            return
        try:
            while True:
                self.run(self.commands.get_nowait())
        except queue.Empty:
            pass
        try:
            if not self._stopped:
                self._poll_job = self.app.after(60, self._poll)
        except Exception:  # noqa: BLE001 - window closed
            pass

    def run(self, action: str) -> None:
        player = self.app.player
        transport = player.transport
        if action == 'play_pause':
            player.toggle()
        elif action == 'play':
            if not transport.playing:
                player.toggle()
        elif action == 'pause':
            if transport.playing:
                player.toggle()
        elif action == 'next':
            player.next()
        elif action == 'previous':
            player.previous()
        elif action == 'stop':
            player.stop()
        elif action == 'raise':
            try:
                self.app.deiconify()
                self.app.lift()
                self.app.focus_force()
            except Exception:  # noqa: BLE001
                pass

    def publish(self) -> None:
        """Share the current song and state with the desktop (MPRIS)."""
        if self.mpris is None or self.mpris.error:
            return
        player = self.app.player
        transport = player.transport
        song = transport.song
        status = 'Playing' if transport.playing else ('Paused' if transport.paused and song else 'Stopped')
        self.mpris.update(status=status,
                          title=song.title if song else '', artist=song.display_artist if song else '',
                          album=song.album if song else '',
                          length_us=int((song.duration or 0) * 1_000_000) if song else 0,
                          track=abs(hash(str(song.path))) % 10**9 if song else 0,
                          loop={'off': 'None', 'all': 'Playlist', 'album': 'Playlist', 'one': 'Track'}[player.repeat],
                          shuffle=player.shuffle, volume=int(self.app.volume.get()) / 100,
                          position_us=int(transport.current_position() * 1_000_000))

    def stop(self) -> None:
        self._stopped = True
        if self._poll_job is not None:
            try:
                self.app.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None
        if self.windows is not None:
            self.windows.stop()
        if self.mpris is not None:
            self.mpris.stop()
