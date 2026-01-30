import os
import sqlite3
import logging
try:
    import psycopg2
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="zsxq_investment.db"):
        self.db_path = db_path
        self.db_url = os.getenv("DATABASE_URL")
        self.use_postgres = bool(self.db_url)
        
        if self.use_postgres and not psycopg2:
            logger.warning("DATABASE_URL is set but psycopg2 is not installed. Falling back to SQLite.")
            self.use_postgres = False

        self._create_table()

    def _get_conn(self):
        if self.use_postgres:
            return psycopg2.connect(self.db_url)
        else:
            return sqlite3.connect(self.db_path)

    def _prepare_query(self, query):
        """Adapt query placeholders for the target database."""
        if self.use_postgres:
            return query.replace('?', '%s')
        return query

    def _create_table(self):
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            query = '''
                CREATE TABLE IF NOT EXISTS investment_posts (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    author TEXT,
                    create_time TEXT,
                    url TEXT,
                    section_name TEXT,
                    is_analyzed INTEGER DEFAULT 0,
                    ticker TEXT,
                    suggestion TEXT,
                    logic TEXT,
                    ai_summary TEXT
                )
            '''
            cursor.execute(self._prepare_query(query))
            conn.commit()  # Explicit commit for both SQLite and PostgreSQL
            
            # Migration: Add section_name column if it doesn't exist
            try:
                alter_query = "ALTER TABLE investment_posts ADD COLUMN section_name TEXT"
                cursor.execute(self._prepare_query(alter_query))
                conn.commit()
                logger.info("Added section_name column to existing table")
            except Exception as e:
                # Ignore if column exists or any other error
                # For PostgreSQL, this might be DuplicateColumn
                # For SQLite, this might be OperationalError
                conn.rollback()  # Rollback the failed ALTER
                pass
        except Exception as e:
            logger.error(f"Error creating table: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def post_exists(self, post_id):
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.cursor()
                query = "SELECT 1 FROM investment_posts WHERE id = ?"
                cursor.execute(self._prepare_query(query), (post_id,))
                return cursor.fetchone() is not None
        finally:
            conn.close()

    def save_post(self, post_id, content, author, create_time, url, section_name=None):
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.cursor()
                query = '''
                    INSERT INTO investment_posts (id, content, author, create_time, url, section_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                '''
                cursor.execute(self._prepare_query(query), (post_id, content, author, create_time, url, section_name))
                conn.commit()
                return True
        except (sqlite3.IntegrityError, psycopg2.IntegrityError, Exception):
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_unanalyzed_posts(self, limit=None):
        """获取未分析的帖子,支持限制数量"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            query = "SELECT id, content, url, author, create_time, section_name FROM investment_posts WHERE is_analyzed = 0 ORDER BY create_time DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(self._prepare_query(query))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_unanalyzed_count(self):
        """获取未分析帖子的数量"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM investment_posts WHERE is_analyzed = 0"
            cursor.execute(self._prepare_query(query))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def update_analysis(self, post_id, ticker, suggestion, logic, ai_summary):
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.cursor()
                query = '''
                    UPDATE investment_posts
                    SET ticker = ?, suggestion = ?, logic = ?, ai_summary = ?, is_analyzed = 1
                    WHERE id = ?
                '''
                cursor.execute(self._prepare_query(query), (ticker, suggestion, logic, ai_summary, post_id))
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_post_content(self, post_id, content):
        """更新帖子内容并重置分析状态"""
        conn = self._get_conn()
        try:
            with conn: # Assuming transaction managed by context or autocommit behavior if configured, but _create_table needed explicit. Let's be safe and adhere to consistent pattern.
                cursor = conn.cursor()
                query = '''
                    UPDATE investment_posts
                    SET content = ?, is_analyzed = 0 
                    WHERE id = ?
                '''
                cursor.execute(self._prepare_query(query), (content, post_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
