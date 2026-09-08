import math
import logging
from cf_api import api_get, CodeforcesError
import pandas as pd
from db import read_sql
from lru_cache import LRUCache

PRIOR_STRENGTH = 8

recommendation_cache = LRUCache(capacity=10)

# ------------------------------------------------
# Current Codeforces rating
# ------------------------------------------------


def get_user_data_version(
    conn,
    user_id
):

    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(MAX(id), 0),
                COALESCE(
                    MAX(submitted_at),
                    '1970-01-01'
                )

            FROM submissions

            WHERE user_id = %s
            """,
            (user_id,)
        )

        submission_count, max_id, latest = (
            cursor.fetchone()
        )


        cursor.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(MAX(id), 0)

            FROM problems
            """
        )

        problem_count, max_problem_id = (
            cursor.fetchone()
        )


        cursor.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(frequency), 0)
            FROM classic_problems
            """
        )

        classic_count, classic_frequency_version = cursor.fetchone()

        cursor.execute(
            "SELECT COALESCE(SUM(CRC32(CONCAT(id, ':', COALESCE(verdict, '')))), 0) "
            "FROM submissions WHERE user_id = %s", (user_id,)
        )
        verdict_version = int(cursor.fetchone()[0])


    finally:
        cursor.close()


    return (
        submission_count,
        max_id,
        str(latest),
        problem_count,
        max_problem_id,
        classic_count,
        int(classic_frequency_version),
        verdict_version
    )




def get_cf_rating(handle):
    """Return (training rating, optional fallback explanation)."""
    try:
        rating = api_get("user.info", handles=handle)[0].get("rating")
        if rating is not None:
            return rating, None
        return 1200, "This profile is unrated. Recommendations use a fallback training rating of 1200."
    except CodeforcesError as exc:
        logging.getLogger(__name__).warning("Could not fetch Codeforces rating: %s", exc)
        return 1200, "Codeforces rating could not be retrieved. Recommendations use a fallback training rating of 1200. Try refreshing later."


# ------------------------------------------------
# Era
# ------------------------------------------------

def get_era(year):

    if pd.isna(year):
        return None

    year = int(year)

    if year <= 2019:
        return "old"

    if year <= 2021:
        return "2020-21"

    if year <= 2023:
        return "2022-23"

    return "recent"


# ------------------------------------------------
# Build era adjustment map
# ------------------------------------------------

def build_era_adjustments(conn):

    df = read_sql(
        """
        SELECT
            difficulty,
            problem_index,
            contest_group,
            YEAR(contest_start) AS contest_year

        FROM problems

        WHERE platform = 'Codeforces'
        AND difficulty IS NOT NULL
        AND contest_start IS NOT NULL
        AND problem_index IS NOT NULL;
        """,
        conn
    )

    if df.empty:
        return {}

    df["era"] = df["contest_year"].apply(
        get_era
    )


    # Recent problems = our baseline
    recent = (
        df[df["contest_year"] >= 2024]
        .groupby(
            [
                "contest_group",
                "problem_index"
            ]
        )["difficulty"]
        .median()
        .reset_index()
        .rename(
            columns={
                "difficulty":
                "recent_median"
            }
        )
    )


    era_stats = (
        df.groupby(
            [
                "era",
                "contest_group",
                "problem_index"
            ]
        )["difficulty"]
        .agg(
            era_median="median",
            sample_size="count"
        )
        .reset_index()
    )


    stats = era_stats.merge(
        recent,
        on=[
            "contest_group",
            "problem_index"
        ],
        how="left"
    )


    adjustment_map = {}


    for _, row in stats.iterrows():

        if pd.isna(row["recent_median"]):
            continue

        raw_difference = (
            row["era_median"]
            -
            row["recent_median"]
        )


        # Never allow a crazy correction
        raw_difference = max(
            -300,
            min(
                300,
                raw_difference
            )
        )


        # Shrink unreliable samples
        confidence = (
            row["sample_size"]
            /
            (
                row["sample_size"]
                + 30
            )
        )


        adjustment = (
            raw_difference
            *
            confidence
        )


        key = (
            row["era"],
            row["contest_group"],
            row["problem_index"]
        )

        adjustment_map[key] = adjustment


    return adjustment_map


# ------------------------------------------------
# Bayesian topic weakness
# ------------------------------------------------

def get_topic_weakness(conn, user_id):

    overall = read_sql(
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
            ) AS solved

        FROM submissions

        WHERE user_id = %s;
        """,
        conn,
        params=(user_id,)
    )


    attempted = int(
        overall.iloc[0]["attempted"]
    )

    solved = int(
        overall.iloc[0]["solved"]
    )


    if attempted == 0:
        overall_rate = 0.5
    else:
        overall_rate = (
            solved / attempted
        )


    topics = read_sql(
        """
        SELECT
            topic_id,
            topic,
            attempted,
            solved,
            wrong_submissions

        FROM topic_stats

        WHERE user_id = %s;
        """,
        conn,
        params=(user_id,)
    )


    if topics.empty:
        topics["smoothed_success"] = pd.Series(dtype=float)
        topics["weakness_score"] = pd.Series(dtype=float)
        return {}, topics


    topics["smoothed_success"] = (

        topics["solved"]
        +
        overall_rate
        *
        PRIOR_STRENGTH

    ) / (

        topics["attempted"]
        +
        PRIOR_STRENGTH

    )


    topics["weakness_score"] = (

        100
        *
        (
            1
            -
            topics["smoothed_success"]
        )

    )


    topics = topics.sort_values(
        "weakness_score",
        ascending=False
    )


    weakness = dict(
        zip(
            topics["topic"],
            topics["weakness_score"]
        )
    )


    return weakness, topics


