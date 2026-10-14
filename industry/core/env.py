"""경로·환경변수(.env) 로딩. 비밀값은 커밋되는 산출물에 섞이지 않도록 scrub()으로 가린다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # industry/
REPO = ROOT.parent                              # dashboards/
DATA = ROOT / "data"
SITE = ROOT / "site"
MANUAL = ROOT / "manual"
CACHE = ROOT / ".cache"

SECRET_KEYS = ("EIA_API_KEY", "DATA_GO_KR_KEY", "FRED_API_KEY")


class MissingKey(Exception):
    pass


def load_env(path=ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name, default=None):
    v = os.environ.get(name)
    return v if v else default


def require(name):
    v = env(name)
    if not v:
        raise MissingKey(f"{name} 미설정 — industry/.env 에 추가하세요")
    return v


def scrub(text):
    """에러 메시지 등에 섞인 API 키를 *** 로 치환 (data/*.json 은 공개 저장소에 커밋됨)."""
    from urllib.parse import quote, quote_plus
    text = str(text)
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) >= 6:
            for form in {v, quote(v, safe=""), quote_plus(v)}:
                text = text.replace(form, "***")
    return text
