"""macOS Spaces/full-screen policy for the overlay's Qt tool panel.

Use only public AppKit APIs via the system Objective-C runtime. Other platforms
and Qt's offscreen test platform do not load native libraries or touch winId().
"""
from __future__ import annotations

import ctypes
from functools import lru_cache
import platform
import sys

CAN_JOIN_ALL_SPACES = 1 << 0
MOVE_TO_ACTIVE_SPACE = 1 << 1
FULL_SCREEN_PRIMARY = 1 << 7
FULL_SCREEN_AUXILIARY = 1 << 8
FULL_SCREEN_NONE = 1 << 9
FULL_SCREEN_ALLOWS_TILING = 1 << 11
FULL_SCREEN_DISALLOWS_TILING = 1 << 12
PRIMARY = 1 << 16
AUXILIARY = 1 << 17
CAN_JOIN_ALL_APPLICATIONS = 1 << 18
NONACTIVATING_PANEL = 1 << 7


def collection_behavior(current: int, major_version: int) -> int:
    """Remove mutually exclusive policies before opting into all Spaces."""
    incompatible = (MOVE_TO_ACTIVE_SPACE | FULL_SCREEN_PRIMARY | FULL_SCREEN_NONE |
                    FULL_SCREEN_ALLOWS_TILING | PRIMARY | AUXILIARY)
    behavior = (current & ~incompatible) | CAN_JOIN_ALL_SPACES | FULL_SCREEN_AUXILIARY | FULL_SCREEN_DISALLOWS_TILING
    if major_version >= 13:
        behavior |= CAN_JOIN_ALL_APPLICATIONS
    else:
        behavior &= ~CAN_JOIN_ALL_APPLICATIONS
    return behavior


class _ObjC:
    def __init__(self):
        self.lib = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        self.lib.sel_registerName.argtypes = [ctypes.c_char_p]
        self.lib.sel_registerName.restype = ctypes.c_void_p

    @lru_cache(maxsize=32)
    def selector(self, name):
        return self.lib.sel_registerName(name.encode('ascii'))

    @lru_cache(maxsize=16)
    def signature(self, result, arguments):
        # Each signature has an independent callable, avoiding mutable global
        # objc_msgSend argtypes. NSUInteger/NSInteger match 64-bit Cocoa's ABI.
        return ctypes.CFUNCTYPE(result, ctypes.c_void_p, ctypes.c_void_p, *arguments)(('objc_msgSend', self.lib))

    def send(self, receiver, name, result=ctypes.c_void_p, arguments=(), values=()):
        return self.signature(result, arguments)(receiver, self.selector(name), *values)


@lru_cache(maxsize=1)
def _runtime():
    return _ObjC()


def configure_overlay(widget) -> bool:
    from aqt.qt import QApplication
    if sys.platform != 'darwin' or QApplication.platformName() != 'cocoa':
        return False
    api = _runtime()
    # QWidget.winId() on Cocoa is an NSView pointer, never an NSWindow pointer.
    window = api.send(int(widget.winId()), 'window')
    if not window:
        return False
    if not api.send(window, 'respondsToSelector:', ctypes.c_bool, (ctypes.c_void_p,),
                    (api.selector('setFloatingPanel:'),)):
        raise RuntimeError('Overlay native window is not an NSPanel')
    # A regular activating tool panel is still owned by Anki's app group.
    # Nonactivating panels are eligible to join another app's full-screen Space
    # and can accept keys without activating Anki's full-screen main window.
    style = api.send(window, 'styleMask', ctypes.c_ulong)
    if not style & NONACTIVATING_PANEL:
        api.send(window, 'setStyleMask:', None, (ctypes.c_ulong,), (style | NONACTIVATING_PANEL,))
    api.send(window, 'setFloatingPanel:', None, (ctypes.c_bool,), (True,))
    api.send(window, 'setBecomesKeyOnlyIfNeeded:', None, (ctypes.c_bool,), (False,))
    current = api.send(window, 'collectionBehavior', ctypes.c_ulong)
    major = int(platform.mac_ver()[0].split('.')[0])
    behavior = collection_behavior(current, major)
    if behavior != current:
        api.send(window, 'setCollectionBehavior:', None, (ctypes.c_ulong,), (behavior,))
    # Qt::Tool creates NSPanel; keep it visible when another app is active.
    api.send(window, 'setHidesOnDeactivate:', None, (ctypes.c_bool,), (False,))
    api.send(window, 'setCanHide:', None, (ctypes.c_bool,), (False,))
    level = api.send(window, 'level', ctypes.c_long)
    # setFloatingPanel: may reset level to 3. Qt lowers level-3 tool windows
    # on app deactivation, so retain its WindowStaysOnTop level (8) instead.
    if level < 8:
        api.send(window, 'setLevel:', None, (ctypes.c_long,), (8,))
    return True


def window_status(widget) -> dict:
    """Local, content-free diagnostics for full-screen visibility/focus."""
    from aqt.qt import QApplication
    if sys.platform != 'darwin' or QApplication.platformName() != 'cocoa':
        return {}
    api = _runtime()
    window = api.send(int(widget.winId()), 'window')
    if not window:
        return {}
    status = {
        name: api.send(window, selector, result)
        for name, selector, result in (
            ('style', 'styleMask', ctypes.c_ulong),
            ('behavior', 'collectionBehavior', ctypes.c_ulong),
            ('level', 'level', ctypes.c_long),
            ('visible', 'isVisible', ctypes.c_bool),
            ('active_space', 'isOnActiveSpace', ctypes.c_bool),
            ('key', 'isKeyWindow', ctypes.c_bool),
            ('hides_on_deactivate', 'hidesOnDeactivate', ctypes.c_bool),
        )
    }
    from aqt.qt import Qt
    status['app_active'] = QApplication.instance().applicationState() == Qt.ApplicationState.ApplicationActive
    return status


def has_keyboard_focus(widget) -> bool:
    from aqt.qt import QApplication
    if sys.platform != 'darwin' or QApplication.platformName() != 'cocoa':
        return False
    api = _runtime()
    window = api.send(int(widget.winId()), 'window')
    return bool(window and api.send(window, 'isKeyWindow', ctypes.c_bool))


def focus_overlay(widget) -> bool:
    """Make only the panel key; do not activate Anki or switch its main Space."""
    from aqt.qt import QApplication
    if sys.platform != 'darwin' or QApplication.platformName() != 'cocoa':
        return False
    api = _runtime()
    view = int(widget.winId())
    window = api.send(view, 'window')
    if not window:
        return False
    api.send(window, 'makeKeyWindow', None)
    api.send(window, 'makeFirstResponder:', ctypes.c_bool, (ctypes.c_void_p,), (view,))
    return bool(api.send(window, 'isKeyWindow', ctypes.c_bool))
