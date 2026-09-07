import streamlit as st
from db import get_connection, read_sql
from cf_import import import_codeforces_user
from cf_api import CodeforcesError
from recommender import build_recommendations, get_cache_stats


# --------------------------------------------------
# PAGE
# --------------------------------------------------

st.set_page_config(
    page_title="CPCompass",
    page_icon="🧭",
    layout="wide"
)

st.title("🧭 CPCompass")
st.caption(
    "Competitive Programming Analytics & Training Assistant"
)

handle_input = st.text_input("Codeforces Handle", key="handle_input")
imported_user_id = None
if st.button("Load / Refresh Profile", type="primary"):
    if not handle_input.strip():
        st.error("Please enter a Codeforces handle.")
    else:
        with st.status("Loading profile...", expanded=True) as status:
            try:
                imported_user_id = import_codeforces_user(
                    handle_input, on_status=st.write
                )
            except CodeforcesError as exc:
                status.update(label="Profile could not be loaded", state="error")
                st.error(str(exc))
            else:
                status.update(label="Profile ready", state="complete")

# Open after the importer commits so the selector sees the new profile.
conn = get_connection()
try:
    users_df = read_sql(
        "SELECT id, handle FROM users ORDER BY handle", conn
    )
    if users_df.empty:
        st.info("Enter a Codeforces handle above to load your first profile.")
        st.stop()

    handles = users_df["handle"].tolist()
    if imported_user_id is not None:
        st.session_state["selected_profile"] = users_df.loc[
            users_df["id"] == imported_user_id, "handle"
        ].iloc[0]
    if st.session_state.get("selected_profile") not in handles:
        st.session_state["selected_profile"] = handles[0]
    selected_handle = st.selectbox(
        "Previously Loaded Profiles", handles, key="selected_profile"
    )
    user_id = int(users_df.loc[users_df["handle"] == selected_handle, "id"].iloc[0])


    # --------------------------------------------------
    # BASIC STATS
    # --------------------------------------------------

    stats = read_sql(
        """
        SELECT

            COUNT(
                DISTINCT problem_id
            ) AS attempted,

            COUNT(
                DISTINCT CASE
                    WHEN verdict = 'OK'
                    THEN problem_id
                END
            ) AS solved,

            COUNT(*) AS submissions

        FROM submissions

        WHERE user_id = %s;
        """,
        conn,
        params=(user_id,)
    )


    attempted = int(stats.iloc[0]["attempted"])
    solved = int(stats.iloc[0]["solved"])
    submissions = int(stats.iloc[0]["submissions"])


    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Problems Attempted",
        attempted
    )

    c2.metric(
        "Problems Solved",
        solved
    )

    c3.metric(
        "Total Submissions",
        submissions
    )


    st.divider()


    # --------------------------------------------------
    # TOPIC PERFORMANCE
    # --------------------------------------------------

    st.header("📊 Topic Performance")


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
        params=(user_id,)
    )


    if not topic_df.empty:

        st.dataframe(
            topic_df,
            width="stretch",
            hide_index=True
        )

        st.subheader(
            "Success Rate by Topic"
        )

        st.bar_chart(
            topic_df.set_index("topic")[
                "success_rate"
            ]
        )

    else:
        st.info(
            "Not enough topic data yet."
        )


    st.divider()


    # --------------------------------------------------
    # SMART RECOMMENDATION ENGINE
    # --------------------------------------------------

    st.header("🎯 Training Recommendations")

    with st.spinner(
        "Analyzing your Codeforces history..."
    ):

        (
            user_rating,
            weakness_df,
            smart_df,
            quick_df,
            deep_df

        ) = build_recommendations(
            conn,
            user_id,
            selected_handle,
            force_refresh=(imported_user_id == user_id)
        )


    rating_note = weakness_df.attrs.get("rating_note")
    st.metric(
        "Training Rating (fallback)" if rating_note else "Current Codeforces Rating",
        user_rating
    )
    if rating_note:
        st.warning(rating_note)


    # --------------------------------------------------
    # WEAKNESS ANALYSIS
    # --------------------------------------------------

    st.subheader("Weakness Analysis")


    if not weakness_df.empty:

        weakness_display = weakness_df[
            [
                "topic",
                "attempted",
                "solved",
                "smoothed_success",
                "weakness_score"
            ]
        ].copy()


        weakness_display[
            "smoothed_success"
        ] = (
            weakness_display[
                "smoothed_success"
            ]
            * 100
        ).round(2)


        weakness_display[
            "weakness_score"
        ] = (
            weakness_display[
                "weakness_score"
            ].round(2)
        )


        weakness_display = (
            weakness_display.head(10)
        )


        weakness_display = (
            weakness_display.rename(
                columns={
                    "topic": "Topic",
                    "attempted": "Attempted",
                    "solved": "Solved",
                    "smoothed_success":
                        "Smoothed Success %",
                    "weakness_score":
                        "Weakness Score"
                }
            )
        )


        st.dataframe(
            weakness_display,
            width="stretch",
            hide_index=True
        )


    st.divider()


    # --------------------------------------------------
    # HELPER
    # --------------------------------------------------

    def prepare_problem_table(df):

        if df.empty:
            return df

        result = df.copy()


        result["Tags"] = result[
            "tags"
        ].apply(
            lambda tags:
            ", ".join(tags)
        )


        result[
            "Predicted Solve %"
        ] = (
            result[
                "predicted_solve"
            ]
            * 100
        ).round(1)


        result["Problem"] = result.apply(
            lambda row:
            (
                "https://codeforces.com/problemset/"
                f"problem/"
                f"{row['external_id'].split('-')[0]}/"
                f"{row['external_id'].split('-', 1)[1]}"
            ),
            axis=1
        )


        return result


    # --------------------------------------------------
    # SMART PICKS
    # --------------------------------------------------

    st.subheader("🎯 Smart Picks")

    st.caption(
        "Problems selected using topic weakness, "
        "era-adjusted difficulty and challenge fit."
    )


    if smart_df.empty:

        st.info(
            "No smart recommendations available."
        )

    else:

        smart = prepare_problem_table(
            smart_df
        )


        smart_display = smart[
            [
                "title",
                "official_rating",
                "effective_rating",
                "Predicted Solve %",
                "Tags",
                "recommendation_score",
                "Problem"
            ]
        ].copy()


        smart_display[
            "recommendation_score"
        ] = (
            smart_display[
                "recommendation_score"
            ].round(1)
        )


        smart_display = smart_display.rename(
            columns={
                "title": "Problem Name",

                "official_rating":
                    "Official Rating",

                "effective_rating":
                    "Era-Adjusted Rating",

                "recommendation_score":
                    "Recommendation Score"
            }
        )


        st.dataframe(
            smart_display,
            width="stretch",
            hide_index=True,

            column_config={

                "Problem":
                    st.column_config.LinkColumn(
                        "Open Problem",
                        display_text="Open"
                    )
            }
        )


    st.divider()


    # --------------------------------------------------
    # QUICK + DEEP
    # --------------------------------------------------

    st.caption(
        "QuickSolve and DeepThink use popularity as a quality signal; "
        "curated classic entries take priority when available."
    )
    left, right = st.columns(2)


    # -------------------------
    # QUICK SOLVE
    # -------------------------

    with left:

        st.subheader("⚡ QuickSolve")

        st.caption(
            f"Practice problems around "
            f"{user_rating - 300} rating."
        )


        if quick_df.empty:

            st.info(
                "No QuickSolve problems found."
            )

        else:

            quick = prepare_problem_table(
                quick_df
            )


            quick_display = quick[
                [
                    "title",
                    "official_rating",
                    "effective_rating",
                    "solved_count",
                    "Problem"
                ]
            ].copy()


            quick_display = (
                quick_display.rename(
                    columns={

                        "title":
                            "Problem",

                        "official_rating":
                            "Official",

                        "effective_rating":
                            "Adjusted",

                        "solved_count":
                            "Solvers",

                        "Problem":
                            "Link"
                    }
                )
            )


            st.dataframe(
                quick_display,
                width="stretch",
                hide_index=True,

                column_config={

                    "Link":
                        st.column_config.LinkColumn(
                            "Link",
                            display_text="Open"
                        )
                }
            )


    # -------------------------
    # DEEP THINK
    # -------------------------

    with right:

        st.subheader("🧠 DeepThink")

        st.caption(
            f"Stretch problems around "
            f"{user_rating + 300} rating."
        )


        if deep_df.empty:

            st.info(
                "No DeepThink problems found."
            )

        else:

            deep = prepare_problem_table(
                deep_df
            )


            deep_display = deep[
                [
                    "title",
                    "official_rating",
                    "effective_rating",
                    "solved_count",
                    "Problem"
                ]
            ].copy()


            deep_display = (
                deep_display.rename(
                    columns={

                        "title":
                            "Problem",

                        "official_rating":
                            "Official",

                        "effective_rating":
                            "Adjusted",

                        "solved_count":
                            "Solvers",

                        "Problem":
                            "Link"
                    }
                )
            )


            st.dataframe(
                deep_display,
                width="stretch",
                hide_index=True,

                column_config={

                    "Link":
                        st.column_config.LinkColumn(
                            "Link",
                            display_text="Open"
                        )
                }
            )


    st.divider()

    st.subheader("⚙️ Recommendation Engine")

    cache_stats = get_cache_stats()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Cache Hits",
        cache_stats["hits"]
    )

    c2.metric(
        "Cache Misses",
        cache_stats["misses"]
    )

    c3.metric(
        "Hit Rate",
        f'{cache_stats["hit_rate"]}%'
    )

    c4.metric(
        "LRU Entries",
        f'{cache_stats["size"]}/{cache_stats["capacity"]}'
    )


finally:
    conn.close()
