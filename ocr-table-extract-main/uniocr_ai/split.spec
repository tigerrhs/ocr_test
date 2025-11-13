# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],  # 실행 엔트리
    pathex=[],
    binaries=[],
    datas=[
        ('entrypoint.txt', '.'),  # entrypoint.txt를 실행 폴더에 포함
    ],
    hiddenimports=[
        'uniocr',
        'sqlite3',
        'jpype',
        'yaml',
        'reportlab', 'reportlab.pdfgen.canvas',
        'pdfrw', 'pdfrw.toreportlab',
        'fitz',
        'cv2',
        'torch', 'torch._utils', 'torch.nn', 'torch.nn.functional', 'torch.autograd',
        'easydict',
        'skimage.io',
        'detectron2', 'detectron2.config', 'detectron2.engine.defaults'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch._dynamo',
        'torch._inductor',
        'torch.utils.tensorboard',
        'torchaudio'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # 추가
    a.zipfiles,      # 추가
    a.datas,         # 추가
    [],
    name='uniocr',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)