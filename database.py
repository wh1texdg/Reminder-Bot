import asyncio
import asyncpg

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
            deadline_at TIMESTAMP
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
        "SELECT * FROM deadlines WHERE user_id = $1",
        user_id)

async def add_task(conn,user_id,title, deadline_at):
    await conn.execute("""
        INSERT INTO deadlines (user_id, title, deadline_at) 
        VALUES ($1, $2, $3)
    """, user_id, title, deadline_at)