-- CPCompass schema for MySQL 8.0+.
-- Fresh installations: mysql -u root -p < schema.sql
-- Existing tables are preserved, not migrated. The view is recreated.
-- Change both database statements if using a custom MYSQL_DATABASE.
CREATE DATABASE IF NOT EXISTS cpcompass
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE cpcompass;

CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT,
    handle VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_handle (handle)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS problems (
    id INT NOT NULL AUTO_INCREMENT,
    platform VARCHAR(20) NOT NULL,
    external_id VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    difficulty INT DEFAULT NULL,
    contest_id INT DEFAULT NULL,
    problem_index VARCHAR(10) DEFAULT NULL,
    contest_start DATETIME DEFAULT NULL,
    contest_group VARCHAR(30) DEFAULT NULL,
    solved_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_problems_platform_external (platform, external_id),
    KEY idx_problems_platform_difficulty (platform, difficulty)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS topics (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_topics_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS submissions (
    id BIGINT NOT NULL,
    user_id INT NOT NULL,
    problem_id INT NOT NULL,
    verdict VARCHAR(50) DEFAULT NULL,
    submitted_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    KEY idx_submissions_user_problem_verdict (user_id, problem_id, verdict),
    KEY idx_submissions_user_time (user_id, submitted_at),
    KEY idx_submissions_problem (problem_id),
    CONSTRAINT fk_submissions_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_submissions_problem FOREIGN KEY (problem_id) REFERENCES problems(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS problem_topics (
    problem_id INT NOT NULL,
    topic_id INT NOT NULL,
    PRIMARY KEY (problem_id, topic_id),
    KEY idx_problem_topics_topic (topic_id),
    CONSTRAINT fk_problem_topics_problem FOREIGN KEY (problem_id) REFERENCES problems(id),
    CONSTRAINT fk_problem_topics_topic FOREIGN KEY (topic_id) REFERENCES topics(id)
) ENGINE=InnoDB;

-- Preserve the existing database's provenance field and composite key.
-- No curated data is bundled; multiple sources can identify the same problem.
CREATE TABLE IF NOT EXISTS classic_problems (
    problem_id INT NOT NULL,
    source VARCHAR(50) NOT NULL,
    frequency INT NOT NULL DEFAULT 0,

    PRIMARY KEY (problem_id, source),

    CONSTRAINT fk_classic_problems_problem
        FOREIGN KEY (problem_id)
        REFERENCES problems(id)
) ENGINE=InnoDB;

CREATE OR REPLACE SQL SECURITY INVOKER VIEW topic_stats AS
SELECT
    s.user_id,
    t.id AS topic_id,
    t.name AS topic,
    COUNT(DISTINCT s.problem_id) AS attempted,
    COUNT(DISTINCT CASE WHEN s.verdict = 'OK' THEN s.problem_id END) AS solved,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN s.verdict = 'OK' THEN s.problem_id END)
        / COUNT(DISTINCT s.problem_id), 2
    ) AS success_rate,
    SUM(CASE WHEN s.verdict <> 'OK' THEN 1 ELSE 0 END) AS wrong_submissions
FROM submissions s
JOIN problems p ON p.id = s.problem_id
JOIN problem_topics pt ON pt.problem_id = p.id
JOIN topics t ON t.id = pt.topic_id
GROUP BY s.user_id, t.id, t.name;
