import requests
from db import get_connection


BASE_URL = "https://c2-ladders-juol.onrender.com/api/ladder"


def fetch_ladder(start_rating, end_rating):
    response = requests.get(
        BASE_URL,
        params={
            "startRating": start_rating,
            "endRating": end_rating,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data["data"]


def main():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        total_added = 0
        total_updated = 0
        total_missing = 0

        for start_rating in range(800, 3500, 100):
            end_rating = start_rating + 100

            print(
                f"Fetching C2 ladder "
                f"{start_rating}-{end_rating}..."
            )

            problems = fetch_ladder(
                start_rating,
                end_rating,
            )

            for problem in problems:
                contest_id = problem.get("contestId")
                index = problem.get("index")
                frequency = problem.get("frequency", 0)

                if contest_id is None or index is None:
                    continue

                external_id = f"{contest_id}-{index}"

                cursor.execute(
                    """
                    SELECT id
                    FROM problems
                    WHERE platform = 'Codeforces'
                      AND external_id = %s
                    """,
                    (external_id,),
                )

                row = cursor.fetchone()

                if row is None:
                    total_missing += 1
                    continue

                problem_id = row[0]

                cursor.execute(
                    """
                    INSERT INTO classic_problems
                        (problem_id, source, frequency)
                    VALUES (%s, %s, %s)

                    ON DUPLICATE KEY UPDATE
                        frequency = %s
                    """,
                    (
                        problem_id,
                        "C2Ladders",
                        frequency,
                        frequency,
                    ),
                )

                if cursor.rowcount == 1:
                    total_added += 1
                elif cursor.rowcount == 2:
                    total_updated += 1

            conn.commit()

        print()
        print("C2Ladders import completed.")
        print("New classic rows added:", total_added)
        print("Existing rows updated:", total_updated)
        print(
            "C2 problems not found locally:",
            total_missing,
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()