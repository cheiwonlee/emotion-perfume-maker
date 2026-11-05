"""
가상 보드(mock)와 대시보드를 잇는 얇은 다리.
`python run.py` 로 실행했을 때만 mock 이 등록되어 있고, 그 외에는 runtime 이 None 이다.
"""
try:
    from mock import runtime
except ImportError:  # 레포 루트가 sys.path 에 없을 때 (예: manage.py runserver 단독 실행)
    runtime = None


def active() -> bool:
    return runtime is not None and runtime.is_active()
