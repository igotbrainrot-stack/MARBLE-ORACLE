"""Live CPU and GPU readings for the right CRT instrument.

CPU usage is read on the UI thread (Linux /proc or Windows GetSystemTimes).
Temperatures and the GPU are refreshed on a background thread so the window
never waits on nvidia-smi or WMI. A missing sensor stays None. Nothing here
is invented.
"""
import os
import subprocess
import threading
import time

_cpu_last = None
_lock = threading.Lock()
_slow = {"cpu_c": None, "gpu_c": None, "gpu_u": None}
_started = False


def cpu_percent():
    """Return 0..1 CPU usage, or None if this OS cannot be read."""
    if os.name == "nt":
        return _win_cpu()
    return _linux_cpu()


def _linux_cpu():
    global _cpu_last
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        if parts[0] != "cpu":
            return None
        vals = list(map(int, parts[1:]))
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        now = time.time()
        prev = _cpu_last
        _cpu_last = (idle, total, now)
        if prev is None or now <= prev[2]:
            return 0.0
        d_idle = idle - prev[0]
        d_total = total - prev[1]
        if d_total <= 0:
            return None
        return max(0.0, min(1.0, 1.0 - d_idle / d_total))
    except Exception:
        return None


def _win_cpu():
    global _cpu_last
    try:
        import ctypes
        from ctypes import wintypes

        class FT(ctypes.Structure):
            _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

        idle, kern, user = FT(), FT(), FT()
        if not ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
            return None

        def ticks(ft):
            return (ft.hi << 32) | ft.lo

        # Kernel time already includes idle time.
        idle_t = ticks(idle)
        total = ticks(kern) + ticks(user)
        now = time.time()
        prev = _cpu_last
        _cpu_last = (idle_t, total, now)
        if prev is None or total <= prev[1]:
            return 0.0
        d_total = total - prev[1]
        d_idle = idle_t - prev[0]
        if d_total <= 0:
            return None
        return max(0.0, min(1.0, 1.0 - d_idle / d_total))
    except Exception:
        return None


def cpu_temp_c():
    """Celsius, or None. Starts the background reader on first call."""
    _ensure()
    with _lock:
        return _slow["cpu_c"]


def gpu_temp_c():
    _ensure()
    with _lock:
        return _slow["gpu_c"]


def gpu_util():
    """0..1 GPU usage, or None."""
    _ensure()
    with _lock:
        return _slow["gpu_u"]


def _ensure():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="oracle-sensors", daemon=True).start()


def _loop():
    while True:
        cpu_c = _read_cpu_temp()
        gpu_c, gpu_u = _read_gpu()
        with _lock:
            _slow["cpu_c"] = cpu_c
            _slow["gpu_c"] = gpu_c
            _slow["gpu_u"] = gpu_u
        time.sleep(1.6)


def _run(args):
    kw = {"timeout": 4, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.check_output(args, **kw)


def _read_cpu_temp():
    try:
        if os.name != "nt" and os.path.isdir("/sys/class/thermal"):
            best = None
            for name in os.listdir("/sys/class/thermal"):
                path = os.path.join("/sys/class/thermal", name, "temp")
                if not os.path.isfile(path):
                    continue
                raw = int(open(path).read().strip() or 0)
                c = raw / 1000.0 if raw > 1000 else float(raw)
                if 15.0 < c < 115.0:
                    best = c if best is None else max(best, c)
            if best is not None:
                return best
        if os.name == "nt":
            out = _run([
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
                "-ErrorAction SilentlyContinue | Select-Object -First 1 "
                "-ExpandProperty CurrentTemperature)",
            ])
            text = out.decode("utf-8", "replace").strip()
            if text.isdigit():
                c = int(text) / 10.0 - 273.15
                if 15.0 < c < 115.0:
                    return c
    except Exception:
        return None
    return None


def _nvidia_bins():
    found = ["nvidia-smi"]
    if os.name == "nt":
        found += [
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        ]
    return found


def _read_gpu():
    for exe in _nvidia_bins():
        try:
            out = _run([
                exe, "--query-gpu=temperature.gpu,utilization.gpu",
                "--format=csv,noheader,nounits",
            ])
            line = out.decode("utf-8", "replace").strip().splitlines()
            if not line:
                continue
            temp_s, util_s = [p.strip() for p in line[0].split(",")[:2]]
            temp = None
            util = None
            if temp_s not in ("", "[N/A]", "N/A"):
                temp = float(temp_s)
            if util_s not in ("", "[N/A]", "N/A"):
                util = max(0.0, min(1.0, float(util_s) / 100.0))
            if temp is not None or util is not None:
                return temp, util
        except Exception:
            continue
    if os.name != "nt":
        return _linux_gpu()
    return _win_gpu_counter()


def _linux_gpu():
    import glob
    temp = None
    util = None
    try:
        for path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
            util = max(0.0, min(1.0, int(open(path).read()) / 100.0))
            break
        for path in glob.glob("/sys/class/drm/card*/device/hwmon/hwmon*/temp1_input"):
            raw = int(open(path).read())
            c = raw / 1000.0 if raw > 200 else float(raw)
            if 15.0 < c < 115.0:
                temp = c
                break
    except Exception:
        return None, None
    return temp, util


def _win_gpu_counter():
    """GPU 3D-engine usage on Windows when nvidia-smi is not installed."""
    try:
        out = _run([
            "powershell", "-NoProfile", "-Command",
            "$s = (Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage' "
            "-ErrorAction SilentlyContinue).CounterSamples; "
            "if ($s) { [int][math]::Min(100, ($s | Measure-Object CookedValue -Sum).Sum) }",
        ])
        text = out.decode("utf-8", "replace").strip()
        if text.isdigit():
            return None, max(0.0, min(1.0, int(text) / 100.0))
    except Exception:
        return None, None
    return None, None


def memory_percent():
    """Return 0..1 memory used, or None."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class MEM(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]
            m = MEM()
            m.dwLength = ctypes.sizeof(MEM)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return None
            return max(0.0, min(1.0, m.dwMemoryLoad / 100.0))
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0])
        total = info.get("MemTotal", 0)
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        if total <= 0:
            return None
        return max(0.0, min(1.0, 1.0 - avail / total))
    except Exception:
        return None
