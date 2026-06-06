"""배포 후 모듈 캐시(stale import) 방지 가드.

문제(근본 원인):
    Streamlit Cloud는 코드가 바뀌면 page 스크립트는 새로 실행하지만,
    `import`된 모듈은 살아있는 프로세스의 sys.modules에 캐시된 옛 버전을
    계속 사용한다. 그래서 기존 모듈(config 등)에 새 심볼을 추가하면
    `from config import 새심볼`이 옛 캐시 모듈을 만나 ImportError가 난다.
    (디스크의 파일은 최신이지만 메모리의 모듈이 옛것이라 발생.)

해결:
    앱 진입점(app.py) 최상단에서 refresh()를 호출한다. 프로젝트 .py 파일들의
    변경(mtime)을 감지하면 프로젝트 모듈을 sys.modules에서 비워, 이후 import가
    디스크의 최신본을 다시 읽게 한다. 변경이 없으면 무동작이라 평소 런타임
    오버헤드는 사실상 0이다. 이 가드 모듈 자신은 절대 비우지 않는다.
"""

import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKIP_DIRS = ("__pycache__", os.sep + ".git", os.sep + ".streamlit", os.sep + "data")
_LAST_SIG = None


def _signature() -> tuple:
    """프로젝트 내 모든 .py 파일의 (경로, mtime) 시그니처."""
    sig = []
    for root, _dirs, files in os.walk(_PROJECT_DIR):
        if any(skip in root for skip in _SKIP_DIRS):
            continue
        for fn in files:
            if fn.endswith(".py"):
                path = os.path.join(root, fn)
                try:
                    sig.append((path, os.path.getmtime(path)))
                except OSError:
                    pass
    return tuple(sorted(sig))


def _purge_project_modules() -> int:
    """이 가드를 제외한 프로젝트 모듈을 sys.modules에서 제거."""
    purged = 0
    for name, mod in list(sys.modules.items()):
        if name == __name__ or mod is None:
            continue
        file = getattr(mod, "__file__", None)
        if file and os.path.abspath(file).startswith(_PROJECT_DIR):
            del sys.modules[name]
            purged += 1
    return purged


def refresh() -> int:
    """프로젝트 파일이 바뀌었으면 모듈 캐시를 비운다.

    Returns:
        비운 모듈 수 (0이면 변경 없음 → 무동작).
    """
    global _LAST_SIG
    sig = _signature()
    if sig == _LAST_SIG:
        return 0
    _LAST_SIG = sig
    return _purge_project_modules()
