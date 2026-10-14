"""뉴욕연은 글로벌 공급망 압력지수(GSCPI) 엑셀."""
import io
from datetime import datetime

from ..http import get

URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"


def parse(xlsx_bytes):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            if len(r) >= 2 and isinstance(r[0], datetime) and isinstance(r[1], (int, float)):
                out[r[0].strftime("%Y-%m")] = float(r[1])
        if out:
            break
    wb.close()
    return out


def series():
    return parse(get(URL, timeout=90, cache_hours=12))
