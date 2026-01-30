import os
from database import Database

db = Database()
print(f'Using PostgreSQL: {db.use_postgres}')
print(f'Database URL configured: {bool(os.getenv("DATABASE_URL"))}')

try:
    count = db.get_unanalyzed_count()
    print(f'Unanalyzed posts in cloud DB: {count}')
    
    # Get total count
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM investment_posts')
    total = cursor.fetchone()[0]
    print(f'Total posts in cloud DB: {total}')
    conn.close()
except Exception as e:
    print(f'Error: {e}')