# ------------------------------------------------
# Candidate problems
# ------------------------------------------------

def get_candidates(
    conn,
    user_id,
    adjustment_map
):

    df = read_sql(
        """
        SELECT

            p.id,
            p.external_id,
            p.title,

            p.difficulty
                AS official_rating,

            p.problem_index,
            p.contest_group,

            YEAR(p.contest_start)
                AS contest_year,

            p.solved_count,

            GROUP_CONCAT(
                DISTINCT t.name
                SEPARATOR '|||'
            ) AS tags,

            MAX(
                CASE
                    WHEN cp.problem_id
                         IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS is_classic,

            COALESCE(
                MAX(
                    CASE
                        WHEN cp.source = 'C2Ladders'
                        THEN cp.frequency
                        ELSE 0
                    END
                ),
                0
            ) AS c2_frequency

        FROM problems p

        JOIN problem_topics pt
            ON p.id = pt.problem_id

        JOIN topics t
            ON t.id = pt.topic_id

        LEFT JOIN classic_problems cp
            ON cp.problem_id = p.id

        WHERE
            p.platform = 'Codeforces'

        AND
            p.difficulty IS NOT NULL

        AND NOT EXISTS (

            SELECT 1

            FROM submissions s

            WHERE
                s.user_id = %s

            AND
                s.problem_id = p.id

            AND
                s.verdict = 'OK'
        )

        GROUP BY
            p.id,
            p.external_id,
            p.title,
            p.difficulty,
            p.problem_index,
            p.contest_group,
            p.contest_start,
            p.solved_count;
        """,
        conn,
        params=(user_id,)
    )


    if df.empty:
        for column in ("effective_rating", "popularity_score", "c2_score",
                       "classic_score", "weakness_match", "predicted_solve",
                       "difficulty_fit", "recommendation_score", "mode_score"):
            df[column] = pd.Series(dtype=float)
        return df


    df["tags"] = (
        df["tags"]
        .fillna("")
        .apply(
            lambda x:
            x.split("|||")
        )
    )


    # ------------------------------------------------
    # Era-adjusted rating
    # ------------------------------------------------

    def effective_rating(row):

        era = get_era(
            row["contest_year"]
        )

        key = (
            era,
            row["contest_group"],
            row["problem_index"]
        )

        adjustment = (
            adjustment_map.get(
                key,
                0
            )
        )

        value = (
            row["official_rating"]
            -
            adjustment
        )

        # nice readable number
        return int(
            round(value / 50)
            * 50
        )


    df["effective_rating"] = (
        df.apply(
            effective_rating,
            axis=1
        )
    )


    # ------------------------------------------------
    # Popularity score
    # ------------------------------------------------

    maximum = max(
        1,
        df["solved_count"].max()
    )


    df["popularity_score"] = (

        df["solved_count"]
        .apply(math.log1p)

        /

        math.log1p(maximum)

        *

        100
    )


    # ------------------------------------------------
    # Curated / classic score
    # ------------------------------------------------
    # C2Ladders frequency is log-normalized so that a few
    # very large frequencies do not dominate the ranking.
    max_c2_frequency = max(
        1,
        df["c2_frequency"].max()
    )

    df["c2_score"] = (
        df["c2_frequency"]
        .apply(math.log1p)
        /
        math.log1p(max_c2_frequency)
        *
        100
    )

    # Prefer the C2 signal when available.
    # Otherwise fall back to Codeforces popularity.
    df["classic_score"] = df.apply(
        lambda row:
            row["c2_score"]
            if row["c2_frequency"] > 0
            else 0.70 * row["popularity_score"],
        axis=1
    )


    return df


# ------------------------------------------------
# Main recommendation system
# ------------------------------------------------

