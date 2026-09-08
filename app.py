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
# THEME
# --------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --bg: #07090d;
        --panel: #0d1117;
        --panel-soft: #111827;
        --border: rgba(255,255,255,0.085);
        --border-strong: rgba(139,92,246,0.28);
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #8b5cf6;
        --accent2: #22d3ee;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at 80% -10%, rgba(139,92,246,0.14), transparent 34rem),
            radial-gradient(circle at 15% 5%, rgba(34,211,238,0.08), transparent 27rem),
            var(--bg);
        color: var(--text);
    }

    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"] { right: 1rem; }

    .block-container {
        max-width: 1240px;
        padding-top: 1.8rem;
        padding-bottom: 4rem;
    }

    .topline {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1.1rem;
    }

    .brand-mini {
        color: #dbeafe;
        font-weight: 700;
        letter-spacing: -0.015em;
    }

    .creator-chip {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        padding: .45rem .72rem;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: rgba(13,17,23,.72);
        color: var(--muted) !important;
        text-decoration: none !important;
        font-size: .82rem;
        transition: .18s ease;
    }

    .creator-chip:hover {
        border-color: rgba(34,211,238,.38);
        color: #e2e8f0 !important;
        transform: translateY(-1px);
    }

    .hero {
        padding: 1.25rem 0 1.45rem 0;
    }

    .hero-kicker {
        color: var(--accent2);
        text-transform: uppercase;
        letter-spacing: .17em;
        font-size: .7rem;
        font-weight: 800;
        margin-bottom: .58rem;
    }

    .hero-title {
        font-size: clamp(2.7rem, 6vw, 5.2rem);
        line-height: .94;
        font-weight: 850;
        letter-spacing: -.06em;
        margin: 0;
        background: linear-gradient(90deg, #fff 8%, #ddd6fe 55%, #67e8f9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-copy {
        color: var(--muted);
        max-width: 760px;
        margin-top: 1rem;
        font-size: 1.03rem;
        line-height: 1.68;
    }

    .micro-row {
        display: flex;
        flex-wrap: wrap;
        gap: .55rem;
        margin-top: 1rem;
    }

    .micro-pill {
        border: 1px solid var(--border);
        background: rgba(13,17,23,.58);
        color: #a8b3c4;
        border-radius: 999px;
        padding: .38rem .65rem;
        font-size: .76rem;
    }

    .section-label {
        color: #a5b4fc;
        font-size: .74rem;
        text-transform: uppercase;
        letter-spacing: .15em;
        font-weight: 800;
        margin-top: 2rem;
        margin-bottom: .28rem;
    }

    .section-title {
        font-size: 1.68rem;
        font-weight: 760;
        letter-spacing: -.03em;
        margin: 0 0 .85rem 0;
    }

    .profile-strip {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin: .15rem 0 .75rem 0;
        color: var(--muted);
        font-size: .9rem;
    }

    .profile-link {
        color: #c4b5fd !important;
        font-weight: 700;
        text-decoration: none !important;
    }

    .profile-link:hover { color: #67e8f9 !important; }

    div[data-testid="stForm"] {
        background: linear-gradient(180deg, rgba(17,24,39,.91), rgba(13,17,23,.91));
        border: 1px solid var(--border-strong);
        border-radius: 18px;
        padding: .35rem .45rem .55rem .45rem;
        box-shadow: 0 18px 60px rgba(0,0,0,.27);
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(17,24,39,.90), rgba(13,17,23,.88));
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: .9rem 1rem;
        transition: .18s ease;
    }

    div[data-testid="stMetric"]:hover {
        border-color: rgba(139,92,246,.32);
        transform: translateY(-1px);
    }

    div[data-testid="stMetricLabel"] { color: var(--muted); }
    div[data-testid="stMetricValue"] { color: #f8fafc; }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 14px;
        overflow: hidden;
    }

    [data-testid="stExpander"] {
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(13,17,23,.68);
    }

    button[kind="primary"] {
        border-radius: 10px !important;
        font-weight: 750 !important;
        box-shadow: 0 8px 26px rgba(139,92,246,.18);
    }

    div[data-baseweb="tab-list"] {
        gap: .45rem;
        border-bottom: 1px solid var(--border);
    }

    button[data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    hr { border-color: var(--border) !important; }

    .footer {
        margin-top: 3rem;
        padding-top: 1.25rem;
        border-top: 1px solid var(--border);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        color: #64748b;
        font-size: .82rem;
    }

    .footer a {
        color: #a78bfa !important;
        text-decoration: none !important;
        font-weight: 700;
    }

    .footer a:hover { color: #67e8f9 !important; }

    @media (max-width: 700px) {
        .topline, .footer, .profile-strip { align-items: flex-start; flex-direction: column; }
        .block-container { padding-top: 1rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# HERO
# --------------------------------------------------

st.markdown(
    """
    <div class="topline">
        <div class="brand-mini">🧭 CPCompass</div>
        <a class="creator-chip" href="https://codeforces.com/profile/EqualCell" target="_blank">
            Created by <strong>EqualCell ↗</strong>
        </a>
    </div>

    <div class="hero">
        <div class="hero-kicker">Codeforces training intelligence</div>
        <h1 class="hero-title">Practice with direction.</h1>
        <div class="hero-copy">
            CPCompass turns your Codeforces history into a focused training plan using
            weakness analysis, era-aware difficulty and curated problem quality signals.
        </div>
        <div class="micro-row">
            <span class="micro-pill">Bayesian weakness scoring</span>
            <span class="micro-pill">Era-adjusted ratings</span>
            <span class="micro-pill">C2Ladders quality signal</span>
            <span class="micro-pill">LRU-cached recommendations</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# PROFILE SEARCH
# --------------------------------------------------

with st.form("profile_form", clear_on_submit=False):
    input_col, button_col = st.columns([4.7, 1.3], vertical_alignment="bottom")

    with input_col:
        handle_input = st.text_input(
            "Codeforces handle",
            placeholder="Enter a Codeforces handle",
            label_visibility="collapsed",
        )

    with button_col:
        submitted = st.form_submit_button(
            "Analyze profile",
            type="primary",
            use_container_width=True,
        )

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
    st.markdown("<div style='height: .8rem'></div>", unsafe_allow_html=True)
    st.info("Enter a handle and press Enter — or click Analyze profile — to build a training plan.")

    st.markdown(
        """
        <div class="footer">
            <span>CPCompass · Competitive programming analytics</span>
            <span>Built by <a href="https://codeforces.com/profile/EqualCell" target="_blank">EqualCell ↗</a></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# --------------------------------------------------
# DATABASE + PROFILE
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

    st.markdown('<div class="section-label">Profile overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Your training snapshot</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="profile-strip">
            <span>Active profile · <a class="profile-link" href="https://codeforces.com/profile/{selected_handle}" target="_blank">@{selected_handle} ↗</a></span>
            <span>Recommendations exclude problems already solved with AC.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


    # --------------------------------------------------
    # STATS
    # --------------------------------------------------

    stats = read_sql(
        """
        SELECT
            COUNT(DISTINCT problem_id) AS attempted,
            COUNT(DISTINCT CASE WHEN verdict = 'OK' THEN problem_id END) AS solved,
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
    # RECOMMENDATIONS
    # --------------------------------------------------

    with st.spinner("Building your training plan..."):
        user_rating, weakness_df, smart_df, quick_df, deep_df = build_recommendations(
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
    # ANALYTICS
    # --------------------------------------------------

    st.markdown('<div class="section-label">Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Where your practice is leaking points</div>', unsafe_allow_html=True)

    topic_df = read_sql(
        """
        SELECT topic, attempted, solved, success_rate, wrong_submissions
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
                ["topic", "attempted", "solved", "smoothed_success", "weakness_score"]
            ].copy()

            weakness_display["smoothed_success"] = (
                weakness_display["smoothed_success"] * 100
            ).round(1)
            weakness_display["weakness_score"] = weakness_display["weakness_score"].round(1)

            weakness_display = weakness_display.head(8).rename(
                columns={
                    "topic": "Topic",
                    "attempted": "Tried",
                    "solved": "Solved",
                    "smoothed_success": "Smoothed Success %",
                    "weakness_score": "Weakness",
                }
            )

            st.dataframe(weakness_display, width="stretch", hide_index=True)
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
    # HELPERS
    # --------------------------------------------------

    def prepare_problem_table(df):
        if df.empty:
            return df

        result = df.copy()
        result["Tags"] = result["tags"].apply(lambda tags: ", ".join(tags))
        result["Predicted Solve %"] = (result["predicted_solve"] * 100).round(1)
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
            ["title", "official_rating", "effective_rating", "solved_count", "Problem Link"]
        ].copy()

        display = display.rename(
            columns={
                "title": "Problem",
                "official_rating": "Official",
                "effective_rating": "Era-adjusted",
                "solved_count": "Solvers",
            }
        )

        st.dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Official": st.column_config.NumberColumn(
                    "Official",
                    help="The original Codeforces difficulty rating.",
                    format="%d",
                ),
                "Era-adjusted": st.column_config.NumberColumn(
                    "Era-adjusted",
                    help="A modern-equivalent training estimate based on how the same contest slot is rated across eras.",
                    format="%d",
                ),
                "Problem Link": st.column_config.LinkColumn("Open", display_text="Solve ↗"),
            },
        )


    # --------------------------------------------------
    # TRAINING PLAN
    # --------------------------------------------------

    st.markdown('<div class="section-label">Training plan</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">What you should solve next</div>', unsafe_allow_html=True)

    with st.expander("What does Era-adjusted rating mean?"):
        st.markdown(
            """
            **Official rating** is the Codeforces number attached to the problem. **Era-adjusted rating** is CPCompass's
            training estimate for how that problem compares with problems in the same contest slot today.

            CPCompass groups problems by contest type and index (for example, Div. 2 C), compares the median rating in
            that era with the median for recent contests, then applies a confidence-shrunk correction.

            So the adjusted value can go **either up or down**. If an older era's Div. 2 C problems were typically rated
            lower than recent Div. 2 C problems, an old 1600 may be treated as roughly 1650/1700 in modern training terms.
            The correction is capped and shrunk when the sample is small — it is a heuristic, not an official Codeforces rating.
            """
        )

    smart_tab, quick_tab, deep_tab = st.tabs(["🎯 Smart Picks", "⚡ QuickSolve", "🧠 DeepThink"])

    with smart_tab:
        st.caption(
            "Weakness-aware recommendations combining topic fit, era-adjusted difficulty, challenge fit and curated quality."
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

            smart_display["recommendation_score"] = smart_display["recommendation_score"].round(1)
            smart_display = smart_display.rename(
                columns={
                    "title": "Problem",
                    "official_rating": "Official",
                    "effective_rating": "Era-adjusted",
                    "recommendation_score": "Score",
                }
            )

            st.dataframe(
                smart_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Official": st.column_config.NumberColumn(
                        "Official",
                        help="The original Codeforces difficulty rating.",
                        format="%d",
                    ),
                    "Era-adjusted": st.column_config.NumberColumn(
                        "Era-adjusted",
                        help="CPCompass's modern-equivalent training estimate. It can be above or below the official rating.",
                        format="%d",
                    ),
                    "Problem Link": st.column_config.LinkColumn("Open", display_text="Solve ↗"),
                },
            )

    with quick_tab:
        st.caption(
            f"Fast, high-quality reps around {user_rating - 300} rating, with C2Ladders frequency used as a curated quality signal."
        )
        show_mode_table(quick_df, "No QuickSolve problems found in the current target window.")

    with deep_tab:
        st.caption(
            f"Stretch problems around {user_rating + 300} rating for deliberate, longer-form practice."
        )
        show_mode_table(deep_df, "No DeepThink problems found in the current target window.")


    # --------------------------------------------------
    # SYSTEM INFO
    # --------------------------------------------------

    with st.expander("System & recommendation engine"):
        cache_stats = get_cache_stats()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cache Hits", cache_stats["hits"])
        c2.metric("Cache Misses", cache_stats["misses"])
        c3.metric("Hit Rate", f'{cache_stats["hit_rate"]}%')
        c4.metric("LRU Entries", f'{cache_stats["size"]}/{cache_stats["capacity"]}')
        st.caption(
            "Recommendations are cached in the running app process. A profile refresh bypasses the cached result."
        )


    # --------------------------------------------------
    # FOOTER
    # --------------------------------------------------

    st.markdown(
        """
        <div class="footer">
            <span>CPCompass · Competitive programming analytics & training</span>
            <span>Created by <a href="https://codeforces.com/profile/EqualCell" target="_blank">EqualCell ↗</a></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

finally:
    conn.close()
