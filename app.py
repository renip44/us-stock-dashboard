from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

PORTFOLIO_FILE = "portfolio.csv"
REQUIRED_COLUMNS = ["Ticker", "Shares", "AvgCost"]

KR_FILE = "kr_portfolio.csv"
KR_COLUMNS = ["Ticker", "Shares", "AvgCost"]

KRW_FILE = "krw_assets.csv"
KRW_COLUMNS = ["Name", "Category", "Amount"]
KRW_CATEGORIES = ["현금", "예금/적금", "국내주식", "부동산", "채권", "기타"]

USD_FILE = "usd_assets.csv"
USD_COLUMNS = ["Name", "Category", "Amount"]
USD_CATEGORIES = ["현금", "예금/적금(MMF 등)", "채권", "기타"]

TARGET_FILE = "target_allocation.csv"
TARGET_COLUMNS = ["Category", "TargetPct"]
TARGET_CATEGORIES = ["미국주식", "한국주식", "원화자산", "달러자산"]

HISTORY_FILE = "asset_history.csv"
HISTORY_COLUMNS = [
    "Date",
    "TotalKRW",
    "TotalUSD",
    "USStockKRW",
    "KRStockKRW",
    "KRWAssetsKRW",
    "USDAssetsKRW",
]

st.set_page_config(page_title="전체 자산배분 현황", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
    @media (max-width: 640px) {
        .block-container { padding: 0.8rem 0.6rem 2rem 0.6rem; }
        [data-testid="stMetricValue"] { font-size: 1.1rem; }
        [data-testid="stMetricLabel"] { font-size: 0.75rem; }
        h1 { font-size: 1.4rem; }
        h2, h3 { font-size: 1.1rem; }
        .stTabs [data-baseweb="tab"] { font-size: 0.8rem; padding: 0.4rem 0.5rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def check_password() -> bool:
    """앱이 클라우드에 배포되어 secrets에 APP_PASSWORD가 설정된 경우에만 비밀번호를 요구한다."""
    try:
        required = st.secrets.get("APP_PASSWORD")
    except Exception:
        required = None
    if not required:
        return True
    if st.session_state.get("authed"):
        return True
    st.title("🔒 접속 비밀번호")
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("입장"):
        if pw == required:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False


if not check_password():
    st.stop()


def load_portfolio() -> pd.DataFrame:
    try:
        df = pd.read_csv(PORTFOLIO_FILE)
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        return df[REQUIRED_COLUMNS]
    except FileNotFoundError:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)


def save_portfolio(df: pd.DataFrame) -> None:
    df.to_csv(PORTFOLIO_FILE, index=False)


def load_kr_portfolio() -> pd.DataFrame:
    try:
        df = pd.read_csv(KR_FILE)
        for col in KR_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        return df[KR_COLUMNS]
    except FileNotFoundError:
        return pd.DataFrame(columns=KR_COLUMNS)


def save_kr_portfolio(df: pd.DataFrame) -> None:
    df.to_csv(KR_FILE, index=False)


def load_krw_assets() -> pd.DataFrame:
    try:
        df = pd.read_csv(KRW_FILE)
        for col in KRW_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        return df[KRW_COLUMNS]
    except FileNotFoundError:
        return pd.DataFrame(columns=KRW_COLUMNS)


def save_krw_assets(df: pd.DataFrame) -> None:
    df.to_csv(KRW_FILE, index=False)


def load_usd_assets() -> pd.DataFrame:
    try:
        df = pd.read_csv(USD_FILE)
        for col in USD_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        return df[USD_COLUMNS]
    except FileNotFoundError:
        return pd.DataFrame(columns=USD_COLUMNS)


def save_usd_assets(df: pd.DataFrame) -> None:
    df.to_csv(USD_FILE, index=False)


def load_target_allocation() -> pd.DataFrame:
    try:
        df = pd.read_csv(TARGET_FILE)
        for col in TARGET_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        return df[TARGET_COLUMNS]
    except FileNotFoundError:
        return pd.DataFrame(
            [{"Category": c, "TargetPct": 25.0} for c in TARGET_CATEGORIES]
        )


def save_target_allocation(df: pd.DataFrame) -> None:
    df.to_csv(TARGET_FILE, index=False)


def load_history() -> pd.DataFrame:
    try:
        df = pd.read_csv(HISTORY_FILE)
        for col in HISTORY_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        return df[HISTORY_COLUMNS]
    except FileNotFoundError:
        return pd.DataFrame(columns=HISTORY_COLUMNS)


def save_history(df: pd.DataFrame) -> None:
    df.to_csv(HISTORY_FILE, index=False)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_prices(tickers: tuple[str, ...]) -> dict[str, dict]:
    result = {}
    if not tickers:
        return result
    data = yf.Tickers(" ".join(tickers))
    for t in tickers:
        try:
            fast = data.tickers[t].fast_info
            price = fast.get("lastPrice") or fast.get("last_price")
            prev_close = fast.get("previousClose") or fast.get("previous_close")
            result[t] = {
                "price": float(price) if price is not None else None,
                "prev_close": float(prev_close) if prev_close is not None else None,
            }
        except Exception:
            result[t] = {"price": None, "prev_close": None}
    return result


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def fetch_sectors(tickers: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).get_info()
            result[t] = info.get("sector") or info.get("quoteType", "기타") or "기타"
        except Exception:
            result[t] = "알수없음"
    return result


@st.cache_data(ttl=60, show_spinner=False)
def fetch_usdkrw() -> float | None:
    try:
        fast = yf.Ticker("KRW=X").fast_info
        rate = fast.get("lastPrice") or fast.get("last_price")
        return float(rate) if rate is not None else None
    except Exception:
        return None


if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
if "kr_portfolio" not in st.session_state:
    st.session_state.kr_portfolio = load_kr_portfolio()
if "krw_assets" not in st.session_state:
    st.session_state.krw_assets = load_krw_assets()
if "usd_assets" not in st.session_state:
    st.session_state.usd_assets = load_usd_assets()
if "target_alloc" not in st.session_state:
    st.session_state.target_alloc = load_target_allocation()
if "history" not in st.session_state:
    st.session_state.history = load_history()

st.title("💰 전체 자산배분 현황")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("🇺🇸 미국주식 관리")

    st.subheader("종목 추가 (직접 입력)")
    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ticker = c1.text_input("티커 (예: AAPL)").strip().upper()
        shares = c2.number_input("수량", min_value=0.0, step=1.0, value=0.0)
        avg_cost = st.number_input("평단가 (USD, 선택)", min_value=0.0, step=0.01, value=0.0)
        submitted = st.form_submit_button("추가")
        if submitted and ticker and shares > 0:
            df = st.session_state.portfolio
            if ticker in df["Ticker"].values:
                df.loc[df["Ticker"] == ticker, "Shares"] += shares
                if avg_cost > 0:
                    df.loc[df["Ticker"] == ticker, "AvgCost"] = avg_cost
            else:
                new_row = pd.DataFrame(
                    [{"Ticker": ticker, "Shares": shares, "AvgCost": avg_cost}]
                )
                df = pd.concat([df, new_row], ignore_index=True)
            st.session_state.portfolio = df
            save_portfolio(df)
            st.success(f"{ticker} 추가/갱신 완료")

    with st.expander("CSV로 가져오기 (Ticker, Shares, AvgCost)"):
        uploaded = st.file_uploader("CSV 업로드", type=["csv"], key="stock_csv")
        if uploaded is not None:
            try:
                new_df = pd.read_csv(uploaded)
                for col in REQUIRED_COLUMNS:
                    if col not in new_df.columns:
                        new_df[col] = 0
                new_df = new_df[REQUIRED_COLUMNS]
                mode = st.radio("가져오기 방식", ["교체", "병합(합산)"], horizontal=True, key="stock_mode")
                if st.button("CSV 적용", key="stock_apply"):
                    if mode == "교체":
                        st.session_state.portfolio = new_df
                    else:
                        merged = pd.concat([st.session_state.portfolio, new_df], ignore_index=True)
                        merged = merged.groupby("Ticker", as_index=False).agg(
                            {"Shares": "sum", "AvgCost": "last"}
                        )
                        st.session_state.portfolio = merged
                    save_portfolio(st.session_state.portfolio)
                    st.success("CSV 반영 완료")
                    st.rerun()
            except Exception as e:
                st.error(f"CSV 처리 오류: {e}")

    with st.expander("보유 종목 편집"):
        edited = st.data_editor(
            st.session_state.portfolio,
            num_rows="dynamic",
            use_container_width=True,
            key="editor",
        )
        if st.button("변경사항 저장", key="stock_save"):
            edited = edited.dropna(subset=["Ticker"])
            edited["Ticker"] = edited["Ticker"].astype(str).str.upper().str.strip()
            edited = edited[edited["Ticker"] != ""]
            st.session_state.portfolio = edited.reset_index(drop=True)
            save_portfolio(st.session_state.portfolio)
            st.success("저장 완료")
            st.rerun()

        csv_bytes = st.session_state.portfolio.to_csv(index=False).encode("utf-8")
        st.download_button("CSV 다운로드", csv_bytes, "portfolio_export.csv", "text/csv", key="stock_dl")

    st.divider()
    st.header("🇰🇷 한국주식 관리")
    st.caption("티커에 코스피는 .KS, 코스닥은 .KQ를 붙이세요. 예: 삼성전자 005930.KS, 에코프로 086520.KQ")

    with st.form("kr_add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        kr_ticker = c1.text_input("티커 (예: 005930.KS)").strip().upper()
        kr_shares = c2.number_input("수량", min_value=0.0, step=1.0, value=0.0, key="kr_shares")
        kr_avg_cost = st.number_input("평단가 (KRW, 선택)", min_value=0.0, step=100.0, value=0.0, key="kr_avg_cost")
        kr_submitted_stock = st.form_submit_button("추가")
        if kr_submitted_stock and kr_ticker and kr_shares > 0:
            df = st.session_state.kr_portfolio
            if kr_ticker in df["Ticker"].values:
                df.loc[df["Ticker"] == kr_ticker, "Shares"] += kr_shares
                if kr_avg_cost > 0:
                    df.loc[df["Ticker"] == kr_ticker, "AvgCost"] = kr_avg_cost
            else:
                new_row = pd.DataFrame(
                    [{"Ticker": kr_ticker, "Shares": kr_shares, "AvgCost": kr_avg_cost}]
                )
                df = pd.concat([df, new_row], ignore_index=True)
            st.session_state.kr_portfolio = df
            save_kr_portfolio(df)
            st.success(f"{kr_ticker} 추가/갱신 완료")

    with st.expander("CSV로 가져오기 (Ticker, Shares, AvgCost)"):
        kr_uploaded = st.file_uploader("CSV 업로드", type=["csv"], key="kr_stock_csv")
        if kr_uploaded is not None:
            try:
                new_kr_df = pd.read_csv(kr_uploaded)
                for col in KR_COLUMNS:
                    if col not in new_kr_df.columns:
                        new_kr_df[col] = 0
                new_kr_df = new_kr_df[KR_COLUMNS]
                kr_mode = st.radio("가져오기 방식", ["교체", "병합(합산)"], horizontal=True, key="kr_stock_mode")
                if st.button("CSV 적용", key="kr_stock_apply"):
                    if kr_mode == "교체":
                        st.session_state.kr_portfolio = new_kr_df
                    else:
                        merged = pd.concat([st.session_state.kr_portfolio, new_kr_df], ignore_index=True)
                        merged = merged.groupby("Ticker", as_index=False).agg(
                            {"Shares": "sum", "AvgCost": "last"}
                        )
                        st.session_state.kr_portfolio = merged
                    save_kr_portfolio(st.session_state.kr_portfolio)
                    st.success("CSV 반영 완료")
                    st.rerun()
            except Exception as e:
                st.error(f"CSV 처리 오류: {e}")

    with st.expander("보유 종목 편집"):
        kr_edited = st.data_editor(
            st.session_state.kr_portfolio,
            num_rows="dynamic",
            use_container_width=True,
            key="kr_stock_editor",
        )
        if st.button("변경사항 저장", key="kr_stock_save"):
            kr_edited = kr_edited.dropna(subset=["Ticker"])
            kr_edited["Ticker"] = kr_edited["Ticker"].astype(str).str.upper().str.strip()
            kr_edited = kr_edited[kr_edited["Ticker"] != ""]
            st.session_state.kr_portfolio = kr_edited.reset_index(drop=True)
            save_kr_portfolio(st.session_state.kr_portfolio)
            st.success("저장 완료")
            st.rerun()

        kr_csv_bytes = st.session_state.kr_portfolio.to_csv(index=False).encode("utf-8")
        st.download_button("CSV 다운로드", kr_csv_bytes, "kr_portfolio_export.csv", "text/csv", key="kr_stock_dl")

    st.divider()
    st.header("🏦 원화자산 관리")
    st.caption("현금, 예금/적금, 부동산 등 원화 기준 현금성 자산 (국내주식은 위 '한국주식 관리'를 이용하세요)")

    with st.form("krw_add_form", clear_on_submit=True):
        name = st.text_input("자산명 (예: 파킹통장)")
        category = st.selectbox("분류", KRW_CATEGORIES)
        amount = st.number_input("금액 (KRW)", min_value=0.0, step=10000.0, value=0.0)
        krw_submitted = st.form_submit_button("추가")
        if krw_submitted and name and amount > 0:
            df = st.session_state.krw_assets
            if name in df["Name"].values:
                df.loc[df["Name"] == name, "Amount"] += amount
                df.loc[df["Name"] == name, "Category"] = category
            else:
                new_row = pd.DataFrame(
                    [{"Name": name, "Category": category, "Amount": amount}]
                )
                df = pd.concat([df, new_row], ignore_index=True)
            st.session_state.krw_assets = df
            save_krw_assets(df)
            st.success(f"{name} 추가/갱신 완료")

    with st.expander("CSV로 가져오기 (Name, Category, Amount)"):
        krw_uploaded = st.file_uploader("CSV 업로드", type=["csv"], key="krw_csv")
        if krw_uploaded is not None:
            try:
                new_krw_df = pd.read_csv(krw_uploaded)
                for col in KRW_COLUMNS:
                    if col not in new_krw_df.columns:
                        new_krw_df[col] = 0
                new_krw_df = new_krw_df[KRW_COLUMNS]
                krw_mode = st.radio("가져오기 방식", ["교체", "병합(합산)"], horizontal=True, key="krw_mode")
                if st.button("CSV 적용", key="krw_apply"):
                    if krw_mode == "교체":
                        st.session_state.krw_assets = new_krw_df
                    else:
                        merged = pd.concat([st.session_state.krw_assets, new_krw_df], ignore_index=True)
                        merged = merged.groupby(["Name", "Category"], as_index=False).agg(
                            {"Amount": "sum"}
                        )
                        st.session_state.krw_assets = merged
                    save_krw_assets(st.session_state.krw_assets)
                    st.success("CSV 반영 완료")
                    st.rerun()
            except Exception as e:
                st.error(f"CSV 처리 오류: {e}")

    with st.expander("원화자산 편집"):
        krw_edited = st.data_editor(
            st.session_state.krw_assets,
            num_rows="dynamic",
            use_container_width=True,
            key="krw_editor",
        )
        if st.button("변경사항 저장", key="krw_save"):
            krw_edited = krw_edited.dropna(subset=["Name"])
            krw_edited["Name"] = krw_edited["Name"].astype(str).str.strip()
            krw_edited = krw_edited[krw_edited["Name"] != ""]
            st.session_state.krw_assets = krw_edited.reset_index(drop=True)
            save_krw_assets(st.session_state.krw_assets)
            st.success("저장 완료")
            st.rerun()

        krw_csv_bytes = st.session_state.krw_assets.to_csv(index=False).encode("utf-8")
        st.download_button("CSV 다운로드", krw_csv_bytes, "krw_assets_export.csv", "text/csv", key="krw_dl")

    st.divider()
    st.header("💵 달러자산 관리")
    st.caption("증권사 예수금, 달러 파킹통장/MMF 등 USD로 보유 중인 현금성 자산 (주식 아님)")

    with st.form("usd_add_form", clear_on_submit=True):
        usd_name = st.text_input("자산명 (예: 증권사 달러예수금)")
        usd_category = st.selectbox("분류", USD_CATEGORIES)
        usd_amount = st.number_input("금액 (USD)", min_value=0.0, step=100.0, value=0.0)
        usd_submitted = st.form_submit_button("추가")
        if usd_submitted and usd_name and usd_amount > 0:
            df = st.session_state.usd_assets
            if usd_name in df["Name"].values:
                df.loc[df["Name"] == usd_name, "Amount"] += usd_amount
                df.loc[df["Name"] == usd_name, "Category"] = usd_category
            else:
                new_row = pd.DataFrame(
                    [{"Name": usd_name, "Category": usd_category, "Amount": usd_amount}]
                )
                df = pd.concat([df, new_row], ignore_index=True)
            st.session_state.usd_assets = df
            save_usd_assets(df)
            st.success(f"{usd_name} 추가/갱신 완료")

    with st.expander("CSV로 가져오기 (Name, Category, Amount)"):
        usd_uploaded = st.file_uploader("CSV 업로드", type=["csv"], key="usd_csv")
        if usd_uploaded is not None:
            try:
                new_usd_df = pd.read_csv(usd_uploaded)
                for col in USD_COLUMNS:
                    if col not in new_usd_df.columns:
                        new_usd_df[col] = 0
                new_usd_df = new_usd_df[USD_COLUMNS]
                usd_mode = st.radio("가져오기 방식", ["교체", "병합(합산)"], horizontal=True, key="usd_mode")
                if st.button("CSV 적용", key="usd_apply"):
                    if usd_mode == "교체":
                        st.session_state.usd_assets = new_usd_df
                    else:
                        merged = pd.concat([st.session_state.usd_assets, new_usd_df], ignore_index=True)
                        merged = merged.groupby(["Name", "Category"], as_index=False).agg(
                            {"Amount": "sum"}
                        )
                        st.session_state.usd_assets = merged
                    save_usd_assets(st.session_state.usd_assets)
                    st.success("CSV 반영 완료")
                    st.rerun()
            except Exception as e:
                st.error(f"CSV 처리 오류: {e}")

    with st.expander("달러자산 편집"):
        usd_edited = st.data_editor(
            st.session_state.usd_assets,
            num_rows="dynamic",
            use_container_width=True,
            key="usd_editor",
        )
        if st.button("변경사항 저장", key="usd_save"):
            usd_edited = usd_edited.dropna(subset=["Name"])
            usd_edited["Name"] = usd_edited["Name"].astype(str).str.strip()
            usd_edited = usd_edited[usd_edited["Name"] != ""]
            st.session_state.usd_assets = usd_edited.reset_index(drop=True)
            save_usd_assets(st.session_state.usd_assets)
            st.success("저장 완료")
            st.rerun()

        usd_csv_bytes = st.session_state.usd_assets.to_csv(index=False).encode("utf-8")
        st.download_button("CSV 다운로드", usd_csv_bytes, "usd_assets_export.csv", "text/csv", key="usd_dl")

    st.divider()
    st.header("🎯 목표 비중 설정")
    st.caption("리밸런싱 계산에 사용할 자산군별 목표 비중 (%). 저장 버튼을 눌러야 반영됩니다.")

    saved_target_map = dict(
        zip(st.session_state.target_alloc["Category"], st.session_state.target_alloc["TargetPct"])
    )
    new_targets = {}
    for cat in TARGET_CATEGORIES:
        new_targets[cat] = st.number_input(
            cat,
            min_value=0.0,
            max_value=100.0,
            value=float(saved_target_map.get(cat, 25.0)),
            step=1.0,
            key=f"target_input_{cat}",
        )
    total_target_pct = sum(new_targets.values())
    if abs(total_target_pct - 100) < 0.5:
        st.caption(f"✅ 합계: {total_target_pct:.1f}%")
    else:
        st.caption(f"⚠️ 합계: {total_target_pct:.1f}% (100%가 되도록 조정하세요)")

    if st.button("목표 비중 저장", key="target_save"):
        target_df = pd.DataFrame(
            [{"Category": c, "TargetPct": v} for c, v in new_targets.items()]
        )
        st.session_state.target_alloc = target_df
        save_target_allocation(target_df)
        st.success("저장 완료")
        st.rerun()

    st.divider()
    if st.button("🔄 시세/환율 새로고침"):
        fetch_prices.clear()
        fetch_usdkrw.clear()
        st.rerun()

# ---------------- Data prep: US stocks ----------------
portfolio = st.session_state.portfolio.copy()
portfolio = portfolio.dropna(subset=["Ticker"])
portfolio["Ticker"] = portfolio["Ticker"].astype(str).str.strip()
portfolio = portfolio[portfolio["Ticker"] != ""]

kr_portfolio = st.session_state.kr_portfolio.copy()
kr_portfolio = kr_portfolio.dropna(subset=["Ticker"])
kr_portfolio["Ticker"] = kr_portfolio["Ticker"].astype(str).str.upper().str.strip()
kr_portfolio = kr_portfolio[kr_portfolio["Ticker"] != ""]

krw_assets = st.session_state.krw_assets.copy()
krw_assets = krw_assets.dropna(subset=["Name"])
krw_assets["Name"] = krw_assets["Name"].astype(str).str.strip()
krw_assets = krw_assets[krw_assets["Name"] != ""]
krw_assets["Amount"] = pd.to_numeric(krw_assets["Amount"], errors="coerce").fillna(0)

usd_assets = st.session_state.usd_assets.copy()
usd_assets = usd_assets.dropna(subset=["Name"])
usd_assets["Name"] = usd_assets["Name"].astype(str).str.strip()
usd_assets = usd_assets[usd_assets["Name"] != ""]
usd_assets["Amount"] = pd.to_numeric(usd_assets["Amount"], errors="coerce").fillna(0)

if portfolio.empty and kr_portfolio.empty and krw_assets.empty and usd_assets.empty:
    st.info("왼쪽 사이드바에서 미국주식, 한국주식, 원화자산 또는 달러자산을 추가하세요.")
    st.stop()

tickers = tuple(sorted(portfolio["Ticker"].unique())) if not portfolio.empty else tuple()
kr_tickers = tuple(sorted(kr_portfolio["Ticker"].unique())) if not kr_portfolio.empty else tuple()

with st.spinner("실시간 시세 및 환율 조회 중..."):
    prices = fetch_prices(tickers)
    sectors = fetch_sectors(tickers)
    kr_prices = fetch_prices(kr_tickers)
    usdkrw = fetch_usdkrw()

if not portfolio.empty:
    portfolio["CurrentPrice"] = portfolio["Ticker"].map(lambda t: prices.get(t, {}).get("price"))
    portfolio["PrevClose"] = portfolio["Ticker"].map(lambda t: prices.get(t, {}).get("prev_close"))
    portfolio["Sector"] = portfolio["Ticker"].map(lambda t: sectors.get(t, "알수없음"))

    missing = portfolio[portfolio["CurrentPrice"].isna()]["Ticker"].tolist()
    if missing:
        st.warning(f"시세를 가져오지 못한 종목: {', '.join(missing)}")

    portfolio["CurrentPrice"] = portfolio["CurrentPrice"].fillna(0)
    portfolio["PrevClose"] = portfolio["PrevClose"].fillna(portfolio["CurrentPrice"])
    portfolio["MarketValueUSD"] = portfolio["Shares"] * portfolio["CurrentPrice"]
    portfolio["CostBasisUSD"] = portfolio["Shares"] * portfolio["AvgCost"]
    portfolio["PnLUSD"] = portfolio["MarketValueUSD"] - portfolio["CostBasisUSD"]
    portfolio["PnLPct"] = portfolio.apply(
        lambda r: (r["PnLUSD"] / r["CostBasisUSD"] * 100) if r["CostBasisUSD"] > 0 else 0, axis=1
    )
    portfolio["DayChangePct"] = portfolio.apply(
        lambda r: ((r["CurrentPrice"] - r["PrevClose"]) / r["PrevClose"] * 100) if r["PrevClose"] else 0,
        axis=1,
    )
    portfolio["DayChangeUSD"] = (portfolio["CurrentPrice"] - portfolio["PrevClose"]) * portfolio["Shares"]
else:
    portfolio["MarketValueUSD"] = []
    portfolio["DayChangeUSD"] = []

if not kr_portfolio.empty:
    kr_portfolio["CurrentPrice"] = kr_portfolio["Ticker"].map(lambda t: kr_prices.get(t, {}).get("price"))
    kr_portfolio["PrevClose"] = kr_portfolio["Ticker"].map(lambda t: kr_prices.get(t, {}).get("prev_close"))

    kr_missing = kr_portfolio[kr_portfolio["CurrentPrice"].isna()]["Ticker"].tolist()
    if kr_missing:
        st.warning(f"시세를 가져오지 못한 한국주식: {', '.join(kr_missing)} (티커에 .KS 또는 .KQ가 붙어있는지 확인하세요)")

    kr_portfolio["CurrentPrice"] = kr_portfolio["CurrentPrice"].fillna(0)
    kr_portfolio["PrevClose"] = kr_portfolio["PrevClose"].fillna(kr_portfolio["CurrentPrice"])
    kr_portfolio["MarketValueKRW"] = kr_portfolio["Shares"] * kr_portfolio["CurrentPrice"]
    kr_portfolio["CostBasisKRW"] = kr_portfolio["Shares"] * kr_portfolio["AvgCost"]
    kr_portfolio["PnLKRW"] = kr_portfolio["MarketValueKRW"] - kr_portfolio["CostBasisKRW"]
    kr_portfolio["PnLPct"] = kr_portfolio.apply(
        lambda r: (r["PnLKRW"] / r["CostBasisKRW"] * 100) if r["CostBasisKRW"] > 0 else 0, axis=1
    )
    kr_portfolio["DayChangePct"] = kr_portfolio.apply(
        lambda r: ((r["CurrentPrice"] - r["PrevClose"]) / r["PrevClose"] * 100) if r["PrevClose"] else 0,
        axis=1,
    )
    kr_portfolio["DayChangeKRW"] = (kr_portfolio["CurrentPrice"] - kr_portfolio["PrevClose"]) * kr_portfolio["Shares"]
else:
    kr_portfolio["MarketValueKRW"] = []
    kr_portfolio["DayChangeKRW"] = []

total_kr_cost_krw = kr_portfolio["CostBasisKRW"].sum() if not kr_portfolio.empty else 0.0
total_kr_pnl_krw = kr_portfolio["PnLKRW"].sum() if not kr_portfolio.empty else 0.0
total_kr_day_change_krw = kr_portfolio["DayChangeKRW"].sum() if not kr_portfolio.empty else 0.0

total_stock_usd = portfolio["MarketValueUSD"].sum() if not portfolio.empty else 0.0
total_cost_usd = portfolio["CostBasisUSD"].sum() if not portfolio.empty else 0.0
total_pnl_usd = portfolio["PnLUSD"].sum() if not portfolio.empty else 0.0
total_day_change_usd = portfolio["DayChangeUSD"].sum() if not portfolio.empty else 0.0
portfolio["Weight%"] = (
    portfolio["MarketValueUSD"] / total_stock_usd * 100 if total_stock_usd else 0
)

total_kr_stock_krw = kr_portfolio["MarketValueKRW"].sum() if not kr_portfolio.empty else 0.0
kr_portfolio["Weight%"] = (
    kr_portfolio["MarketValueKRW"] / total_kr_stock_krw * 100 if total_kr_stock_krw else 0
)

if not usdkrw:
    st.error("환율 조회에 실패했습니다. 새로고침을 눌러 다시 시도해주세요. (원화 환산 금액이 부정확할 수 있습니다)")
    usdkrw = 0.0

total_stock_krw = total_stock_usd * usdkrw
total_krw_assets = krw_assets["Amount"].sum() if not krw_assets.empty else 0.0
total_krw_assets_usd = total_krw_assets / usdkrw if usdkrw else 0.0
total_usd_assets = usd_assets["Amount"].sum() if not usd_assets.empty else 0.0
total_usd_assets_krw = total_usd_assets * usdkrw

grand_total_krw = total_stock_krw + total_kr_stock_krw + total_krw_assets + total_usd_assets_krw
grand_total_usd = total_stock_usd + (total_kr_stock_krw / usdkrw if usdkrw else 0) + total_krw_assets_usd + total_usd_assets

current_by_category_krw = {
    "미국주식": total_stock_krw,
    "한국주식": total_kr_stock_krw,
    "원화자산": total_krw_assets,
    "달러자산": total_usd_assets_krw,
}

# ---------------- Rebalancing ----------------
target_map = dict(
    zip(st.session_state.target_alloc["Category"], st.session_state.target_alloc["TargetPct"])
)
rebalance_rows = []
for cat in TARGET_CATEGORIES:
    current_amt = current_by_category_krw.get(cat, 0.0)
    current_pct = (current_amt / grand_total_krw * 100) if grand_total_krw else 0.0
    target_pct = float(target_map.get(cat, 0.0))
    target_amt = grand_total_krw * target_pct / 100
    rebalance_rows.append(
        {
            "구분": cat,
            "현재금액(KRW)": current_amt,
            "현재비중%": current_pct,
            "목표비중%": target_pct,
            "차이%": current_pct - target_pct,
            "조정필요액(KRW)": target_amt - current_amt,
        }
    )
rebalance_df = pd.DataFrame(rebalance_rows)

# ---------------- Asset history snapshot (once per day, latest value kept) ----------------
if grand_total_krw > 0:
    today_str = datetime.now().strftime("%Y-%m-%d")
    hist = st.session_state.history
    hist = hist[hist["Date"] != today_str]
    new_snapshot = pd.DataFrame(
        [
            {
                "Date": today_str,
                "TotalKRW": grand_total_krw,
                "TotalUSD": grand_total_usd,
                "USStockKRW": total_stock_krw,
                "KRStockKRW": total_kr_stock_krw,
                "KRWAssetsKRW": total_krw_assets,
                "USDAssetsKRW": total_usd_assets_krw,
            }
        ]
    )
    hist = pd.concat([hist, new_snapshot], ignore_index=True).sort_values("Date").reset_index(drop=True)
    st.session_state.history = hist
    save_history(hist)

# ---------------- Unified asset table (for total allocation view) ----------------
unified_rows = []
for _, r in portfolio.iterrows():
    unified_rows.append(
        {
            "자산명": r["Ticker"],
            "분류": "미국주식",
            "금액(KRW)": r["MarketValueUSD"] * usdkrw,
            "금액(USD)": r["MarketValueUSD"],
        }
    )
for _, r in kr_portfolio.iterrows():
    unified_rows.append(
        {
            "자산명": r["Ticker"],
            "분류": "한국주식",
            "금액(KRW)": r["MarketValueKRW"],
            "금액(USD)": r["MarketValueKRW"] / usdkrw if usdkrw else 0,
        }
    )
for _, r in krw_assets.iterrows():
    unified_rows.append(
        {
            "자산명": r["Name"],
            "분류": r["Category"],
            "금액(KRW)": r["Amount"],
            "금액(USD)": r["Amount"] / usdkrw if usdkrw else 0,
        }
    )
for _, r in usd_assets.iterrows():
    unified_rows.append(
        {
            "자산명": r["Name"],
            "분류": "달러현금성자산-" + r["Category"],
            "금액(KRW)": r["Amount"] * usdkrw,
            "금액(USD)": r["Amount"],
        }
    )
unified_df = pd.DataFrame(unified_rows)
if not unified_df.empty:
    unified_df["비중%"] = (
        unified_df["금액(KRW)"] / grand_total_krw * 100 if grand_total_krw else 0
    )

# ---------------- Top metrics ----------------
st.subheader("전체 자산 요약")
m1, m2, m3 = st.columns(3)
m1.metric("총 자산 (KRW)", f"₩{grand_total_krw:,.0f}")
m2.metric("총 자산 (USD)", f"${grand_total_usd:,.2f}")
m3.metric(
    "미국주식 비중",
    f"{(total_stock_krw / grand_total_krw * 100) if grand_total_krw else 0:.1f}%",
    f"₩{total_stock_krw:,.0f}",
)
m4, m5, m6 = st.columns(3)
m4.metric(
    "한국주식 비중",
    f"{(total_kr_stock_krw / grand_total_krw * 100) if grand_total_krw else 0:.1f}%",
    f"₩{total_kr_stock_krw:,.0f}",
)
m5.metric(
    "원화자산 비중",
    f"{(total_krw_assets / grand_total_krw * 100) if grand_total_krw else 0:.1f}%",
    f"₩{total_krw_assets:,.0f}",
)
m6.metric(
    "달러자산 비중",
    f"{(total_usd_assets_krw / grand_total_krw * 100) if grand_total_krw else 0:.1f}%",
    f"${total_usd_assets:,.2f}",
)
st.caption(f"USD/KRW 환율: {usdkrw:,.2f}  |  마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

st.divider()

tab0, tab_reb, tab_hist, tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "💰 전체 자산 배분",
        "⚖️ 리밸런싱",
        "📈 자산 추이",
        "🇺🇸 종목별 배분",
        "🏭 섹터별 배분",
        "📋 미국주식 보유 내역",
        "🇰🇷 한국 종목별 배분",
        "📋 한국주식 보유 내역",
    ]
)

with tab0:
    c1, c2 = st.columns([1, 1])
    with c1:
        type_df = pd.DataFrame(
            [
                {"구분": "미국주식", "금액(KRW)": total_stock_krw},
                {"구분": "한국주식", "금액(KRW)": total_kr_stock_krw},
                {"구분": "원화자산", "금액(KRW)": total_krw_assets},
                {"구분": "달러자산", "금액(KRW)": total_usd_assets_krw},
            ]
        )
        type_df = type_df[type_df["금액(KRW)"] > 0]
        fig_type = px.pie(
            type_df, names="구분", values="금액(KRW)", hole=0.4, title="자산군별 비중"
        )
        st.plotly_chart(fig_type, use_container_width=True)
    with c2:
        if not unified_df.empty:
            fig_all = px.pie(
                unified_df, names="자산명", values="금액(KRW)", hole=0.4, title="전체 자산별 비중"
            )
            st.plotly_chart(fig_all, use_container_width=True)

    if not unified_df.empty:
        fig_bar = px.bar(
            unified_df.sort_values("비중%", ascending=True),
            x="비중%",
            y="자산명",
            color="분류",
            orientation="h",
            title="전체 자산 비중 (%)",
            text_auto=".1f",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        st.dataframe(
            unified_df.sort_values("금액(KRW)", ascending=False).style.format(
                {"금액(KRW)": "₩{:,.0f}", "금액(USD)": "${:,.2f}", "비중%": "{:.1f}%"}
            ),
            use_container_width=True,
            height=350,
        )

with tab_reb:
    st.caption("사이드바 '🎯 목표 비중 설정'에서 저장한 목표 비중을 기준으로 계산합니다.")
    target_sum = sum(target_map.values())
    if abs(target_sum - 100) > 0.5:
        st.warning(f"목표 비중 합계가 {target_sum:.1f}%로 100%가 아닙니다. 사이드바에서 조정 후 저장해주세요.")

    reb_chart_df = rebalance_df.melt(
        id_vars="구분", value_vars=["현재비중%", "목표비중%"], var_name="구분2", value_name="비중%"
    )
    fig_reb = px.bar(
        reb_chart_df, x="구분", y="비중%", color="구분2", barmode="group",
        title="현재 비중 vs 목표 비중", text_auto=".1f",
    )
    st.plotly_chart(fig_reb, use_container_width=True)

    st.dataframe(
        rebalance_df.style.format(
            {
                "현재금액(KRW)": "₩{:,.0f}",
                "현재비중%": "{:.1f}%",
                "목표비중%": "{:.1f}%",
                "차이%": "{:+.1f}%",
                "조정필요액(KRW)": "₩{:+,.0f}",
            }
        ),
        use_container_width=True,
    )
    st.caption("조정필요액이 **양수(+)면 매수**(비중 부족), **음수(-)면 매도**(비중 초과)가 필요하다는 뜻입니다.")

with tab_hist:
    hist_df = st.session_state.history.copy()
    if hist_df.empty:
        st.info("아직 기록된 자산 추이가 없습니다. 앱을 사용할 때마다 오늘 날짜 스냅샷이 자동으로 저장됩니다.")
    else:
        hist_df["Date"] = pd.to_datetime(hist_df["Date"])
        fig_hist = px.line(
            hist_df, x="Date", y="TotalKRW", markers=True, title="총자산 추이 (KRW)"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

        fig_hist_area = px.area(
            hist_df,
            x="Date",
            y=["USStockKRW", "KRStockKRW", "KRWAssetsKRW", "USDAssetsKRW"],
            title="자산군별 추이 (KRW)",
        )
        st.plotly_chart(fig_hist_area, use_container_width=True)

        st.dataframe(
            hist_df.sort_values("Date", ascending=False).style.format(
                {
                    "TotalKRW": "₩{:,.0f}",
                    "TotalUSD": "${:,.2f}",
                    "USStockKRW": "₩{:,.0f}",
                    "KRStockKRW": "₩{:,.0f}",
                    "KRWAssetsKRW": "₩{:,.0f}",
                    "USDAssetsKRW": "₩{:,.0f}",
                }
            ),
            use_container_width=True,
        )
        hist_csv_bytes = st.session_state.history.to_csv(index=False).encode("utf-8")
        st.download_button(
            "자산 추이 CSV 다운로드", hist_csv_bytes, "asset_history_export.csv", "text/csv", key="hist_dl"
        )
    st.caption("⚠️ 무료 클라우드 호스팅은 컨테이너가 재시작되면 기록이 초기화될 수 있습니다. 주기적으로 CSV 백업을 권장합니다.")

with tab1:
    if portfolio.empty:
        st.info("보유 중인 미국주식이 없습니다.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            fig = px.pie(
                portfolio, names="Ticker", values="MarketValueUSD", hole=0.4, title="종목별 자산 비중 (미국주식 내)"
            )
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = px.bar(
                portfolio.sort_values("Weight%", ascending=True),
                x="Weight%",
                y="Ticker",
                orientation="h",
                title="종목별 비중 (%)",
                text_auto=".1f",
            )
            st.plotly_chart(fig2, use_container_width=True)

with tab2:
    if portfolio.empty:
        st.info("보유 중인 미국주식이 없습니다.")
    else:
        sector_df = portfolio.groupby("Sector", as_index=False)["MarketValueUSD"].sum()
        c1, c2 = st.columns([1, 1])
        with c1:
            fig3 = px.pie(
                sector_df, names="Sector", values="MarketValueUSD", hole=0.4, title="섹터별 자산 비중"
            )
            st.plotly_chart(fig3, use_container_width=True)
        with c2:
            st.dataframe(
                sector_df.assign(
                    비중=(sector_df["MarketValueUSD"] / total_stock_usd * 100).round(1).astype(str) + "%"
                ).rename(columns={"MarketValueUSD": "평가금액(USD)"}),
                use_container_width=True,
            )

with tab3:
    if portfolio.empty:
        st.info("보유 중인 미국주식이 없습니다.")
    else:
        st.metric("총 손익 (미국주식)", f"${total_pnl_usd:,.2f}",
                   f"{(total_pnl_usd / total_cost_usd * 100) if total_cost_usd else 0:.2f}%")
        st.metric("일간 변동 (미국주식)", f"${total_day_change_usd:,.2f}")

        display_df = portfolio[
            [
                "Ticker",
                "Shares",
                "AvgCost",
                "CurrentPrice",
                "DayChangePct",
                "MarketValueUSD",
                "Weight%",
                "PnLUSD",
                "PnLPct",
                "Sector",
            ]
        ].sort_values("MarketValueUSD", ascending=False)

        st.dataframe(
            display_df.style.format(
                {
                    "Shares": "{:.2f}",
                    "AvgCost": "${:.2f}",
                    "CurrentPrice": "${:.2f}",
                    "DayChangePct": "{:.2f}%",
                    "MarketValueUSD": "${:,.2f}",
                    "Weight%": "{:.1f}%",
                    "PnLUSD": "${:,.2f}",
                    "PnLPct": "{:.2f}%",
                }
            ),
            use_container_width=True,
            height=400,
        )

with tab4:
    if kr_portfolio.empty:
        st.info("보유 중인 한국주식이 없습니다.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            fig_kr = px.pie(
                kr_portfolio, names="Ticker", values="MarketValueKRW", hole=0.4, title="종목별 자산 비중 (한국주식 내)"
            )
            st.plotly_chart(fig_kr, use_container_width=True)
        with c2:
            fig_kr2 = px.bar(
                kr_portfolio.sort_values("Weight%", ascending=True),
                x="Weight%",
                y="Ticker",
                orientation="h",
                title="종목별 비중 (%)",
                text_auto=".1f",
            )
            st.plotly_chart(fig_kr2, use_container_width=True)

with tab5:
    if kr_portfolio.empty:
        st.info("보유 중인 한국주식이 없습니다.")
    else:
        st.metric("총 손익 (한국주식)", f"₩{total_kr_pnl_krw:,.0f}",
                   f"{(total_kr_pnl_krw / total_kr_cost_krw * 100) if total_kr_cost_krw else 0:.2f}%")
        st.metric("일간 변동 (한국주식)", f"₩{total_kr_day_change_krw:,.0f}")

        kr_display_df = kr_portfolio[
            [
                "Ticker",
                "Shares",
                "AvgCost",
                "CurrentPrice",
                "DayChangePct",
                "MarketValueKRW",
                "Weight%",
                "PnLKRW",
                "PnLPct",
            ]
        ].sort_values("MarketValueKRW", ascending=False)

        st.dataframe(
            kr_display_df.style.format(
                {
                    "Shares": "{:.2f}",
                    "AvgCost": "₩{:,.0f}",
                    "CurrentPrice": "₩{:,.0f}",
                    "DayChangePct": "{:.2f}%",
                    "MarketValueKRW": "₩{:,.0f}",
                    "Weight%": "{:.1f}%",
                    "PnLKRW": "₩{:,.0f}",
                    "PnLPct": "{:.2f}%",
                }
            ),
            use_container_width=True,
            height=400,
        )
