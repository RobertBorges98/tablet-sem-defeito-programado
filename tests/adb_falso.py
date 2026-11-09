"""ADB falso que simula um Galaxy Tab para os testes (não precisa de aparelho)."""
import json
import os
import sys
from pathlib import Path

ESTADO = Path(os.environ["ADB_FALSO_ESTADO"])
PACOTES_INICIAIS = {
    "android": True, "com.android.systemui": True, "com.android.settings": True,
    "com.google.android.gms": True, "com.android.vending": True,
    "com.dti.samsung": True, "com.facebook.appmanager": True, "com.facebook.services": True,
    "com.samsung.android.game.gos": True, "com.wssyncmldm": True,
    "com.samsung.android.bixby.agent": True, "com.sec.unknown.vendorapp": True,
    "com.whatsapp": True, "com.android.theme.icon.pebble": True,
}
USUARIO = {"com.whatsapp"}


def carregar():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return {"instalado": PACOTES_INICIAIS, "anim": "1.0"}


def salvar(e):
    ESTADO.write_text(json.dumps(e))


def shell(cmd: str, e: dict) -> str:
    props = {"ro.product.manufacturer": "samsung", "ro.product.model": "SM-X200",
             "ro.product.device": "gta8wifi", "ro.build.version.release": "14",
             "ro.build.version.sdk": "34", "ro.build.version.security_patch": "2023-05-01",
             "ro.product.cpu.abi": "arm64-v8a", "ro.board.platform": "ums512",
             "ro.build.display.id": "TESTE"}
    p = cmd.split()
    if p[0] == "getprop":
        return props.get(p[1], "")
    if cmd.startswith("pm list packages"):
        flag = p[3] if len(p) > 3 else ""
        inst = e["instalado"]
        if flag == "-u":
            nomes = list(inst)
        elif flag == "-e":
            nomes = [n for n, ok in inst.items() if ok is True]
        elif flag == "-d":
            nomes = [n for n, ok in inst.items() if ok == "off"]
        elif flag == "-s":
            nomes = [n for n in inst if n not in USUARIO]
        else:
            nomes = [n for n, ok in inst.items() if ok]
        return "\n".join(f"package:{n}" for n in nomes)
    if cmd.startswith("pm uninstall"):
        e["instalado"][p[-1]] = False
        return "Success"
    if cmd.startswith("pm disable-user"):
        e["instalado"][p[-1]] = "off"
        return f"Package {p[-1]} new state: disabled-user"
    if cmd.startswith("pm enable"):
        e["instalado"][p[-1]] = True
        return f"Package {p[-1]} new state: enabled"
    if "install-existing" in cmd:
        e["instalado"][p[-1]] = True
        return f"Package {p[-1]} installed for user: 0"
    if cmd == "cat /proc/meminfo":
        return "MemTotal:        3500000 kB\nMemFree:  100000 kB\nMemAvailable:    1400000 kB\nSwapTotal: 2000000 kB\nSwapFree: 1000000 kB"
    if cmd.startswith("df"):
        return "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-9 52000000 46000000 6000000 89% /data"
    if cmd == "dumpsys battery":
        return "Current Battery Service state:\n  level: 80\n  health: 2\n  temperature: 315\n  voltage: 4100"
    if cmd.startswith("settings get"):
        return e["anim"]
    if cmd.startswith("settings put"):
        e["anim"] = p[-1]
        return ""
    if "query-receivers" in cmd:
        return "com.dti.samsung/.BootReceiver\ncom.whatsapp/.Boot\ncom.android.systemui/.Boot"
    if cmd == "dumpsys meminfo":
        return ("Applications Memory Usage (in Kilobytes):\n\nTotal PSS by process:\n"
                "    300,000K: com.android.systemui (pid 1000)\n    150,000K: com.facebook.services (pid 2000)\n\n"
                "Total PSS by OOM adjustment:\n")
    if "am start -W" in cmd:
        return "Status: ok\nTotalTime: 850\nWaitTime: 900"
    return ""


def main():
    a = sys.argv[1:]
    if a[:1] == ["-s"]:
        a = a[2:]
    if a == ["devices"]:
        print("List of devices attached\nR9TESTE123\tdevice\n")
        return
    if a[:1] == ["shell"]:
        e = carregar()
        print(shell(a[1], e))
        salvar(e)


if __name__ == "__main__":
    main()
