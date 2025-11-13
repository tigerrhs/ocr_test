# -*- coding: utf-8 -*-
import os, sys, importlib

# PyInstaller onedir 배포 시, 실행파일 위치 기준으로 경로 계산
BASE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
PLUGINS = os.path.join(BASE, "plugins")
ENTRY = os.path.join(BASE, "entrypoint.txt")

# plugins 경로를 우선 import path에 추가
if os.path.isdir(PLUGINS):
    sys.path.insert(0, PLUGINS)

# 코어 앱 불러오기 (uniocr.py)
import uniocr
app = uniocr.app

# entrypoint.txt 에 나열된 플러그인 로드
if os.path.exists(ENTRY):
    with open(ENTRY, "r", encoding="utf-8") as f:
        raw = f.read()
    plugin_names = [s.strip() for s in raw.replace(",", "\n").splitlines() if s.strip()]
else:
    plugin_names = []

for name in plugin_names:
    try:
        mod = importlib.import_module(name)
        if hasattr(mod, "create_app"):
            app = mod.create_app()
        elif hasattr(mod, "register"):
            mod.register(app)
    except Exception as e:
        print(f"[플러그인] plugin {name} load failed:", e)

if __name__ == "__main__":
    uniocr.make_db()
    openport = uniocr.lb.open_port()
    uniocr.run(host="0.0.0.0", port=openport)