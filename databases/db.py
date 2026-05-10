import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

from config import settings

# Connection pool
_pool = SimpleConnectionPool(1, 10, settings.database_url)


def get_connection():
    """Get a connection from the pool."""
    return _pool.getconn()


def return_connection(conn):
    """Return a connection to the pool."""
    _pool.putconn(conn)


def execute_query(query: str, params: tuple = None, fetch: str = None):
    """Execute a query and optionally fetch results.

    Args:
        query: SQL query string
        params: Query parameters (tuple)
        fetch: 'one', 'all', or None (for INSERT/UPDATE/DELETE)

    Returns:
        Single row dict, list of dicts, or None depending on fetch parameter
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch == 'one':
                result = cur.fetchone()
                conn.commit()
                return result
            elif fetch == 'all':
                result = cur.fetchall()
                conn.commit()
                return result
            else:
                conn.commit()
                return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        return_connection(conn)


def execute_transaction(queries: list[tuple[str, tuple]]):
    """Execute multiple queries in a single transaction.

    Args:
        queries: List of (query, params) tuples
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for query, params in queries:
                cur.execute(query, params or ())
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        return_connection(conn)


@contextmanager
def get_db():
    """Dependency for FastAPI endpoints - provides a query executor."""
    class QueryExecutor:
        @staticmethod
        def query_one(query: str, params: tuple = None):
            return execute_query(query, params, fetch='one')

        @staticmethod
        def query_all(query: str, params: tuple = None):
            return execute_query(query, params, fetch='all')

        @staticmethod
        def execute(query: str, params: tuple = None):
            return execute_query(query, params, fetch=None)

        @staticmethod
        def execute_many(queries: list[tuple[str, tuple]]):
            return execute_transaction(queries)

    executor = QueryExecutor()
    try:
        yield executor
    finally:
        pass
