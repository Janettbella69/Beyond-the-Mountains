#!/usr/bin/env python3
"""ue_py.py — 把 python 代码发进正在运行的 UE 编辑器执行（走 PL exec bridge :8003）。

前提：编辑器已启动，Content/Python/init_unreal.py 的 bridge 已监听。
用法:
  ue_py.py 'print(unreal.SystemLibrary.get_engine_version())'
  ue_py.py --file build_scene.py
  cat snippet.py | ue_py.py -
环境变量: UE_PY_URL (默认 http://127.0.0.1:8003/exec), UE_PY_TIMEOUT (默认 180s)
退出码: 0 成功；1 编辑器内执行报错；2 连不上 bridge
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("UE_PY_URL", "http://127.0.0.1:8003/exec")
TIMEOUT = float(os.environ.get("UE_PY_TIMEOUT", "180"))


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[1] == "--file" and len(argv) >= 3:
        code = open(argv[2]).read()
    elif argv[1] == "-":
        code = sys.stdin.read()
    else:
        code = argv[1]

    req = urllib.request.Request(
        URL,
        data=json.dumps({"code": code, "timeout": TIMEOUT - 5}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    except (urllib.error.URLError, OSError) as e:
        print(f"[ue_py] cannot reach bridge at {URL}: {e}", file=sys.stderr)
        print("[ue_py] 编辑器没开？或 init_unreal.py 没生效（需重启编辑器）", file=sys.stderr)
        return 2
    out = json.loads(resp.read().decode())
    sys.stdout.write(out.get("out", ""))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
