from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit_log import hash_input
from src.expense_rules import ExpenseDataError, analyze_expenses
from src.ui import apply_page


apply_page("실습 1 · 법인카드 이상탐지", "💳")
st.title("실습 1 · 법인카드 CSV 이상탐지 대시보드")
st.caption("주말 · 심야(22:00–05:59) · 30분 이내 분할결제(2건 이상·합계 50만원 이상)")

sample_path = ROOT / "sample_data" / "corporate_card_sample.csv"
sample_bytes = sample_path.read_bytes()
with st.sidebar:
    st.header("입력")
    st.download_button("샘플 CSV 받기", sample_bytes, "corporate_card_sample.csv", "text/csv")
    uploaded = st.file_uploader("법인카드 CSV", type=["csv"])
    exceptions = st.file_uploader("해외출장 승인 예외 CSV(선택)", type=["csv"], key="exceptions")
    st.info("필수 열: transaction_id, card_id, employee_id, paid_at, merchant, amount")

payload = uploaded.getvalue() if uploaded else sample_bytes
source_name = uploaded.name if uploaded else "corporate_card_sample.csv"

try:
    raw = pd.read_csv(io.BytesIO(payload))
    exception_df = pd.read_csv(exceptions) if exceptions else None
    result = analyze_expenses(raw, exception_df)
except (ExpenseDataError, ValueError, UnicodeDecodeError) as exc:
    st.error(f"실행 전 입력 검증 실패: {exc}")
    st.stop()

alerts = result.alerts
c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 거래", f"{len(result.transactions):,}")
c2.metric("경보 거래", f"{len(alerts):,}")
c3.metric("승인 예외", f"{alerts['approved_exception'].sum():,}" if not alerts.empty else "0")
c4.metric("경보 금액", f"{alerts['amount'].sum():,.0f}원" if not alerts.empty else "0원")

st.subheader("규칙별 경보")
rule_counts = pd.DataFrame(
    {
        "규칙": ["주말", "심야", "분할결제"],
        "건수": [int(result.transactions["R_WEEKEND"].sum()), int(result.transactions["R_NIGHT"].sum()), int(result.transactions["R_SPLIT"].sum())],
    }
).set_index("규칙")
st.bar_chart(rule_counts)

status_filter = st.multiselect("상태 필터", ["ALERT", "APPROVED_EXCEPTION"], default=["ALERT", "APPROVED_EXCEPTION"])
rule_filter = st.multiselect("규칙 필터", ["R_WEEKEND", "R_NIGHT", "R_SPLIT"], default=[])
view = alerts.loc[alerts["status"].isin(status_filter)].copy()
if rule_filter:
    view = view.loc[view[rule_filter].any(axis=1)]
display_columns = [
    "transaction_id", "card_id", "employee_id", "paid_at", "merchant", "amount",
    "rule_id", "calculation_basis", "status",
]
st.dataframe(view[display_columns], width="stretch", hide_index=True)

st.subheader("분할결제 세션 근거")
st.dataframe(result.split_sessions, width="stretch", hide_index=True)

export = view[display_columns].to_csv(index=False).encode("utf-8-sig")
st.download_button("필터 결과 CSV 다운로드", export, "expense_alerts.csv", "text/csv", width="stretch")
st.caption(f"입력 파일: {source_name} · SHA-256(앞 16자리): {hash_input(payload)} · 원본은 수정하거나 외부로 전송하지 않습니다.")