def build_recommendations(
    conn,
    user_id,
    handle,
    force_refresh=False
):

    user_rating, rating_note = get_cf_rating(
        handle
    )


    # ------------------------------------------
    # Build cache key
    # ------------------------------------------

    data_version = get_user_data_version(
        conn,
        user_id
    )


    cache_key = (
        user_id,
        user_rating,
        data_version,
        rating_note
    )


    # ------------------------------------------
    # Try cache
    # ------------------------------------------

    cached_result = (
        None if force_refresh else recommendation_cache.get(cache_key)
    )


    if cached_result is not None:

        print(
            "Recommendation cache HIT"
        )

        return cached_result


    print(
        "Recommendation cache MISS"
    )


    # ------------------------------------------
    # Normal recommendation calculation
    # ------------------------------------------

    adjustment_map = (
        build_era_adjustments(conn)
    )

    weakness, weakness_df = (
        get_topic_weakness(
            conn,
            user_id
        )
    )

    # Keep the five-value return interface; metadata travels with the cached result.
    weakness_df.attrs["rating_note"] = rating_note

    candidates = get_candidates(
        conn,
        user_id,
        adjustment_map
    )


    if candidates.empty:

        result = (
            user_rating,
            weakness_df,
            candidates,
            candidates,
            candidates
        )

        recommendation_cache.put(cache_key, result)
        return result


    # ------------------------------------------------
    # Weakness match
    # ------------------------------------------------

    def weakness_match(tags):

        values = [
            weakness[tag]
            for tag in tags
            if tag in weakness
        ]

        if not values:
            return 0

        values.sort(
            reverse=True
        )

        result = values[0]

        # second relevant weakness matters,
        # but prevents "many tags = automatic win"
        if len(values) >= 2:
            result += (
                0.35
                *
                values[1]
            )

        return min(
            100,
            result
        )


    candidates[
        "weakness_match"
    ] = candidates["tags"].apply(
        weakness_match
    )


    # ------------------------------------------------
    # Predicted solve probability
    #
    # Elo-style curve:
    # equal rating ~= 50%
    # ------------------------------------------------

    candidates[
        "predicted_solve"
    ] = candidates[
        "effective_rating"
    ].apply(

        lambda r:

        1
        /
        (
            1
            +
            10 **
            (
                (r - user_rating)
                /
                400
            )
        )

    )


    # Smart training target:
    # around 40% predicted solve probability
    TARGET_PROBABILITY = 0.40


    candidates[
        "difficulty_fit"
    ] = candidates[
        "predicted_solve"
    ].apply(

        lambda p:

        max(
            0,
            100
            *
            (
                1
                -
                abs(
                    p
                    -
                    TARGET_PROBABILITY
                )
                /
                TARGET_PROBABILITY
            )
        )

    )


    # ------------------------------------------------
    # Final Smart Pick score
    # ------------------------------------------------

    candidates[
        "recommendation_score"
    ] = (

        0.55
        *
        candidates[
            "weakness_match"
        ]

        +

        0.35
        *
        candidates[
            "difficulty_fit"
        ]

        +

        0.10
        *
        candidates[
            "classic_score"
        ]

    )


    main = (

        candidates[
            candidates[
                "weakness_match"
            ] > 0
        ]

        .sort_values(
            "recommendation_score",
            ascending=False
        )

        .head(15)

        .copy()
    )


    # ------------------------------------------------
    # QUICK SOLVE
    # ------------------------------------------------

    quick_target = (
        user_rating - 300
    )


    quick = candidates[
        abs(
            candidates[
                "effective_rating"
            ]
            -
            quick_target
        )
        <= 150
    ].copy()


    quick[
        "mode_score"
    ] = (

        100

        -
        abs(
            quick[
                "effective_rating"
            ]
            -
            quick_target
        )
        /
        1.5

    ).clip(lower=0)


    quick[
        "mode_score"
    ] = (

        0.65
        *
        quick[
            "mode_score"
        ]

        +

        0.35
        *
        quick[
            "classic_score"
        ]

    )


    quick = quick.sort_values(
        [
            "is_classic",
            "mode_score"
        ],
        ascending=False
    ).head(5)


    # ------------------------------------------------
    # DEEP THINK
    # ------------------------------------------------

    deep_target = (
        user_rating + 300
    )


    deep = candidates[
        abs(
            candidates[
                "effective_rating"
            ]
            -
            deep_target
        )
        <= 150
    ].copy()


    deep[
        "mode_score"
    ] = (

        100

        -
        abs(
            deep[
                "effective_rating"
            ]
            -
            deep_target
        )
        /
        1.5

    ).clip(lower=0)


    deep[
        "mode_score"
    ] = (

        0.65
        *
        deep[
            "mode_score"
        ]

        +

        0.35
        *
        deep[
            "classic_score"
        ]

    )


    deep = deep.sort_values(
        [
            "is_classic",
            "mode_score"
        ],
        ascending=False
    ).head(5)


    result = (
        user_rating,
        weakness_df,
        main,
        quick,
        deep
    )

    recommendation_cache.put(cache_key, result)
    return result


def get_cache_stats():
    return recommendation_cache.stats()
