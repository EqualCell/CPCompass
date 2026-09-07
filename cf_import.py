from datetime import datetime, timezone
from db import get_connection
from cf_api import api_get, CodeforcesError




def import_codeforces_user(handle, on_status=None):
    """Validate and atomically refresh one profile; return its database user ID."""
    handle = handle.strip()
    if not handle:
        raise CodeforcesError("Please enter a Codeforces handle.")
    if ";" in handle or any(ch.isspace() for ch in handle):
        raise CodeforcesError("Please enter one Codeforces handle without spaces.")
    report = on_status if on_status is not None else lambda message: None
    report("Validating Codeforces handle...")
    profile = api_get("user.info", handles=handle)[0]
    handle = profile["handle"]
    report("Fetching Codeforces submissions...")
    submissions = api_get("user.status", handle=handle)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users(handle) VALUES (%s) ON DUPLICATE KEY UPDATE handle = %s",
                (handle, handle)
            )
            cursor.execute("SELECT id FROM users WHERE handle = %s", (handle,))
            user_id = cursor.fetchone()[0]
            cursor.execute("SELECT id, name FROM topics")
            topic_ids = {name: topic_id for topic_id, name in cursor.fetchall()}
            problem_ids = {}
            for submission in submissions:
                problem = submission["problem"]
                contest_id = problem.get("contestId")
                index = problem.get("index")
                title = problem["name"]
                external_id = f"{contest_id}-{index}" if contest_id is not None else f"{title}-{index}"
                if external_id not in problem_ids:
                    cursor.execute(
                        """INSERT INTO problems
                        (platform, external_id, title, difficulty, contest_id, problem_index)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)""",
                        ("Codeforces", external_id, title, problem.get("rating"), contest_id, index)
                    )
                    cursor.execute(
                        "SELECT id FROM problems WHERE platform = %s AND external_id = %s",
                        ("Codeforces", external_id)
                    )
                    problem_ids[external_id] = cursor.fetchone()[0]
                    for tag in problem.get("tags", []):
                        if tag not in topic_ids:
                            cursor.execute(
                                "INSERT INTO topics(name) VALUES (%s) ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)",
                                (tag,)
                            )
                            cursor.execute("SELECT id FROM topics WHERE name = %s", (tag,))
                            topic_ids[tag] = cursor.fetchone()[0]
                        cursor.execute(
                            """INSERT INTO problem_topics(problem_id, topic_id) VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE topic_id = %s""",
                            (problem_ids[external_id], topic_ids[tag], topic_ids[tag])
                        )
                # Refresh verdicts too: an existing pending submission may now be judged.
                verdict = submission.get("verdict")
                cursor.execute(
                    """INSERT INTO submissions(id, user_id, problem_id, verdict, submitted_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE verdict = %s""",
                    (submission["id"], user_id, problem_ids[external_id], verdict,
                     datetime.fromtimestamp(submission["creationTimeSeconds"], timezone.utc).replace(tzinfo=None),
                     verdict)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conn.close()
    report(f"Imported {len(submissions)} submissions")
    report("Profile ready")
    return user_id


def main():
    try:
        import_codeforces_user(input("Enter Codeforces handle: "), on_status=print)
    except CodeforcesError as exc:
        print(str(exc))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
