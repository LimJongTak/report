"""한컴오피스 자동화(COM) 도우미 — ING-03, OUT-04.

Windows + 한컴오피스(2020 이상)가 설치되어 있을 때만 동작한다.
COM 호출은 별도 프로세스에서 실행해 Streamlit 스레드/COM 초기화 문제를 피한다.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import config

_WORKER = r'''
import sys, json, pythoncom, win32com.client as w
pythoncom.CoInitialize()
args = json.loads(sys.argv[1])
res = {"ok": False}
hwp = None
try:
    if args.get("dll"):
        # 한컴 공식 보안 모듈(FilePathCheckerModule) 등록 → 파일 접근 승인 창 없이 자동화
        import winreg
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation\Modules")
        winreg.SetValueEx(k, "FilePathCheckerModule", 0, winreg.REG_SZ, args["dll"])
        winreg.CloseKey(k)
    hwp = w.Dispatch("HWPFrame.HwpObject")
    try:
        res["module"] = bool(hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"))
    except Exception:
        pass
    try:
        hwp.XHwpWindows.Item(0).Visible = bool(args.get("visible"))
    except Exception:
        pass
    hwp.SetMessageBoxMode(0x00020021)
    if args["op"] == "probe":
        res = {"ok": True, "version": str(hwp.Version), "module": res.get("module", False)}
    else:
        fmt_in = {"hwp": "HWP", "hwpx": "HWPX"}.get(args["src"].rsplit(".", 1)[-1].lower(), "")
        if not hwp.Open(args["src"], fmt_in, "forceopen:true"):
            res = {"ok": False, "error": "파일 열기 실패"}
        else:
            if args["op"] == "text":
                hwp.InitScan(); out = []
                while True:
                    st, t = hwp.GetText()
                    if st in (0, 1):
                        break
                    out.append(t)
                hwp.ReleaseScan()
                res = {"ok": True, "text": "".join(out)}
            else:
                ok = hwp.SaveAs(args["dst"], args["fmt"], "")
                res = {"ok": bool(ok)}
except Exception as e:
    res = {"ok": False, "error": repr(e)}
finally:
    try:
        if hwp is not None:
            hwp.Clear(1)
            hwp.Quit()
    except Exception:
        pass
sys.stdout.write(json.dumps(res, ensure_ascii=False))
'''


SECURITY_HELP = (
    "한컴오피스가 '파일 접근 허용' 보안 창을 띄우고 기다리는 중일 수 있습니다. "
    "창이 보이면 [접근 허용] 또는 [모두 허용]을 누르세요. 매번 묻지 않게 하려면 한컴 개발자센터의 "
    "보안모듈(FilePathCheckerModule.dll)을 받아 config/settings.yaml의 hancom.security_module_dll에 경로를 넣으세요."
)


def _hwp_pids() -> set[int]:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Hwp.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=20).stdout
        return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"Hwp')}
    except Exception:  # noqa: BLE001
        return set()


def _run(args: dict, timeout: int | None = None) -> dict:
    if sys.platform != "win32":
        return {"ok": False, "error": "Windows 전용 기능"}
    timeout = timeout or int(config.get("hancom.timeout", 120))
    args = {**args, "dll": config.get("hancom.security_module_dll") or "", "visible": bool(config.get("hancom.visible", False))}
    before = _hwp_pids()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        cp = subprocess.run(
            [sys.executable, "-c", _WORKER, json.dumps(args, ensure_ascii=False)],
            capture_output=True, timeout=timeout, encoding="utf-8", errors="replace", env=env,
        )
        return json.loads(cp.stdout.strip() or '{"ok": false, "error": "응답 없음"}')
    except subprocess.TimeoutExpired:
        # 이 작업이 띄운 한글 프로세스만 정리
        for pid in _hwp_pids() - before:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        return {"ok": False, "error": "한컴 응답 시간 초과. " + SECURITY_HELP}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e)}


_available: bool | None = None


def available() -> bool:
    """한컴오피스 자동화 사용 가능 여부(결과 캐시)."""
    global _available
    if _available is None:
        _available = bool(_run({"op": "probe"}, timeout=60).get("ok"))
    return _available


def probe() -> dict:
    return _run({"op": "probe"}, timeout=60)


def convert(src: str | Path, dst: str | Path, fmt: str) -> dict:
    """한컴으로 다른 형식 저장. fmt: HWPX | PDF | HWP"""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    global _available
    res = _run({"op": "save", "src": str(Path(src).resolve()), "dst": str(Path(dst).resolve()), "fmt": fmt})
    res["ok"] = bool(res.get("ok")) and Path(dst).exists()
    if "시간 초과" in str(res.get("error", "")):
        _available = False   # 이번 실행 동안은 한컴 경로를 건너뛰고 대체 경로 사용
    return res


def hwp_to_hwpx(src, dst) -> dict:
    return convert(src, dst, "HWPX")


def to_pdf(src, dst) -> dict:
    return convert(src, dst, "PDF")
