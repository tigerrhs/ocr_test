import sys, shutil, pathlib
from setuptools import Extension, setup
from Cython.Build import cythonize
import glob

ROOT = pathlib.Path(__file__).parent.resolve()
SRC_DIR = ROOT / "uniocr_ai"
BIN_DIR = ROOT / "bin"

def to_module_name(path: pathlib.Path) -> str:
    # 하위 경로를 모듈 경로로 변환: dir/sub/mod.pyx -> dir.sub.mod
    rel = path.relative_to(SRC_DIR).with_suffix("")  # drop .py/.pyx
    parts = list(rel.parts)
    return ".".join(parts)

def ensure_pkg_inits_for(path: pathlib.Path):
    """
    SRC_DIR 안의 path에 해당하는 파일이 BIN_DIR로 복사될 때,
    필요한 __init__.py들을 BIN_DIR 쪽 패키지 디렉터리에 보장해준다.
    - __init__.py 원본이 있으면 복사
    - 없으면 빈 __init__.py 생성
    - .py 이외 파일은 그냥 복사
    """
    rel_path = path.relative_to(SRC_DIR)
    rel_dir = rel_path.parent

    cur_src = SRC_DIR
    cur_dst = BIN_DIR

    for part in rel_dir.parts:
        cur_src = cur_src / part
        cur_dst = cur_dst / part
        cur_dst.mkdir(parents=True, exist_ok=True)

        src_init = cur_src / "__init__.py"
        dst_init = cur_dst / "__init__.py"

        if src_init.exists():
            shutil.copy2(src_init, dst_init)   # 원본 __init__.py 보존
        elif not dst_init.exists():
            dst_init.write_text("")            # 없으면 빈 파일 생성

    # 일반 파일 복사
    if path.is_file() and path.suffix != ".py":
        dst = BIN_DIR / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)

def main(build_file=[]):
    print(f"[i] SRC_DIR={SRC_DIR}")
    print(f"[i] BIN_DIR={BIN_DIR}")

    if not SRC_DIR.exists():
        print(f"[!] {SRC_DIR} 폴더가 없습니다.")
        sys.exit(1)

    if build_file:  # 특정 파일 재빌드
        targets = build_file

    else:   # 전체 빌드
        targets = [p for p in SRC_DIR.rglob("*.py") if p.name != "__init__.py"]

    if not targets:
        print("[!] 빌드할*.py 파일이 없습니다.")
        sys.exit(1)

    print("[i] 빌드 대상:")
    for t in targets:
        print("   -", t.relative_to(SRC_DIR))

    if BIN_DIR.exists():
        shutil.rmtree(BIN_DIR)
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    # 출력 쪽 패키지 __init__.py 준비
    for t in targets:
        ensure_pkg_inits_for(t)

    # 각 파일을 Extension으로 등록 (모듈명은 경로를 점으로)
    exts = []
    for t in targets:
        mod_name = to_module_name(t)
        exts.append(
            Extension(
                mod_name,
                [str(t)],
                language="c"
            )
        )

    built = cythonize(
        exts,
        compiler_directives=dict(language_level=3, boundscheck=False, initializedcheck=False),
        build_dir=str(ROOT / "build"),
        annotate=False,
        quiet=False,
        force=True
    )

    # 산출물을 plugins/로
    setup(
        name="plugins",
        ext_modules=built,
        script_args=["build_ext", f"--build-lib={BIN_DIR}"],
    )

    print("[i] 빌드 완료. 생성물:")
    for p in BIN_DIR.rglob("*"):
        if p.is_file():
            print("   -", p.relative_to(BIN_DIR))

    # 빌드 끝난 뒤 정리
    shutil.rmtree("build", ignore_errors=True)
    for path in glob.glob("temp.linux-*"):
        shutil.rmtree(path, ignore_errors=True)

if __name__ == "__main__":
    main()