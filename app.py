import email.utils
import html
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

import gspread
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from google.oauth2.service_account import Credentials

# =============================================================================
# 1. 페이지 기본 설정 및 구글 시트(블로그추이) 설정
# =============================================================================
st.set_page_config(
    page_title="차담진 블로그 일일 방문자수 추이",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

KST = timezone(timedelta(hours=9))
HISTORY_FILE = "visitor_history.json"
MAIN_BLUE = "#003BF5"

SPREADSHEET_ID = "14NIjDOA9y8RKuSCfm_-y5AScBQl49tOzv7Sxkv97LBw"
SHEET_TAB_NAME = "블로그추이"

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

INFO_CATEGORY_KEYWORDS = ["정보", "칼럼", "상식", "뉴스", "가이드", "꿀팁", "노하우", "자동차정보"]
REVIEW_CATEGORY_KEYWORDS = ["후기", "출고", "판매후기", "출고후기", "계약사례", "인도"]

INFO_TITLE_KEYWORDS = [
    "받는 법", "하는 법", "고르는 법", "구분법", "구별", "시세조회", "감가", "총정리",
    "점검 순서", "경고등", "원인", "증상", "해결", "대처", "관리법", "교체주기",
    "체크리스트", "가이드", "장단점", "차이점", "주의사항", "서류", "수수료",
    "취득세", "이전등록비", "성능점검", "카히스토리", "허위매물", "기준", "요령", "방법",
]

REVIEW_STRONG_PHRASES = [
    "판매후기", "출고후기", "리스후기", "렌트후기", "할부후기", "매입후기",
    "출고 도와", "출고도와", "출고했", "출고 완료", "인도해", "인도 완료",
    "방문해 주셨", "방문해주셨", "방문해 주신", "방문해주신",
    "고객님께서", "회원님께서", "차주님께서", "계약해 주셨", "계약해주셨",
    "시운전", "출고건", "계약 사례", "출고 사례",
]

BLOG_CHANNELS = [
    {"id": "va6xoti5qj", "name": "담소카", "group": "중고차·할부", "url": "https://blog.naver.com/va6xoti5qj"},
    {"id": "7avapfrvtbv", "name": "진담카", "group": "중고차·할부", "url": "https://blog.naver.com/7avapfrvtbv"},
    {"id": "jqqktejtgj", "name": "중부해", "group": "중고차·할부", "url": "https://blog.naver.com/jqqktejtgj"},
    {"id": "hanto2528", "name": "회파중", "group": "회생·파산·할부", "url": "https://blog.naver.com/hanto2528"},
    {"id": "8ah60uq", "name": "심운리스", "group": "오토리스·렌트", "url": "https://blog.naver.com/8ah60uq"},
    {"id": "sh-7200", "name": "파복회", "group": "회생·파산·할부", "url": "https://blog.naver.com/sh-7200"},
    {"id": "joongpahoe", "name": "중파회", "group": "회생·파산·할부", "url": "https://blog.naver.com/joongpahoe"},
    {"id": "43n3km-m10e4ee", "name": "차품딜", "group": "중고차·할부", "url": "https://blog.naver.com/43n3km-m10e4ee"},
    {"id": "ssswin00", "name": "여봉카", "group": "중고차·할부", "url": "https://blog.naver.com/ssswin00"},
    {"id": "dadamauto", "name": "다담오토리스", "group": "오토리스·렌트", "url": "https://blog.naver.com/dadamauto"},
    {"id": "simwooin00", "name": "리턴카", "group": "오토리스·렌트", "url": "https://blog.naver.com/simwooin00"},
    {"id": "vbsr27960", "name": "차담오토리스", "group": "오토리스·렌트", "url": "https://blog.naver.com/vbsr27960"},
    {"id": "kathyprovenzano", "name": "리품카", "group": "중고차·할부", "url": "https://blog.naver.com/kathyprovenzano"},
    {"id": "gpdltlsck", "name": "헤이신차", "group": "신차·장기렌트", "url": "https://blog.naver.com/gpdltlsck"},
    {"id": "easyplancar_", "name": "이지플랜카", "group": "신차·장기렌트", "url": "https://blog.naver.com/easyplancar_"},
    {"id": "carrocar", "name": "차로차", "group": "중고차·할부", "url": "https://blog.naver.com/carrocar"},
]

NAME_TO_ID = {b["name"]: b["id"] for b in BLOG_CHANNELS}

BASELINE_HISTORY = {
    "2026-11-12": {
        "va6xoti5qj": 297, "7avapfrvtbv": 103, "hanto2528": 120, "8ah60uq": 114,
        "sh-7200": 95, "joongpahoe": 103, "43n3km-m10e4ee": 97, "jqqktejtgj": 138,
        "simwooin00": 30, "vbsr27960": 12, "kathyprovenzano": 23, "gpdltlsck": 21,
        "easyplancar_": 9, "carrocar": 12,
    },
    "2026-11-13": {
        "va6xoti5qj": 229, "7avapfrvtbv": 114, "hanto2528": 117, "8ah60uq": 129,
        "sh-7200": 93, "joongpahoe": 104, "43n3km-m10e4ee": 84, "jqqktejtgj": 150,
        "simwooin00": 40, "vbsr27960": 19, "kathyprovenzano": 13, "gpdltlsck": 17,
        "easyplancar_": 6, "carrocar": 7,
    },
    "2026-11-14": {
        "va6xoti5qj": 208, "7avapfrvtbv": 104, "hanto2528": 107, "8ah60uq": 98,
        "sh-7200": 70, "joongpahoe": 100, "43n3km-m10e4ee": 83, "jqqktejtgj": 122,
        "simwooin00": 40, "vbsr27960": 12, "kathyprovenzano": 14, "gpdltlsck": 9,
        "easyplancar_": 8, "carrocar": 5,
    },
    "2026-11-15": {
        "va6xoti5qj": 211, "7avapfrvtbv": 110, "hanto2528": 101, "8ah60uq": 80,
        "sh-7200": 64, "joongpahoe": 83, "43n3km-m10e4ee": 86, "jqqktejtgj": 122,
        "simwooin00": 38, "vbsr27960": 13, "kathyprovenzano": 23, "gpdltlsck": 15,
        "easyplancar_": 2, "carrocar": 7,
    },
    "2026-11-16": {
        "va6xoti5qj": 289, "7avapfrvtbv": 162, "jqqktejtgj": 124, "hanto2528": 135,
        "8ah60uq": 85, "sh-7200": 68, "joongpahoe": 79, "43n3km-m10e4ee": 82,
        "ssswin00": 17, "dadamauto": 13, "simwooin00": 35, "vbsr27960": 14,
        "kathyprovenzano": 19, "gpdltlsck": 12, "easyplancar_": 5, "carrocar": 6,
    },
}

st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');

    html, body, [class*="css"], .stApp {
        font-family: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        background-color: #F6F8FC !important;
        color: #0F172A;
        letter-spacing: -0.02em;
    }

    .block-container {
        padding-top: 4.4rem !important;
        padding-bottom: 4rem !important;
        max-width: 1380px !important;
    }

    .top-hero-bar {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 6px solid #003BF5;
        border-radius: 18px;
        padding: 20px 24px;
        margin-bottom: 18px;
        box-shadow: 0 4px 16px rgba(0, 59, 245, 0.05);
    }
    .top-hero-title {
        font-size: 1.65rem;
        font-weight: 850;
        color: #0F172A;
        letter-spacing: -0.03em;
        margin: 0;
        line-height: 1.3;
    }
    .top-hero-sub {
        font-size: 0.88rem;
        font-weight: 500;
        color: #64748B;
        margin-top: 4px;
    }

    div.stButton > button[kind="primary"] {
        background-color: #003BF5 !important;
        border-color: #003BF5 !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 0.55rem 1rem !important;
        box-shadow: 0 4px 12px rgba(0, 59, 245, 0.22) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #002ED1 !important;
        border-color: #002ED1 !important;
    }

    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 18px;
        padding: 20px 22px;
        min-height: 142px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }
    .kpi-card-highlight {
        background: linear-gradient(135deg, #F5F8FF 0%, #FFFFFF 100%);
        border: 1.5px solid #003BF5;
        border-radius: 18px;
        padding: 20px 22px;
        min-height: 142px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 6px 18px rgba(0, 59, 245, 0.10);
    }
    .kpi-label {
        font-size: 0.82rem;
        font-weight: 700;
        color: #64748B;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.95rem;
        font-weight: 900;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.03em;
        line-height: 1.2;
        word-break: keep-all;
    }
    .kpi-top1-row {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 2px;
    }
    .kpi-top1-name {
        font-size: 1.45rem;
        font-weight: 850;
        color: #003BF5;
        letter-spacing: -0.03em;
        white-space: nowrap;
    }
    .kpi-top1-count {
        font-size: 1.65rem;
        font-weight: 900;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #475569;
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid #EEF2F6;
        font-variant-numeric: tabular-nums;
    }

    .blog-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 18px;
        padding: 20px;
        margin-bottom: 16px;
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
    }
    .blog-card:hover {
        border-color: #003BF5;
        box-shadow: 0 8px 24px rgba(0, 59, 245, 0.12);
        transform: translateY(-2px);
    }
    .blog-card-top1 {
        background: linear-gradient(180deg, #F5F8FF 0%, #FFFFFF 45%);
        border: 2px solid #003BF5;
        box-shadow: 0 6px 20px rgba(0, 59, 245, 0.10);
    }

    .rank-badge-1 {
        background: #003BF5;
        color: #FFFFFF;
        font-weight: 850;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.86rem;
        box-shadow: 0 2px 8px rgba(0, 59, 245, 0.30);
    }
    .rank-badge-23 {
        background: #E8EEFF;
        color: #003BF5;
        border: 1px solid #B8C9FF;
        font-weight: 800;
        padding: 3px 9px;
        border-radius: 8px;
        font-size: 0.84rem;
    }
    .rank-badge-mid {
        background: #1E293B;
        color: #FFFFFF;
        font-weight: 750;
        padding: 3px 9px;
        border-radius: 8px;
        font-size: 0.82rem;
    }
    .rank-badge-low {
        background: #F1F5F9;
        color: #475569;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 8px;
        font-size: 0.82rem;
    }

    .company-name {
        font-size: 1.32rem;
        font-weight: 850;
        color: #0F172A;
        letter-spacing: -0.03em;
    }
    .visitor-number-top {
        font-size: 2.25rem;
        font-weight: 900;
        color: #003BF5;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.04em;
        line-height: 1.1;
    }
    .visitor-number-normal {
        font-size: 2.15rem;
        font-weight: 900;
        color: #0F172A;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.04em;
        line-height: 1.1;
    }

    .delta-up {
        background: #E8EEFF;
        color: #003BF5;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-variant-numeric: tabular-nums;
    }
    .delta-down {
        background: #FFF1F2;
        color: #E11D48;
        font-weight: 800;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-variant-numeric: tabular-nums;
    }
    .delta-flat {
        background: #F1F5F9;
        color: #64748B;
        font-weight: 650;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 2. 구글 시트(블로그추이 탭) 영구 저장 · 불러오기 커넥터
# =============================================================================
def get_gsheet_worksheet():
    secret_key = None
    for key_name in ("gcp_service_account", "google_service_account", "service_account"):
        if key_name in st.secrets:
            secret_key = dict(st.secrets[key_name])
            break
    if not secret_key:
        return None, "구글 시트 미연결(로컬 저장 중)"

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(secret_key, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            ws = spreadsheet.worksheet(SHEET_TAB_NAME)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_TAB_NAME, rows=500, cols=20)
        return ws, "구글 시트(블로그추이) 실시간 연동됨"
    except Exception as e:
        return None, f"구글 시트 연결 확인 필요 ({type(e).__name__})"


def load_from_gsheet(ws) -> dict[str, dict[str, int]]:
    loaded: dict[str, dict[str, int]] = {}
    try:
        all_rows = ws.get_all_values()
        if len(all_rows) < 2:
            return loaded
        headers = [h.strip() for h in all_rows[0]]
        for row in all_rows[1:]:
            if not row or not re.match(r"^\d{4}-\d{2}-\d{2}$", row[0].strip()):
                continue
            d_str = row[0].strip()
            loaded[d_str] = {}
            for col_idx, col_name in enumerate(headers[1:], start=1):
                if col_idx >= len(row):
                    continue
                bid = NAME_TO_ID.get(col_name)
                if bid and row[col_idx].strip() != "":
                    val_clean = row[col_idx].replace(",", "").strip()
                    if val_clean.isdigit():
                        loaded[d_str][bid] = int(val_clean)
    except Exception:
        pass
    return loaded


def save_to_gsheet(ws, records: dict[str, dict[str, int]]) -> bool:
    try:
        headers = ["날짜"] + [b["name"] for b in BLOG_CHANNELS] + ["전체합계"]
        rows = [headers]
        for d_str in sorted(records.keys()):
            day_map = records[d_str]
            vals = [day_map.get(b["id"], "") for b in BLOG_CHANNELS]
            day_sum = sum(v for v in vals if isinstance(v, int))
            rows.append([d_str] + vals + [day_sum])
        ws.clear()
        ws.update(range_name="A1", values=rows, value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False


# =============================================================================
# 3. 네이버 블로그 방문자수 + 최근 포스팅(평일 5일 후기/정보 분류) 수집 엔진
# =============================================================================
def classify_post_type(title: str, category: str = "", description: str = "") -> str:
    """게시판/카테고리명(1순위) → 제목 패턴(2순위) → 본문 고객·출고 서사(3순위) 순으로 판별합니다."""
    cat_low = category.lower().strip()
    title_low = title.lower().strip()
    desc_clean = re.sub(r"<[^>]+>", " ", description or "").lower()

    # 1순위: 블로그 게시판/카테고리명 기준 (잘못된 게시판에 올라간 글도 바로 발견 가능)
    if cat_low:
        if any(kw in cat_low for kw in INFO_CATEGORY_KEYWORDS):
            return "정보"
        if any(kw in cat_low for kw in REVIEW_CATEGORY_KEYWORDS):
            return "후기"

    # 2순위: 제목에 명확한 후기 단어 또는 정보글 패턴이 있는 경우
    if any(kw in title_low for kw in ["후기", "출고", "인도", "겟!"]):
        return "후기"
    if any(kw in title_low for kw in INFO_TITLE_KEYWORDS):
        return "정보"

    # 3순위: 본문 도입부의 실제 고객 방문·출고 서사 문구 판별
    full_text = f"{title_low} {desc_clean}"
    if any(phrase in full_text for phrase in REVIEW_STRONG_PHRASES):
        return "후기"

    return "정보"


def get_recent_5_weekdays(ref_date_str: str) -> list[str]:
    """기준일 이하 가장 최근 평일(월~금) 5개 날짜(YYYY-MM-DD)를 오름차순으로 반환합니다."""
    try:
        cur_dt = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
    except Exception:
        cur_dt = datetime.now(KST).date()

    weekdays: list[str] = []
    scan_dt = cur_dt
    while len(weekdays) < 5:
        if scan_dt.weekday() < 5:  # 0=월, 1=화, 2=수, 3=목, 4=금
            weekdays.append(scan_dt.strftime("%Y-%m-%d"))
        scan_dt -= timedelta(days=1)
    weekdays.reverse()
    return weekdays


def fetch_blog_posts_by_date(blog_id: str) -> dict[str, list[dict[str, str]]]:
    """네이버 블로그 RSS 및 글 목록 API를 통해 날짜별 포스팅(후기/정보, 제목, 링크)을 수집합니다."""
    posts_by_date: dict[str, list[dict[str, str]]] = {}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://blog.naver.com/{blog_id}",
    }

    # 1차: 네이버 블로그 공식 RSS 피드 조회 (제목, 카테고리, 본문 요약, 정확한 발행일)
    rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
    try:
        resp = requests.get(rss_url, headers=headers, timeout=8)
        if resp.status_code == 200 and "<item>" in resp.text:
            root = ET.fromstring(resp.text)
            for item in root.findall("./channel/item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or f"https://blog.naver.com/{blog_id}").strip()
                pub_date_raw = (item.findtext("pubDate") or "").strip()
                category = (item.findtext("category") or "").strip()
                desc = (item.findtext("description") or "").strip()
                if not pub_date_raw:
                    continue
                try:
                    dt = email.utils.parsedate_to_datetime(pub_date_raw).astimezone(KST)
                    d_str = dt.strftime("%Y-%m-%d")
                    p_type = classify_post_type(title, category, desc)
                    posts_by_date.setdefault(d_str, []).append(
                        {"type": p_type, "title": title, "link": link}
                    )
                except Exception:
                    continue
    except Exception:
        pass

    # 2차 폴백: RSS가 비어있는 경우 PostTitleListAsync JSON 조회
    if not posts_by_date:
        list_url = (
            f"https://blog.naver.com/PostTitleListAsync.naver"
            f"?blogId={blog_id}&currentPage=1&countPerPage=30"
        )
        try:
            resp = requests.get(list_url, headers=headers, timeout=8)
            if resp.status_code == 200:
                cleaned = resp.text.replace("\\'", "'")
                data = json.loads(cleaned)
                for item in data.get("postList", []):
                    raw_title = urllib.parse.unquote(item.get("title", "")).replace("+", " ")
                    title = html.unescape(raw_title).strip()
                    add_date = str(item.get("addDate", "")).strip()
                    log_no = str(item.get("logNo", "")).strip()
                    link = f"https://blog.naver.com/{blog_id}/{log_no}" if log_no else f"https://blog.naver.com/{blog_id}"

                    d_str = None
                    m_dot = re.match(r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", add_date)
                    if m_dot:
                        d_str = f"{m_dot.group(1)}-{int(m_dot.group(2)):02d}-{int(m_dot.group(3)):02d}"
                    elif "전" in add_date or "방금" in add_date:
                        d_str = datetime.now(KST).strftime("%Y-%m-%d")

                    if d_str:
                        p_type = classify_post_type(title)
                        posts_by_date.setdefault(d_str, []).append(
                            {"type": p_type, "title": title, "link": link}
                        )
        except Exception:
            pass

    return posts_by_date


def fetch_single_blog(blog: dict) -> tuple[str, dict[str, int], dict[str, list[dict[str, str]]]]:
    """단일 블로그의 일별 방문자수(5일 XML + 모바일)와 최근 포스팅 목록을 함께 수집합니다."""
    blog_id = blog["id"]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://blog.naver.com/{blog_id}",
    }
    daily_counts: dict[str, int] = {}

    xml_url = f"https://blog.naver.com/NVisitorgp4Ajax.nhn?blogId={blog_id}"
    try:
        resp = requests.get(xml_url, headers=headers, timeout=8)
        if resp.status_code == 200 and "<visitorcnt" in resp.text:
            root = ET.fromstring(resp.text)
            for elem in root.findall("visitorcnt"):
                raw_date = elem.attrib.get("id", "")
                cnt_str = elem.attrib.get("cnt", "0")
                if len(raw_date) == 8 and cnt_str.isdigit():
                    iso_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                    daily_counts[iso_date] = int(cnt_str)
    except Exception:
        pass

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    try:
        m_headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            ),
            "Referer": f"https://m.blog.naver.com/{blog_id}",
        }
        m_resp = requests.get(f"https://m.blog.naver.com/{blog_id}", headers=m_headers, timeout=8)
        if m_resp.status_code == 200:
            match = re.search(r'"dayVisitorCount"\s*:\s*(\d+)', m_resp.text)
            if not match:
                match = re.search(r"오늘\s*<em[^>]*>([\d,]+)</em>", m_resp.text)
            if match:
                live_today = int(match.group(1).replace(",", ""))
                prev_val = daily_counts.get(today_str, 0)
                daily_counts[today_str] = max(prev_val, live_today)
    except Exception:
        pass

    posts_map = fetch_blog_posts_by_date(blog_id)
    return blog_id, daily_counts, posts_map


def load_local_history() -> dict[str, dict[str, int]]:
    merged: dict[str, dict[str, int]] = {d: dict(m) for d, m in BASELINE_HISTORY.items()}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                source_map = saved.get("records", saved) if "records" in saved else saved
                for d_str, b_map in source_map.items():
                    if isinstance(b_map, dict) and re.match(r"^\d{4}-\d{2}-\d{2}$", str(d_str)):
                        merged.setdefault(d_str, {}).update(
                            {k: int(v) for k, v in b_map.items() if v is not None}
                        )
        except Exception:
            pass
    return merged


def save_local_history(records: dict[str, dict[str, int]]) -> None:
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


@st.cache_data(ttl=900, show_spinner=False)
def collect_all_blogs_cached(_version: str = "v4") -> tuple[dict[str, dict[str, int]], dict[str, dict[str, list[dict[str, str]]]], str, int, str]:
    """구글 시트 + 로컬 기록을 불러온 뒤, 네이버 실시간 방문자수 및 포스팅 현황을 병합합니다."""
    records = load_local_history()
    posts_by_blog: dict[str, dict[str, list[dict[str, str]]]] = {}

    ws, gsheet_status = get_gsheet_worksheet()
    if ws is not None:
        gsheet_records = load_from_gsheet(ws)
        for d_str, b_map in gsheet_records.items():
            records.setdefault(d_str, {}).update(b_map)

    success_count = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_single_blog, blog) for blog in BLOG_CHANNELS]
        for future in as_completed(futures):
            try:
                blog_id, fetched_map, posts_map = future.result()
                posts_by_blog[blog_id] = posts_map
                if fetched_map:
                    success_count += 1
                    for d_str, cnt in fetched_map.items():
                        records.setdefault(d_str, {})[blog_id] = cnt
            except Exception:
                pass

    save_local_history(records)
    if ws is not None:
        saved_ok = save_to_gsheet(ws, records)
        gsheet_status = "구글 시트(블로그추이) 자동 저장 완료" if saved_ok else "구글 시트 저장 실패(권한 확인 필요)"

    updated_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    return records, posts_by_blog, updated_at, success_count, gsheet_status


