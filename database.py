import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            score INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            streak INTEGER DEFAULT 1,
            grade INTEGER,
            school TEXT,
            region TEXT,
            age INTEGER,
            weak_subjects TEXT,
            free_hours TEXT,
            phone_number TEXT,
            password TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS completed_lessons (
            user_id INTEGER,
            subject_id TEXT,
            lesson_id INTEGER,
            PRIMARY KEY (user_id, subject_id, lesson_id)
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, full_name):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, phone_number FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    is_new = False
    if not row:
        cursor.execute("INSERT INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
        is_new = True
    elif not row[1]:  # Agar profil to'liq to'ldirilmagan bo'lsa
        is_new = True
        
    conn.commit()
    conn.close()
    return is_new

def update_full_profile(user_id, grade, school, region, age, weak_subjects, free_hours, phone, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET grade = ?, school = ?, region = ?, age = ?, weak_subjects = ?, free_hours = ?, phone_number = ?, password = ?
        WHERE user_id = ?
    """, (grade, school, region, age, weak_subjects, free_hours, phone, password, user_id))
    conn.commit()
    conn.close()

def update_user_activity(user_id):
    pass  # Kerakli qo'shimcha statistikalar uchun

def get_user_stats(user_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT full_name, score, level, streak, grade, school, region, age, weak_subjects, free_hours, phone_number
        FROM users WHERE user_id = ?
    """, (user_id,))
    user = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM completed_lessons WHERE user_id = ?", (user_id,))
    lessons_done = cursor.fetchone()[0]
    
    conn.close()
    return user, lessons_done

def get_leaderboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, score FROM users ORDER BY score DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_completed_lessons(user_id, subject_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT lesson_id FROM completed_lessons WHERE user_id = ? AND subject_id = ?", (user_id, subject_id))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_result(user_id, subject_id, lesson_id, score, total):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO completed_lessons VALUES (?, ?, ?)", (user_id, subject_id, lesson_id))
    cursor.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (score * 10, user_id))
    conn.commit()
    conn.close()