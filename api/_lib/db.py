import os
import psycopg2
import psycopg2.extras


def get_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise Exception('DATABASE_URL environment variable is not set')
    conn = psycopg2.connect(database_url, sslmode='require')
    return conn


def query(sql, params=None, fetchone=False, fetchall=False):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetchone:
                result = cur.fetchone()
            elif fetchall:
                result = cur.fetchall()
            else:
                result = None
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            try:
                return cur.rowcount
            except Exception:
                return 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_many(sql, params_list):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)
            conn.commit()
            return cur.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_returning(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
