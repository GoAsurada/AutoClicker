"""Safe device listing for the add-instance dialog.

The normal list action must never run adb connect against unrelated local
services. A full emulator-port scan is an explicit user action.
"""


def discover_devices(clicker, scan_ports=False):
    """Return online serials; probe emulator ports only on explicit request."""
    if scan_ports:
        return clicker.get_connected_devices()

    if not clicker._ensure_adb_server():
        return []

    result = clicker._run_adb_stage("디바이스 목록 조회", ["devices"])
    if result is None:
        return []

    online = []
    for line in (result.stdout or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            online.append(parts[0])
    return clicker.normalize_device_serials(online)
