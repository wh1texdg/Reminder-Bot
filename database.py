import asyncio

async def create_tables(conn):
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT
        )
    ''')

    await conn.execute('''
        CREATE TABLE IF NOT EXISTS deadlines (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            title TEXT,
            deadline_at TIMESTAMP,
            remind_mode TEXT DEFAULT 'intervals',
            reminded_48h BOOLEAN DEFAULT FALSE,
            reminded_24h BOOLEAN DEFAULT FALSE,
            reminded_12h BOOLEAN DEFAULT FALSE,
            last_reminded_at TIMESTAMP
        )
    ''')

async def add_user(conn, user_id, username):
    await conn.execute("""
        INSERT INTO users (user_id, username)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO NOTHING
        """, user_id, username)
    
async def get_deadlines(conn, user_id):
    return await conn.fetch(
        "SELECT * FROM deadlines WHERE user_id = $1 ORDER BY deadline_at",
        user_id)

async def add_task(conn,user_id,title, deadline_at,remind_mode):
    await conn.execute("""
        INSERT INTO deadlines (user_id, title, deadline_at,remind_mode) 
        VALUES ($1, $2, $3, $4)
    """, user_id, title, deadline_at,remind_mode)

async def edit_task(conn, id, user_id, title=None, deadline_at=None):
    if title:
        await conn.execute("""
            UPDATE deadlines SET title = $1
            WHERE id = $2 AND user_id = $3
        """, title, id, user_id)
    if deadline_at:
        await conn.execute("""
            UPDATE deadlines SET deadline_at = $1
            WHERE id = $2 AND user_id = $3
        """, deadline_at, id, user_id)

async def delete_task(conn, id, user_id):
    await conn.execute("""
        DELETE FROM deadlines WHERE id = $1 AND user_id = $2
    """, id, user_id)

async def get_all_deadlines(conn):
    return await conn.fetch("SELECT * FROM deadlines")