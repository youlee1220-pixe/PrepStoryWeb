# ===========================================
# PrepStory 학원 성적·진도 관리 시스템 (웹버전)
# -------------------------------------------
# 로그인(ID/비밀번호) + 역할(원장/담임) 분리
# 단원명→학기 자동추출 / 진도 누적그래프 / PDF 생성 포함
# ===========================================

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import os, re, datetime, textwrap

# --------------------------
# 파일 설정
# --------------------------
USERS_FILE = "users.csv"
DATA_FILE = "prepstory_scores.csv"
LOGO_FILE = "로고.gif"
SLOGAN_FILE = "미래의이야기를그려가는곳.jpg"

# 색상
GRAY = "#B0BEC5"
RED = "#C62828"

st.set_page_config(page_title="PrepStory 학원 성적·진도 관리", layout="wide")

# --------------------------
# 유저 데이터 로드
# --------------------------
@st.cache_data
def load_users():
    if not os.path.exists(USERS_FILE):
        st.error("⚠️ users.csv 파일이 없습니다.")
        return pd.DataFrame(columns=["ID", "이름", "역할", "비밀번호"])
    return pd.read_csv(USERS_FILE)

def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=[
            "학생명","학년","반","월","단원명","학기",
            "전체문항","맞은문항","정답률","단원평가","진도진행률",
            "코멘트","작성자_ID","작성시각"
        ]).to_csv(DATA_FILE, index=False)

# --------------------------
# Helper Functions
# --------------------------
def extract_term(unit_name: str):
    m = re.search(r"(초|중|고)\d-\d", str(unit_name))
    return m.group() if m else ""

def get_prev_progress(df, student, term, month):
    df_s = df[(df["학생명"] == student) & (df["학기"] == term)]
    prev_months = sorted(df_s["월"].unique())
    prev = [m for m in prev_months if m < month]
    if not prev: return 0.0
    last = max(prev)
    return float(df_s[df_s["월"] == last]["진도진행률"].astype(float).max())

def make_progress_bar(term, prev_val, curr_val):
    added = max(0, curr_val - prev_val)
    fig, ax = plt.subplots(figsize=(6, 1))
    ax.barh([term], [prev_val], color=GRAY, height=0.5)
    ax.barh([term], [added], left=[prev_val], color=RED, height=0.5)
    ax.set_xlim(0, 100)
    ax.set_xticks([0,20,40,60,80,100])
    ax.set_xlabel("%")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.legend(["지난달","이번달"], loc="center right", frameon=False)
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# --------------------------
# 로그인 화면
# --------------------------
users = load_users()
ensure_data_file()
df_all = pd.read_csv(DATA_FILE)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 PrepStory 학원 성적·진도 관리 로그인")
    id_in = st.text_input("ID")
    pw_in = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        user = users[(users["ID"] == id_in) & (users["비밀번호"] == pw_in)]
        if not user.empty:
            st.session_state.logged_in = True
            st.session_state.user_id = user.iloc[0]["ID"]
            st.session_state.user_name = user.iloc[0]["이름"]
            st.session_state.role = user.iloc[0]["역할"]
            st.success(f"{st.session_state.user_name}님 환영합니다!")
            st.rerun()
        else:
            st.error("로그인 정보가 올바르지 않습니다.")
    st.stop()

# --------------------------
# 로그인 후 메인 화면
# --------------------------
role = st.session_state.role
user_id = st.session_state.user_id
user_name = st.session_state.user_name

st.sidebar.success(f"👤 {user_name} ({role}) 로그인 중")
menu = st.sidebar.radio("메뉴 선택", ["성적 입력/수정", "리포트 보기", "데이터 관리" if role=="admin" else None])

# --------------------------
# 입력 / 수정
# --------------------------
if menu == "성적 입력/수정":
    st.header("📝 성적 및 진도 입력/수정")

    with st.form("input_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("학생명")
            grade = st.text_input("학년", "")
            clazz = st.text_input("반", "")
            month = st.text_input("월 (예: 2025-10)", datetime.datetime.now().strftime("%Y-%m"))
            unit = st.text_input("단원명 (예: 초5-2 분수의 곱셈)")
        with c2:
            total = st.number_input("전체 문항 수", 1, 100, 20)
            correct = st.number_input("맞은 문항 수", 0, 100, 20)
            unit_score = st.number_input("단원평가 점수 (%)", 0.0, 100.0, 100.0, step=0.1)
            progress = st.number_input("이번달 진도 (%)", 0.0, 100.0, 0.0, step=0.1)
            comment = st.text_area("강사 코멘트", "")
        if st.form_submit_button("저장"):
            accuracy = round(correct/total*100, 1)
            term = extract_term(unit)
            new = {
                "학생명": name, "학년": grade, "반": clazz, "월": month, "단원명": unit, "학기": term,
                "전체문항": total, "맞은문항": correct, "정답률": accuracy,
                "단원평가": unit_score, "진도진행률": progress,
                "코멘트": comment, "작성자_ID": user_id, "작성시각": datetime.datetime.now().isoformat()
            }
            df_all = pd.concat([df_all, pd.DataFrame([new])], ignore_index=True)
            df_all.to_csv(DATA_FILE, index=False)
            st.success("저장 완료 ✅")
            st.rerun()

    st.subheader("내가 입력한 데이터")
    my_data = df_all if role=="admin" else df_all[df_all["작성자_ID"]==user_id]
    st.dataframe(my_data)

# --------------------------
# 리포트 보기
# --------------------------
elif menu == "리포트 보기":
    st.header("📄 리포트 보기 및 PDF 생성")

    view_df = df_all if role=="admin" else df_all[df_all["작성자_ID"]==user_id]
    if view_df.empty:
        st.info("데이터가 없습니다.")
        st.stop()

    student = st.selectbox("학생 선택", sorted(view_df["학생명"].unique()))
    months = sorted(view_df[view_df["학생명"]==student]["월"].unique())
    month_sel = st.selectbox("월 선택", months)
    df_m = view_df[(view_df["학생명"]==student)&(view_df["월"]==month_sel)]
    st.dataframe(df_m)

    # 진도 그래프
    term = extract_term(df_m.iloc[0]["단원명"])
    curr = float(df_m["진도진행률"].astype(float).max())
    prev = get_prev_progress(df_all, student, term, month_sel)
    st.write(f"학기: {term} | 지난달 {prev}% → 이번달 {curr}%")
    img = make_progress_bar(term, prev, curr)
    st.image(img)

# --------------------------
# 데이터 관리 (원장 전용)
# --------------------------
elif menu == "데이터 관리" and role=="admin":
    st.header("📂 전체 데이터 관리 (원장 전용)")
    st.dataframe(df_all)
    if st.button("CSV 다운로드"):
        st.download_button("다운로드", df_all.to_csv(index=False).encode("utf-8"), file_name=DATA_FILE)
    if st.button("전체 삭제 (주의)"):
        os.remove(DATA_FILE)
        st.rerun()
