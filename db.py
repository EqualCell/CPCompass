"""Read MySQL query results into Pandas without a SQLAlchemy dependency."""

import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv
import pandas as pd


load_dotenv(Path(__file__).with_name(".env"))


def get_connection():
    """Open MySQL using environment configuration; never default the password."""
    password = os.getenv("MYSQL_PASSWORD")
    if password is None:
        raise ValueError("MYSQL_PASSWORD is not configured. Copy .env.example to .env and configure MySQL.")
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=password,
        database=os.getenv("MYSQL_DATABASE", "cpcompass"),
    )


def read_sql(query, conn, params=None):
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        return pd.DataFrame.from_records(
            cursor.fetchall(), columns=columns, coerce_float=True
        )
    finally:
        cursor.close()
