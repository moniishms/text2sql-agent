import sqlite3

DB_PATH = "file:data/chinook.db?mode=ro"

def get_connection():
    return sqlite3.connect(DB_PATH, uri=True)

def get_schema_text(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
    tables = [row[0] for row in cur.fetchall()]

    lines = []
    for table in tables:
        cur.execute(f'PRAGMA table_info("{table}");')
        columns = [f"{c[1]} ({c[2]})" for c in cur.fetchall()]  # name (type)
        lines.append(f"Table {table}: " + ", ".join(columns))

        cur.execute(f'PRAGMA foreign_key_list("{table}");')
        for fk in cur.fetchall():
            # fk[2] = table it points to, fk[3] = this column, fk[4] = that column
            lines.append(f"  Link: {table}.{fk[3]} -> {fk[2]}.{fk[4]}")
    return "\n".join(lines)

def run_query(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchall()