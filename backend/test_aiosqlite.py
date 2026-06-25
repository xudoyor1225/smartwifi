import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import event

engine = create_async_engine('sqlite+aiosqlite:///:memory:')

@event.listens_for(engine.sync_engine, 'connect')
def set_pragma(dbapi_connection, record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.close()

async def main():
    async with engine.begin() as conn:
        print('Connected successfully!')

asyncio.run(main())
