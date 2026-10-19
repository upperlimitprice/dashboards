"""페이지 레지스트리. 새 페이지 = pages/<key>.py 추가 + 아래 목록에 key 추가.

각 모듈 인터페이스:
  KEY, TITLE, SUBTITLE, NEEDS(필요 환경변수 목록)
  collect(prev: dict) -> raw dict        # 네트워크 수집 → data/<key>.json 저장
  build(raw: dict) -> page dict          # 가공·차트 구성 (네트워크 없음)
"""
import importlib

ORDER = ["power_nowcast", "gas_lng", "plan_actual", "gen_capacity", "grid", "auto", "datacenter", "freight", "mlcc_lead", "solar"]

# 목록(hub) 구역 — 동종 페이지끼리 묶음. 인사이트도 이 구역 단위로 작성
GROUPS = [("🖥 데이터센터", ["power_nowcast", "datacenter"]),
          ("☀️ 전력망 · 발전 · 태양광", ["grid", "gen_capacity", "solar", "plan_actual"]),
          ("🔥 가스 · LNG", ["gas_lng"]), ("🚢 화물 · 물류", ["freight"]),
          ("🧩 전자부품 (MLCC)", ["mlcc_lead"]), ("🚗 자동차", ["auto"])]


def load(key):
    if key not in ORDER:
        raise KeyError(f"알 수 없는 페이지: {key} (가능: {', '.join(ORDER)})")
    return importlib.import_module(f"pages.{key}")


def all_modules():
    return [load(k) for k in ORDER]