# =============================================================================
# 4. 일별 · 월별 · 연도별 순위 및 통계 산출 함수
# =============================================================================
def build_ranked_dataframe(
    records: dict[str, dict[str, int]], selected_date: str, all_dates: list[str]
) -> pd.DataFrame:
    recent_5d = all_dates[-5:] if len(all_dates) >= 5 else all_dates
    completed_dates = [d for d in all_dates if d != all_dates[-1]] or all_dates

    sel_idx = all_dates.index(selected_date)
    prev_date = all_dates[sel_idx - 1] if sel_idx > 0 else None

    comp_curr_date = selected_date
    comp_prev_date = prev_date
    comp_label = f"{selected_date[5:]} 전일대비"

    if selected_date == all_dates[-1] and len(all_dates) >= 3:
        comp_curr_date = all_dates[-2]
        comp_prev_date = all_dates[-3]
        comp_label = f"{comp_curr_date[5:]} 마감 전일대비"

    cur_month_prefix = selected_date[:7]
    cur_year_prefix = selected_date[:4]
    month_dates = [d for d in all_dates if d.startswith(cur_month_prefix)]
    year_dates = [d for d in all_dates if d.startswith(cur_year_prefix)]

    rows = []
    for blog in BLOG_CHANNELS:
        bid = blog["id"]
        sel_val = records.get(selected_date, {}).get(bid, None)
        today_val = records.get(all_dates[-1], {}).get(bid, 0)
        yest_val = records.get(all_dates[-2], {}).get(bid, None) if len(all_dates) >= 2 else None

        c_curr = records.get(comp_curr_date, {}).get(bid, None) if comp_curr_date else None
        c_prev = records.get(comp_prev_date, {}).get(bid, None) if comp_prev_date else None

        if c_curr is not None and c_prev is not None:
            delta = c_curr - c_prev
            delta_pct = (delta / c_prev * 100.0) if c_prev > 0 else 0.0
            has_delta = True
        else:
            delta = 0
            delta_pct = 0.0
            has_delta = False

        valid_month = [records.get(d, {}).get(bid) for d in month_dates if records.get(d, {}).get(bid) is not None]
        sum_month = int(sum(valid_month)) if valid_month else 0

        valid_year = [records.get(d, {}).get(bid) for d in year_dates if records.get(d, {}).get(bid) is not None]
        sum_year = int(sum(valid_year)) if valid_year else 0

        valid_comp = [records.get(d, {}).get(bid) for d in completed_dates if records.get(d, {}).get(bid) is not None]
        avg_comp = int(round(sum(valid_comp) / len(valid_comp))) if valid_comp else int(today_val or 0)

        row_data = {
            "id": bid,
            "업체명": blog["name"],
            "분류": blog["group"],
            "블로그주소": blog["url"],
            "선택일방문자": sel_val if sel_val is not None else -1,
            "선택일표시": sel_val,
            "오늘실시간": int(today_val or 0),
            "어제마감": yest_val,
            "전일증감": delta,
            "전일증감률": delta_pct,
            "증감유효": has_delta,
            "비교기준": comp_label,
            "마감일평균": avg_comp,
            "월간누적합계": sum_month,
            "연간누적합계": sum_year,
        }
        for d in all_dates:
            row_data[d] = records.get(d, {}).get(bid, None)
        rows.append(row_data)

    df = pd.DataFrame(rows)
    df = df.sort_values(
        by=["선택일방문자", "어제마감", "월간누적합계"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    df["순위"] = df.index + 1
    return df


def build_period_summary_dataframe(
    records: dict[str, dict[str, int]], all_dates: list[str], target_prefix: str
) -> tuple[pd.DataFrame, list[str], int]:
    period_dates = [d for d in all_dates if d.startswith(target_prefix)]
    months_in_period = sorted({d[:7] for d in period_dates})

    rows = []
    for blog in BLOG_CHANNELS:
        bid = blog["id"]
        vals = [records.get(d, {}).get(bid) for d in period_dates if records.get(d, {}).get(bid) is not None]
        total_sum = int(sum(vals)) if vals else 0
        daily_avg = int(round(total_sum / len(vals))) if vals else 0
        max_val = int(max(vals)) if vals else 0

        item = {
            "업체명": blog["name"],
            "블로그ID": bid,
            "분류": blog["group"],
            "기간총합계": total_sum,
            "기간일평균": daily_avg,
            "최고일방문": max_val,
            "수집일수": len(vals),
            "블로그주소": blog["url"],
        }
        for m in months_in_period:
            m_vals = [
                records.get(d, {}).get(bid)
                for d in period_dates
                if d.startswith(m) and records.get(d, {}).get(bid) is not None
            ]
            item[f"{int(m[5:7])}월 합계"] = int(sum(m_vals)) if m_vals else 0
        rows.append(item)

    pdf = pd.DataFrame(rows).sort_values(by=["기간총합계", "기간일평균"], ascending=[False, False]).reset_index(drop=True)
    pdf["순위"] = pdf.index + 1
    grand_total = int(pdf["기간총합계"].sum())
    pdf["점유율(%)"] = pdf["기간총합계"].apply(lambda x: round(x / grand_total * 100.0, 1) if grand_total > 0 else 0.0)
    return pdf, months_in_period, len(period_dates)


def build_weekday_post_strip_html(blog_id: str, weekdays_5: list[str], posts_by_blog: dict) -> str:
    """각 카드 내 일별 방문자수 회색 박스 바로 아랫줄에 들어갈 '평일 5일 포스팅 현황' 5칸 HTML을 생성합니다."""
    blog_posts = posts_by_blog.get(blog_id, {})
    cells = []

    for d_str in weekdays_5:
        dt_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        wd_kr = WEEKDAY_KR[dt_obj.weekday()]
        short_date = f"{dt_obj.month}/{dt_obj.day}({wd_kr})"
        day_items = blog_posts.get(d_str, [])

        if not day_items:
            cell_html = (
                f'<div style="flex:1; text-align:center; background:#F8FAFC; border:1px dashed #CBD5E1; '
                f'color:#94A3B8; padding:5px 2px; border-radius:8px; font-size:0.76rem;">'
                f'<div style="font-size:0.65rem; color:#94A3B8; font-weight:600;">{short_date}</div>'
                f'<div style="margin-top:2px; font-weight:700;">미등록</div></div>'
            )
        else:
            types = {p["type"] for p in day_items}
            first_link = html.escape(day_items[0].get("link", f"https://blog.naver.com/{blog_id}"), quote=True)
            tooltip = html.escape(" / ".join(p.get("title", "") for p in day_items), quote=True)
            cnt_suffix = f"×{len(day_items)}" if len(day_items) > 1 else ""

            if "후기" in types and "정보" in types:
                bg_style = "background:linear-gradient(135deg, #003BF5 0%, #00B894 100%); color:#FFFFFF;"
                date_color = "#E0E7FF"
                label_txt = "후기+정보"
            elif "후기" in types:
                bg_style = "background:#003BF5; color:#FFFFFF;"
                date_color = "#DBEAFE"
                label_txt = f"후기{cnt_suffix}"
            else:
                bg_style = "background:#00B894; color:#FFFFFF;"
                date_color = "#D1FAE5"
                label_txt = f"정보{cnt_suffix}"

            cell_html = (
                f'<a href="{first_link}" target="_blank" title="{tooltip}" '
                f'style="flex:1; text-decoration:none; text-align:center; {bg_style} '
                f'padding:5px 2px; border-radius:8px; font-size:0.78rem; display:block; box-shadow:0 1px 3px rgba(15,23,42,0.08);">'
                f'<div style="font-size:0.64rem; color:{date_color}; font-weight:600;">{short_date}</div>'
                f'<div style="margin-top:2px; font-weight:800;">{label_txt}</div></a>'
            )
        cells.append(cell_html)

    return "".join(cells)


# =============================================================================
# 5. 메인 화면 렌더링
# =============================================================================
def main() -> None:
    records, posts_by_blog, updated_at, live_count, gsheet_status = collect_all_blogs_cached()
    all_dates = sorted(records.keys())
    recent_5d = all_dates[-5:] if len(all_dates) >= 5 else all_dates

    col_title, col_date, col_btn = st.columns([5.6, 2.4, 2.0])
    with col_title:
        st.markdown(
            f"""
            <div class="top-hero-bar">
                <div class="top-hero-title">차담진 블로그 일일 방문자수 추이</div>
                <div class="top-hero-sub">
                    관리 채널 16개 · 조회수 순위 자동 정렬 · 누적 {len(all_dates)}일 기록 중 · {gsheet_status} ({updated_at} KST)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_date:
        st.write("")
        date_options = list(reversed(all_dates))
        date_labels = {
            d: f"📅 {d} (오늘 실시간 순위)" if d == all_dates[-1] else f"📅 {d} (마감 순위)"
            for d in date_options
        }
        selected_date = st.selectbox(
            "조회 기준일",
            options=date_options,
            format_func=lambda x: date_labels[x],
            label_visibility="collapsed",
        )
    with col_btn:
        st.write("")
        if st.button("🔄 실시간 수치 새로고침", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()

    if "미연결" in gsheet_status or "확인 필요" in gsheet_status:
        with st.expander("⚙️ 구글 시트(블로그추이) 자동 저장 연결 방법 안내 (최초 1회 설정)"):
            st.markdown(
                f"""
                1. 구글 시트([열기](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit))에 **`{SHEET_TAB_NAME}`** 탭을 만들고, 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)을 **편집자**로 공유합니다.
                2. Streamlit Cloud 앱 화면 우측 하단 **Manage app → Settings → Secrets**에 `[gcp_service_account]` 키를 붙여넣고 저장하면 영구 자동 저장이 시작됩니다.
                """
            )

    df = build_ranked_dataframe(records, selected_date, all_dates)
    weekdays_5 = get_recent_5_weekdays(selected_date)

    # KPI 4개 카드
    sel_total = int(df["선택일표시"].dropna().sum())
    yest_date = all_dates[-2] if len(all_dates) >= 2 else all_dates[-1]
    yest_total = int(sum(records.get(yest_date, {}).values()))
    month_total = int(df["월간누적합계"].sum())
    high_100_cnt = int((df["어제마감"].fillna(df["오늘실시간"]) >= 100).sum())
    cur_month_num = int(selected_date[5:7])

    top1 = df.iloc[0]
    top1_val = int(top1["선택일표시"]) if pd.notna(top1["선택일표시"]) else 0
    top1_share = (top1_val / sel_total * 100.0) if sel_total > 0 else 0.0

    valid_delta_df = df[df["증감유효"]].copy()
    if not valid_delta_df.empty:
        surging_row = valid_delta_df.sort_values("전일증감", ascending=False).iloc[0]
        drop_row = valid_delta_df.sort_values("전일증감", ascending=True).iloc[0]
    else:
        surging_row = top1
        drop_row = top1

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        label_1 = "오늘 실시간 총 방문자 (16개 합산)" if selected_date == all_dates[-1] else f"{selected_date[5:]} 마감 총 방문자"
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">{label_1}</div>
                <div class="kpi-value" style="color:#003BF5;">{sel_total:,}<span style="font-size:1.0rem; font-weight:600; color:#64748B; margin-left:3px;">명</span></div>
                <div class="kpi-sub">어제({yest_date[5:]}) 마감 합산: <strong>{yest_total:,}명</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        avg_yest = yest_total / 14.0
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">이번 달({cur_month_num}월) 누적 방문자 합계</div>
                <div class="kpi-value">{month_total:,}<span style="font-size:1.0rem; font-weight:600; color:#64748B; margin-left:3px;">명</span></div>
                <div class="kpi-sub">어제 평균 <strong>{avg_yest:.1f}명</strong> · 일 100명↑ <strong>{high_100_cnt}개 업체</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="kpi-card-highlight">
                <div class="kpi-label" style="color:#003BF5;">👑 조회수 1위 업체 (점유율 {top1_share:.1f}%)</div>
                <div class="kpi-top1-row">
                    <span class="kpi-top1-name">1위 {top1['업체명']}</span>
                    <span class="kpi-top1-count">{top1_val:,}<span style="font-size:0.95rem; font-weight:600; color:#475569;">명</span></span>
                </div>
                <div class="kpi-sub">어제 <strong>{int(top1['어제마감'] or 0):,}명</strong> · {cur_month_num}월 누적 <strong>{int(top1['월간누적합계']):,}명</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k4:
        s_sign = "+" if surging_row["전일증감"] >= 0 else ""
        d_sign = "+" if drop_row["전일증감"] >= 0 else ""
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">마감일 전일 대비 등락 (최고 상승 · 하락)</div>
                <div style="font-size:0.98rem; font-weight:800; margin-top:4px; color:#003BF5;">
                    ▲ 상승 1위: {surging_row['업체명']} ({s_sign}{int(surging_row['전일증감'])}명 / {s_sign}{surging_row['전일증감률']:.1f}%)
                </div>
                <div class="kpi-sub" style="color:#E11D48; font-weight:800;">
                    ▼ 최대 하락: {drop_row['업체명']} ({d_sign}{int(drop_row['전일증감'])}명 / {d_sign}{drop_row['전일증감률']:.1f}%)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    tab1, tab2, tab3 = st.tabs([
        "📈 일별 조회수 순위 대시보드",
        "🗓️ 월별 · 연도별 데이터 정리",
        "📋 일자별 전체 비교표 & 백업",
    ])

    with tab1:
        c_left, c_right = st.columns([3.0, 7.0])
        with c_left:
            chart_mode = st.radio(
                "차트 분석 모드",
                options=["전체 합산 추이", "상위 5개 업체 컬러 비교", "개별 업체 상세 추이"],
                horizontal=False,
            )
            selected_blog_name = st.selectbox(
                "개별 분석 업체 선택 (조회수 순위순)",
                options=df["업체명"].tolist(),
                format_func=lambda name: f"{int(df.loc[df['업체명']==name, '순위'].values[0])}위 · {name}",
            )
            include_today = st.toggle("오늘 실시간 수치 그래프 포함", value=True)

        with c_right:
            plot_dates = all_dates if include_today else all_dates[:-1]
            fig = go.Figure()
            max_y_val = 10

            if chart_mode == "전체 합산 추이":
                y_totals = [
                    sum(records.get(d, {}).get(b["id"], 0) for b in BLOG_CHANNELS)
                    for d in plot_dates
                ]
                if y_totals:
                    max_y_val = max(y_totals)
                fig.add_trace(
                    go.Scatter(
                        x=[d[5:].replace("-", "/") for d in plot_dates],
                        y=y_totals,
                        mode="lines+markers+text",
                        text=[f"{v:,}명" for v in y_totals],
                        textposition="top center",
                        textfont=dict(size=13, color="#003BF5", family="Pretendard Variable, Pretendard, sans-serif"),
                        cliponaxis=False,
                        name="16개 블로그 합산",
                        line=dict(color="#003BF5", width=3.5),
                        marker=dict(size=9, color="#003BF5"),
                        fill="tozeroy",
                        fillcolor="rgba(0, 59, 245, 0.10)",
                    )
                )
            elif chart_mode == "상위 5개 업체 컬러 비교":
                palette = ["#003BF5", "#FF2E4C", "#00B894", "#FF8A00", "#7C3AED"]
                top5_df = df[df["어제마감"].notna()].head(5)
                for idx, (_, r) in enumerate(top5_df.iterrows()):
                    y_vals = [records.get(d, {}).get(r["id"], None) for d in plot_dates]
                    valid_y = [v for v in y_vals if v is not None]
                    if valid_y:
                        max_y_val = max(max_y_val, max(valid_y))
                    fig.add_trace(
                        go.Scatter(
                            x=[d[5:].replace("-", "/") for d in plot_dates],
                            y=y_vals,
                            mode="lines+markers",
                            cliponaxis=False,
                            name=f"{int(r['순위'])}위 {r['업체명']}",
                            line=dict(color=palette[idx % len(palette)], width=3 if idx == 0 else 2.4),
                            marker=dict(size=8 if idx == 0 else 6),
                        )
                    )
            else:
                target_row = df[df["업체명"] == selected_blog_name].iloc[0]
                y_vals = [records.get(d, {}).get(target_row["id"], None) for d in plot_dates]
                valid_y = [v for v in y_vals if v is not None]
                avg_val = int(target_row["마감일평균"])
                if valid_y:
                    max_y_val = max(max(valid_y), avg_val)
                fig.add_trace(
                    go.Scatter(
                        x=[d[5:].replace("-", "/") for d in plot_dates],
                        y=y_vals,
                        mode="lines+markers+text",
                        text=[f"{v:,}명" if v is not None else "" for v in y_vals],
                        textposition="top center",
                        textfont=dict(size=13, color="#003BF5", family="Pretendard Variable, Pretendard, sans-serif"),
                        cliponaxis=False,
                        name=f"{target_row['업체명']} 일일 방문자",
                        line=dict(color="#003BF5", width=3.5),
                        marker=dict(size=9, color="#003BF5"),
                        fill="tozeroy",
                        fillcolor="rgba(0, 59, 245, 0.11)",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[d[5:].replace("-", "/") for d in plot_dates],
                        y=[avg_val] * len(plot_dates),
                        mode="lines",
                        cliponaxis=False,
                        name=f"마감일 평균 ({avg_val:,}명)",
                        line=dict(color="#FF2E4C", width=2, dash="dash"),
                    )
                )

            fig.update_layout(
                height=340,
                margin=dict(l=20, r=20, t=44, b=20),
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                hovermode="x unified",
                font=dict(family="Pretendard Variable, Pretendard, sans-serif", size=13, color="#1E293B"),
                legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
                yaxis=dict(
                    gridcolor="#EEF2F6",
                    zeroline=False,
                    range=[0, max(max_y_val * 1.28, 10)],
                ),
                xaxis=dict(gridcolor="#F8FAFC", tickfont=dict(size=13)),
            )
            st.plotly_chart(fig, use_container_width=True)

        f_col1, f_col2, f_col3 = st.columns([4, 3, 3])
        with f_col1:
            search_q = st.text_input("🔍 업체명 또는 블로그 ID 검색", placeholder="예: 담소카, 심운리스, va6xoti5qj")
        with f_col2:
            status_filter = st.selectbox(
                "상태 필터",
                options=["전체 업체 (16개)", "전일 대비 상승 ▲", "전일 대비 하락 ▼", "일 100명 이상 상위권"],
            )
        with f_col3:
            sort_option = st.selectbox(
                "정렬 기준",
                options=[
                    "선택일 방문자 순위순 (기본)",
                    "어제 마감 방문자 높은순",
                    "이번 달 누적 합계 높은순",
                    "전일 대비 상승폭순",
                ],
            )

        # 포스팅 구분 범례 바
        st.markdown(
            "".join([
                '<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; ',
                'background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:10px 16px; margin-bottom:14px; font-size:0.82rem;">',
                '<div style="font-weight:750; color:#334155;">📌 카드 하단 평일 5일(월~금) 포스팅 자동 분류 안내 (칸 클릭 시 해당 글로 이동)</div>',
                '<div style="display:flex; align-items:center; gap:14px; font-weight:700;">',
                '<span style="display:inline-flex; align-items:center; gap:5px; color:#003BF5;"><span style="width:10px; height:10px; border-radius:3px; background:#003BF5; display:inline-block;"></span>후기성 글</span>',
                '<span style="display:inline-flex; align-items:center; gap:5px; color:#00B894;"><span style="width:10px; height:10px; border-radius:3px; background:#00B894; display:inline-block;"></span>정보성 글</span>',
                '<span style="display:inline-flex; align-items:center; gap:5px; color:#94A3B8;"><span style="width:10px; height:10px; border-radius:3px; border:1px dashed #CBD5E1; background:#F8FAFC; display:inline-block;"></span>미등록</span>',
                '</div></div>',
            ]),
            unsafe_allow_html=True,
        )

        filtered_df = df.copy()
        if search_q.strip():
            q = search_q.strip().lower()
            filtered_df = filtered_df[
                filtered_df["업체명"].str.lower().str.contains(q)
                | filtered_df["id"].str.lower().str.contains(q)
            ]
        if status_filter == "전일 대비 상승 ▲":
            filtered_df = filtered_df[filtered_df["증감유효"] & (filtered_df["전일증감"] > 0)]
        elif status_filter == "전일 대비 하락 ▼":
            filtered_df = filtered_df[filtered_df["증감유효"] & (filtered_df["전일증감"] < 0)]
        elif status_filter == "일 100명 이상 상위권":
            filtered_df = filtered_df[filtered_df["어제마감"].fillna(filtered_df["오늘실시간"]) >= 100]

        if sort_option == "어제 마감 방문자 높은순":
            filtered_df = filtered_df.sort_values(by=["어제마감", "오늘실시간"], ascending=[False, False])
        elif sort_option == "이번 달 누적 합계 높은순":
            filtered_df = filtered_df.sort_values(by="월간누적합계", ascending=False)
        elif sort_option == "전일 대비 상승폭순":
            filtered_df = filtered_df.sort_values(by="전일증감", ascending=False)

        max_sel_visitor = max(int(df["선택일방문자"].max()), 1)

        grid_cols = st.columns(4)
        for idx, (_, row) in enumerate(filtered_df.iterrows()):
            rank_num = int(row["순위"])
            if rank_num == 1:
                badge_cls = "rank-badge-1"
                card_cls = "blog-card blog-card-top1"
                num_cls = "visitor-number-top"
                bar_color = "#003BF5"
            elif rank_num <= 3:
                badge_cls = "rank-badge-23"
                card_cls = "blog-card"
                num_cls = "visitor-number-top"
                bar_color = "#2563EB"
            elif rank_num <= 8:
                badge_cls = "rank-badge-mid"
                card_cls = "blog-card"
                num_cls = "visitor-number-normal"
                bar_color = "#475569"
            else:
                badge_cls = "rank-badge-low"
                card_cls = "blog-card"
                num_cls = "visitor-number-normal"
                bar_color = "#94A3B8"

            if row["증감유효"]:
                d_val = int(row["전일증감"])
                d_pct = row["전일증감률"]
                if d_val > 0:
                    delta_html = f'<span class="delta-up">▲ +{d_val}명 (+{d_pct:.1f}%)</span>'
                elif d_val < 0:
                    delta_html = f'<span class="delta-down">▼ {d_val}명 ({d_pct:.1f}%)</span>'
                else:
                    delta_html = '<span class="delta-flat">보합 0명 (0.0%)</span>'
            else:
                delta_html = '<span class="delta-flat">그래프 위젯 미표시</span>'

            sel_raw = int(row["선택일표시"]) if pd.notna(row["선택일표시"]) else 0
            sel_v = f"{sel_raw:,}" if pd.notna(row["선택일표시"]) else "-"
            yest_v = f"{int(row['어제마감']):,}명" if pd.notna(row["어제마감"]) else "미표시"
            ratio_pct = min(100, max(4, int(round(sel_raw / max_sel_visitor * 100)))) if sel_raw > 0 else 0

            # 윗줄: 최근 5일 방문자수 회색/파란색 박스
            mini_days = []
            for d in recent_5d:
                v = row.get(d, None)
                v_txt = f"{int(v):,}" if pd.notna(v) else "-"
                if d == selected_date:
                    box_style = "background:#003BF5; color:#FFFFFF; font-weight:800;"
                    day_lbl_color = "#DBEAFE"
                else:
                    box_style = "background:#F1F5F9; color:#1E293B; font-weight:700;"
                    day_lbl_color = "#64748B"
                mini_days.append(
                    f'<div style="flex:1; text-align:center; {box_style} padding:6px 2px; border-radius:8px; font-size:0.84rem; font-variant-numeric:tabular-nums;">'
                    f'<div style="color:{day_lbl_color}; font-size:0.68rem; font-weight:600;">{d[8:]}일</div>'
                    f'<div style="margin-top:1px;">{v_txt}</div></div>'
                )
            mini_strip_html = "".join(mini_days)

            # 아랫줄: 평일 5일(월~금) 포스팅 현황 색상 구분 박스 (후기=#003BF5 / 정보=#00B894 / 미등록=회색점선)
            post_strip_html = build_weekday_post_strip_html(row["id"], weekdays_5, posts_by_blog)

            card_html = "".join([
                f'<div class="{card_cls}">',
                '<div style="display:flex; justify-content:space-between; align-items:center; gap:6px;">',
                '<div style="display:flex; align-items:center; gap:8px; min-width:0;">',
                f'<span class="{badge_cls}">{rank_num}위</span>',
                f'<span class="company-name" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{row["업체명"]}</span>',
                '</div>',
                f'<a href="{row["블로그주소"]}" target="_blank" style="font-size:0.8rem; color:#003BF5; text-decoration:none; font-weight:750; flex-shrink:0;">열기 ↗</a>',
                '</div>',
                f'<div style="font-size:0.78rem; color:#64748B; margin-top:4px; font-weight:500;">{row["id"]} · {row["분류"]}</div>',
                '<div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:14px;">',
                '<div>',
                f'<div style="font-size:0.76rem; font-weight:650; color:#64748B; margin-bottom:2px;">{selected_date[5:]} 방문자수</div>',
                f'<div class="{num_cls}">{sel_v}<span style="font-size:0.95rem; font-weight:700; color:#475569; margin-left:3px;">명</span></div>',
                '</div>',
                '<div style="text-align:right;">',
                f'<div style="font-size:0.7rem; color:#64748B; margin-bottom:4px; font-weight:600;">{row["비교기준"]}</div>',
                f'{delta_html}',
                '</div>',
                '</div>',
                '<div style="width:100%; height:6px; background:#EEF2F6; border-radius:999px; margin-top:12px; overflow:hidden;">',
                f'<div style="width:{ratio_pct}%; height:100%; background:{bar_color}; border-radius:999px;"></div>',
                '</div>',
                '<div style="display:flex; gap:5px; margin-top:12px; padding-top:12px; border-top:1px solid #EEF2F6;">',
                f'{mini_strip_html}',
                '</div>',
                '<div style="margin-top:8px; padding-top:8px; border-top:1px dashed #E2E8F0;">',
                '<div style="display:flex; justify-content:space-between; align-items:center; font-size:0.68rem; color:#64748B; font-weight:700; margin-bottom:5px;">',
                '<span>평일 5일 포스팅 현황</span>',
                '<span><span style="color:#003BF5;">●후기</span> <span style="color:#00B894; margin-left:4px;">●정보</span></span>',
                '</div>',
                '<div style="display:flex; gap:5px;">',
                f'{post_strip_html}',
                '</div>',
                '</div>',
                '<div style="display:flex; justify-content:space-between; font-size:0.82rem; color:#475569; margin-top:10px; padding-top:8px; border-top:1px solid #F1F5F9; font-weight:600;">',
                f'<span>어제 마감: <strong style="color:#0F172A; font-weight:800;">{yest_v}</strong></span>',
                f'<span>{cur_month_num}월 누적: <strong style="color:#003BF5; font-weight:800;">{int(row["월간누적합계"]):,}명</strong></span>',
                '</div>',
                '</div>',
            ])
            with grid_cols[idx % 4]:
                st.markdown(card_html, unsafe_allow_html=True)

    with tab2:
        st.markdown("#### 🗓️ 월별 · 연도별 누적 방문자 정리 리포트")
        available_years = sorted({d[:4] for d in all_dates}, reverse=True)
        available_months = sorted({d[:7] for d in all_dates}, reverse=True)

        p_col1, p_col2, p_col3 = st.columns([2.5, 3.5, 4.0])
        with p_col1:
            unit_choice = st.radio("집계 단위 선택", options=["월별 데이터 정리", "연도별 데이터 정리"], horizontal=True)
        with p_col2:
            if unit_choice == "월별 데이터 정리":
                target_prefix = st.selectbox(
                    "조회할 연-월 선택",
                    options=available_months,
                    format_func=lambda m: f"{m[:4]}년 {int(m[5:7])}월",
                )
                period_title = f"{target_prefix[:4]}년 {int(target_prefix[5:7])}월 월간"
            else:
                target_prefix = st.selectbox(
                    "조회할 연도 선택",
                    options=available_years,
                    format_func=lambda y: f"{y}년 연간 전체",
                )
                period_title = f"{target_prefix}년 연간"

        pdf, months_in_period, tracked_days = build_period_summary_dataframe(records, all_dates, target_prefix)

        with p_col3:
            st.info(
                f"**{period_title}** 누적 수집일수: **{tracked_days}일** · "
                f"16개 블로그 총합: **{int(pdf['기간총합계'].sum()):,}명**"
            )

        max_bar_val = max(int(pdf["기간총합계"].max()), 10)
        bar_colors = [
            "#003BF5" if i == 0 else ("#2563EB" if i < 3 else ("#4F46E5" if i < 8 else "#94A3B8"))
            for i in range(len(pdf))
        ]
        fig_p = go.Figure(
            go.Bar(
                x=[f"{int(r['순위'])}위 {r['업체명']}" for _, r in pdf.iterrows()],
                y=pdf["기간총합계"],
                text=[f"{int(v):,}명" for v in pdf["기간총합계"]],
                textposition="outside",
                textfont=dict(size=13, color="#0F172A", family="Pretendard Variable, Pretendard, sans-serif"),
                cliponaxis=False,
                marker_color=bar_colors,
            )
        )
        fig_p.update_layout(
            title=dict(text=f"{period_title} 업체별 누적 방문자 순위 (1위~16위)", font=dict(size=16, color="#0F172A")),
            height=360,
            margin=dict(l=20, r=20, t=56, b=24),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(family="Pretendard Variable, Pretendard, sans-serif", size=13),
            yaxis=dict(gridcolor="#EEF2F6", range=[0, max_bar_val * 1.25]),
            xaxis=dict(tickfont=dict(size=13)),
        )
        st.plotly_chart(fig_p, use_container_width=True)

        month_cols = [f"{int(m[5:7])}월 합계" for m in months_in_period]
        ordered_cols = ["순위", "업체명", "블로그ID", "분류"] + month_cols + [
            "기간총합계", "기간일평균", "최고일방문", "점유율(%)", "수집일수", "블로그주소"
        ]
        st.dataframe(pdf[ordered_cols], use_container_width=True, hide_index=True)

        period_csv = pdf[ordered_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=f"⬇ {period_title} 순위 정리 리포트 엑셀(CSV) 다운로드",
            data=period_csv,
            file_name=f"블로그_{period_title.replace(' ', '_')}_리포트.csv",
            mime="text/csv",
            type="primary",
        )

    with tab3:
        st.markdown("#### 📋 16개 업체 조회수 순위별 일자별 방문자수 전체 비교표")
        display_cols = ["순위", "업체명", "id", "분류"] + all_dates + ["마감일평균", "월간누적합계", "연간누적합계", "블로그주소"]
        table_df = df[display_cols].rename(
            columns={
                "id": "블로그ID",
                "마감일평균": "마감일평균(명)",
                "월간누적합계": f"{cur_month_num}월합계(명)",
                "연간누적합계": f"{selected_date[:4]}년합계(명)",
            }
        )
        st.dataframe(table_df, use_container_width=True, hide_index=True)

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            csv_bytes = table_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="⬇ 전체 일자 및 월간·연간 합계 엑셀(CSV) 다운로드",
                data=csv_bytes,
                file_name=f"블로그_일일방문자수_누적순위_{selected_date}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )
        with b_col2:
            json_bytes = json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                label="💾 누적 히스토리 원본(visitor_history.json) 백업 다운로드",
                data=json_bytes,
                file_name=f"visitor_history_{selected_date}.json",
                mime="application/json",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
