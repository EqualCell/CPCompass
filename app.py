import streamlit as st
from db import get_connection, read_sql
from cf_import import import_codeforces_user
from cf_api import CodeforcesError
from recommender import build_recommendations, get_cache_stats


# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="CPCompass",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --bg: #07090d;
        --panel: #0d1117;
        --panel-2: #111827;
        --border: rgba(255,255,255,0.08);
        --text: #f3f4f6;
        --muted: #94a3b8;
        --accent: #8b5cf6;
        --accent-2: #22d3ee;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--bg);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stToolbar"] {
        right: 1rem;
    }

    .block-container {
        max-width: 1240px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }

    .hero {
        padding: 1.6rem 0 1.2rem 0;
    }

    .hero-kicker {
        color: var(--accent-2);
        text-transform: uppercase;
        letter-spacing: 0.16em;
        font-size: 0.72rem;
        font-weight: 700;
        margin-bottom: 0.55rem;
    }

    .hero-title {
        font-size: clamp(2.4rem, 6vw, 4.8rem);
        line-height: 0.95;
        font-weight: 800;
        letter-spacing: -0.055em;
        margin: 0;
        background: linear-gradient(90deg, #ffffff 10%, #c4b5fd 55%, #67e8f9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-copy {
        color: var(--muted);
        max-width: 720px;
        margin-top: 0.9rem;
        font-size: 1.03rem;
        line-height: 1.65;
    }

    .section-label {
        color: #cbd5e1;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-weight: 700;
        margin-top: 1.7rem;
        margin-bottom: 0.25rem;
    }

    .section-title {
        font-size: 1.65rem;
        font-weight: 720;
        letter-spacing: -0.025em;
        margin: 0 0 0.85rem 0;
    }

    div[data-testid="stForm"] {
        background: linear-gradient(180deg, rgba(17,24,39,0.94), rgba(13,17,23,0.94));
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 0.35rem 0.45rem 0.55rem 0.45rem;
        box-shadow: 0 14px 45px rgba(0,0,0,0.28);
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(17,24,39,0.92), rgba(13,17,23,0.92));
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 0.85rem 1rem;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--muted);
    }

    div[data-testid="stMetricValue"] {
        color: #f8fafc;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 14px;
        overflow: hidden;
    }

    [data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(13,17,23,0.72);
    }

    button[kind="primary"] {
        border-radius: 10px !important;
        font-weight: 700 !important;
    }

    div[data-baseweb="tab-list"] {
        gap: 0.4rem;
        border-bottom: 1px solid var(--border);
    }

    button[data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    hr {
        border-color: var(--border) !important;
    }

    .active-profile {
        color: var(--muted);
        font-size: 0.92rem;
        margin-top: 0.15rem;
        margin-bottom: 0.65rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# HERO + PROFILE SEARCH
# --------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">Codeforces training intelligence</div>
        <h1 class="hero-title">CPCompass</h1>
        <div class="hero-copy">
            Turn your submission history into focused practice: weakness-aware picks,
            calibrated difficulty, and curated problem recommendations.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("profile_form", clear_on_submit=False):
    input_col, button_col = st.columns([4.6, 1.4], vertical_alignment="bottom")

    with input_col:
        handle_input = st.text_input(
            "Codeforces handle",
            placeholder="Enter a handle, e.g. tourist",
            label_visibility="collapsed",
        )

    with button_col:
        submitted = st.form_submit_button(
            "Analyze profile",
            type="primary",
            use_container_width=True,
        )

# A form submit is triggered by clicking the button or pressing Enter in the input.
imported_user_id = None

if submitted:
    handle = handle_input.strip()

    if not handle:
        st.error("Enter a Codeforces handle first.")
    else:
        with st.status("Syncing Codeforces profile...", expanded=False) as status:
            try:
                imported_user_id = import_codeforces_user(handle)
            except CodeforcesError as exc:
                status.update(label="Could not load profile", state="error")
                st.error(str(exc))
            else:
                st.session_state["active_user_id"] = int(imported_user_id)
                st.session_state["active_handle"] = handle
                status.update(label="Profile ready", state="complete")


# --------------------------------------------------
# LANDING STATE
# --------------------------------------------------

active_user_id = st.session_state.get("active_user_id")
active_handle = st.session_state.get("active_handle")

if active_user_id is None or active_handle is None:
    st.markdown("<div style='height: 1.2rem'></div>", unsafe_allow_html=True)
    st.info("Enter a Codeforces handle above. Press Enter or click Analyze profile to begin.")
    st.stop()


# --------------------------------------------------
# DATABASE + PROFILE VALIDATION
# --------------------------------------------------

conn = get_connection()

try:
    profile_df = read_sql(
        "SELECT id, handle FROM users WHERE id = %s",
        conn,
        params=(active_user_id,),
    )

    if profile_df.empty:
        st.session_state.pop("active_user_id", None)
        st.session_state.pop("active_handle", None)
        st.error("This profile is no longer available. Load it again.")
        st.stop()

    user_id = int(profile_df.iloc[0]["id"])
    selected_handle = str(profile_df.iloc[0]["handle"])
    st.session_state["active_handle"] = selected_handle

    st.markdown(
        '<div class="section-label">Profile overview</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-title">Your training snapshot</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Active profile: @{selected_handle}")


    # --------------------------------------------------
    # BASIC STATS
    # --------------------------------------------------

    stats = read_sql(
        """
        SELECT
            COUNT(DISTINCT problem_id) AS attempted,
            COUNT(
                DISTINCT CASE
                    WHEN verdict = 'OK' THEN problem_id
                END
            ) AS solved,
            COUNT(*) AS submissions
        FROM submissions
        WHERE user_id = %s;
        """,
        conn,
        params=(user_id,),
    )

    attempted = int(stats.iloc[0]["attempted"])
    solved = int(stats.iloc[0]["solved"])
    submissions = int(stats.iloc[0]["submissions"])
    solve_rate = (100.0 * solved / attempted) if attempted else 0.0


    # --------------------------------------------------
    # RECOMMENDATION ENGINE
    # --------------------------------------------------

    with st.spinner("Building your training plan..."):
        (
            user_rating,
            weakness_df,
            smart_df,
            quick_df,
            deep_df,
        ) = build_recommendations(
            conn,
            user_id,
            selected_handle,
            force_refresh=(imported_user_id == user_id),
        )

    rating_note = weakness_df.attrs.get("rating_note")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("CF Rating", user_rating)
    m2.metric("Solved", solved)
    m3.metric("Attempted", attempted)
    m4.metric("Solve Rate", f"{solve_rate:.1f}%")
    m5.metric("Submissions", submissions)

    if rating_note:
        st.warning(rating_note)


    # --------------------------------------------------
    # TOPIC ANALYTICS
    # --------------------------------------------------

    st.markdown(
        '<div class="section-label">Analytics</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-title">Where your practice is leaking points</div>',
        unsafe_allow_html=True,
    )

    topic_df = read_sql(
        """
        SELECT
            topic,
            attempted,
            solved,
            success_rate,
            wrong_submissions
        FROM topic_stats
        WHERE user_id = %s
          AND attempted >= 5
        ORDER BY success_rate ASC;
        """,
        conn,
        params=(user_id,),
    )

    left_analytics, right_analytics = st.columns([1.12, 0.88])

    with left_analytics:
        if not weakness_df.empty:
            weakness_display = weakness_df[
                [
                    "topic",
                    "attempted",
                    "solved",
                    "smoothed_success",
                    "weakness_score",
                ]
            ].copy()

            weakness_display["smoothed_success"] = (
                weakness_display["smoothed_success"] * 100
            ).round(1)
            weakness_display["weakness_score"] = weakness_display[
                "weakness_score"
            ].round(1)

            weakness_display = weakness_display.head(8).rename(
                columns={
                    "topic": "Topic",
                    "attempted": "Tried",
                    "solved": "Solved",
                    "smoothed_success": "Smoothed Success %",
                    "weakness_score": "Weakness",
                }
            )

            st.dataframe(
                weakness_display,
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Not enough data for weakness analysis yet.")

    with right_analytics:
        if not topic_df.empty:
            chart_df = (
                topic_df[["topic", "success_rate"]]
                .sort_values("success_rate", ascending=True)
                .set_index("topic")
            )
            st.bar_chart(chart_df)
        else:
            st.info("Solve at least five problems in a topic to unlock topic analytics.")


    # --------------------------------------------------
    # TABLE HELPERS
    # --------------------------------------------------

    def prepare_problem_table(df):
        if df.empty:
            return df

        result = df.copy()

        result["Tags"] = result["tags"].apply(
            lambda tags: ", ".join(tags)
        )

        result["Predicted Solve %"] = (
            result["predicted_solve"] * 100
        ).round(1)

        result["Problem Link"] = result.apply(
            lambda row: (
                "https://codeforces.com/problemset/problem/"
                f"{row['external_id'].split('-')[0]}/"
                f"{row['external_id'].split('-', 1)[1]}"
            ),
            axis=1,
        )

        return result


    def show_mode_table(df, empty_message):
        if df.empty:
            st.info(empty_message)
            return

        table = prepare_problem_table(df)
        display = table[
            [
                "title",
                "official_rating",
                "effective_rating",
                "solved_count",
                "Problem Link",
            ]
        ].copy()

        display = display.rename(
            columns={
                "title": "Problem",
                "official_rating": "Official",
                "effective_rating": "Adjusted",
                "solved_count": "Solvers",
            }
        )

        st.dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Problem Link": st.column_config.LinkColumn(
                    "Open",
                    display_text="Solve ↗",
                )
            },
        )


    # --------------------------------------------------
    # RECOMMENDATIONS
    # --------------------------------------------------

    st.markdown(
        '<div class="section-label">Training plan</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-title">What you should solve next</div>',
        unsafe_allow_html=True,
    )

    smart_tab, quick_tab, deep_tab = st.tabs(
        ["🎯 Smart Picks", "⚡ QuickSolve", "🧠 DeepThink"]
    )

    with smart_tab:
        st.caption(
            "Weakness-aware recommendations combining topic fit, era-adjusted "
            "difficulty, challenge fit, and curated quality."
        )

        if smart_df.empty:
            st.info("No Smart Picks available yet. Build a little more topic history first.")
        else:
            smart = prepare_problem_table(smart_df)

            smart_display = smart[
                [
                    "title",
                    "official_rating",
                    "effective_rating",
                    "Predicted Solve %",
                    "Tags",
                    "recommendation_score",
                    "Problem Link",
                ]
            ].copy()

            smart_display["recommendation_score"] = smart_display[
                "recommendation_score"
            ].round(1)

            smart_display = smart_display.rename(
                columns={
                    "title": "Problem",
                    "official_rating": "Official",
                    "effective_rating": "Adjusted",
                    "recommendation_score": "Score",
                }
            )

            st.dataframe(
                smart_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Problem Link": st.column_config.LinkColumn(
                        "Open",
                        display_text="Solve ↗",
                    )
                },
            )

    with quick_tab:
        st.caption(
            f"Fast, high-quality reps around {user_rating - 300} rating, "
            "with C2Ladders frequency used as a curated quality signal."
        )
        show_mode_table(
            quick_df,
            "No QuickSolve problems found in the current target window.",
        )

    with deep_tab:
        st.caption(
            f"Stretch problems around {user_rating + 300} rating for deliberate, "
            "longer-form practice."
        )
        show_mode_table(
            deep_df,
            "No DeepThink problems found in the current target window.",
        )


    # --------------------------------------------------
    # SYSTEM INFO
    # --------------------------------------------------

    with st.expander("System & recommendation engine"):
        cache_stats = get_cache_stats()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cache Hits", cache_stats["hits"])
        c2.metric("Cache Misses", cache_stats["misses"])
        c3.metric("Hit Rate", f'{cache_stats["hit_rate"]}%')
        c4.metric(
            "LRU Entries",
            f'{cache_stats["size"]}/{cache_stats["capacity"]}',
        )

        st.caption(
            "Recommendations are cached in the running app process. "
            "A profile refresh bypasses the cached result."
        )


finally:
    conn.close()
