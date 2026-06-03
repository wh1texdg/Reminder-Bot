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

