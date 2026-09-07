import requests
from db import get_connection

from datetime import datetime, timezone





def classify_contest(name):
    name = name.lower()

    if "educational" in name:
        return "Educational"

    if "div. 1 + div. 2" in name:
        return "Combined"

    if "div. 4" in name:
        return "Div4"

    if "div. 3" in name:
        return "Div3"

    if "div. 2" in name:
        return "Div2"

    if "div. 1" in name:
        return "Div1"

    if "global" in name:
        return "Global"

    return "Other"


def main():
    conn = get_connection()
    try:
        cursor = conn.cursor()


        # ------------------------------------------------
        # Contest metadata
        # ------------------------------------------------

        print("Fetching contests...")

        contest_data = requests.get(
            "https://codeforces.com/api/contest.list?gym=false",
            timeout=30
        ).json()

        contest_map = {}

        if contest_data["status"] != "OK":
            raise RuntimeError("Contest metadata fetch failed: " + str(contest_data.get("comment", "Unknown error")))

        if contest_data["status"] == "OK":

            for contest in contest_data["result"]:

                contest_id = contest["id"]

                timestamp = contest.get("startTimeSeconds")

                if timestamp is not None:
                    start = datetime.fromtimestamp(
                        timestamp,
                        tz=timezone.utc
                    ).replace(tzinfo=None)
                else:
                    start = None

                contest_map[contest_id] = {
                    "start": start,
                    "group": classify_contest(contest["name"])
                }


        # ------------------------------------------------
        # Problemset
        # ------------------------------------------------

        print("Fetching problemset...")

        data = requests.get(
            "https://codeforces.com/api/problemset.problems",
            timeout=30
        ).json()

        if data["status"] != "OK":
            print("Problemset fetch failed.")
            exit()


        problems = data["result"]["problems"]
        statistics = data["result"]["problemStatistics"]


        # ------------------------------------------------
        # solvedCount map
        # ------------------------------------------------

        solved_map = {}

        for stat in statistics:

            key = (
                stat.get("contestId"),
                stat.get("index")
            )

            solved_map[key] = stat.get("solvedCount", 0)


        # ------------------------------------------------
        # Existing topics cache
        # ------------------------------------------------

        cursor.execute(
            "SELECT id, name FROM topics"
        )

        topic_cache = {}

        for topic_id, name in cursor.fetchall():
            topic_cache[name] = topic_id


        # ------------------------------------------------
        # Import
        # ------------------------------------------------

        count = 0

        for problem in problems:

            contest_id = problem.get("contestId")
            index = problem.get("index")

            if contest_id is None or index is None:
                continue

            title = problem.get("name")
            rating = problem.get("rating")
            tags = problem.get("tags", [])

            external_id = f"{contest_id}-{index}"

            contest_info = contest_map.get(
                contest_id,
                {
                    "start": None,
                    "group": "Other"
                }
            )

            solved_count = solved_map.get(
                (contest_id, index),
                0
            )


            # --------------------------------------------
            # Insert / update problem
            # --------------------------------------------

            cursor.execute(
                """
                INSERT INTO problems
                (
                    platform,
                    external_id,
                    title,
                    difficulty,
                    contest_id,
                    problem_index,
                    contest_start,
                    contest_group,
                    solved_count
                )

                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)

                ON DUPLICATE KEY UPDATE
                    title = %s,
                    difficulty = %s,
                    contest_id = %s,
                    problem_index = %s,
                    contest_start = %s,
                    contest_group = %s,
                    solved_count = %s
                """,
                (
                    "Codeforces",
                    external_id,
                    title,
                    rating,
                    contest_id,
                    index,
                    contest_info["start"],
                    contest_info["group"],
                    solved_count,

                    title,
                    rating,
                    contest_id,
                    index,
                    contest_info["start"],
                    contest_info["group"],
                    solved_count
                )
            )


            cursor.execute(
                """
                SELECT id
                FROM problems
                WHERE platform = 'Codeforces'
                AND external_id = %s
                """,
                (external_id,)
            )

            problem_id = cursor.fetchone()[0]


            # --------------------------------------------
            # Tags
            # --------------------------------------------

            for tag in tags:

                if tag not in topic_cache:

                    cursor.execute(
                        """
                        INSERT IGNORE INTO topics(name)
                        VALUES (%s)
                        """,
                        (tag,)
                    )

                    cursor.execute(
                        """
                        SELECT id
                        FROM topics
                        WHERE name = %s
                        """,
                        (tag,)
                    )

                    topic_cache[tag] = cursor.fetchone()[0]


                topic_id = topic_cache[tag]

                cursor.execute(
                    """
                    INSERT IGNORE INTO problem_topics
                    (problem_id, topic_id)

                    VALUES (%s, %s)
                    """,
                    (
                        problem_id,
                        topic_id
                    )
                )


            count += 1

            if count % 500 == 0:
                conn.commit()
                print("Imported:", count)


        conn.commit()

        print("Problemset update completed.")


    finally:
        conn.close()


if __name__ == "__main__":
    main()
