import json
import sqlite3

# 1. Connect to SQLite database
conn = sqlite3.connect("data/chinook.db")
cursor = conn.cursor()

# 2. Extract database schema
cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
tables = cursor.fetchall()

schema = {}
for table in tables:
    table_name = table[0]
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    schema[table_name] = [column[1] for column in columns]

# Format schema as a text string
schema_text = ""
for table_name, columns in schema.items():
    schema_text += f"Table: {table_name}\n"
    schema_text += f"Columns: {', '.join(columns)}\n\n"

print("--- Database Schema Loaded ---")
print(schema_text)

# 3. Load questions and queries from JSON file
json_path = "data/chinook_questions.json"
with open(json_path, "r", encoding="utf-8") as f:
    questions_data = json.load(f)

print(f"--- Running {len(questions_data)} queries from {json_path} ---\n")

# 4. Execute each query and display results
for item in questions_data:
    q_id = item.get("id")
    difficulty = item.get("difficulty")
    question = item.get("question")
    sql_query = item.get("gold_sql")

    print(f"[{difficulty.upper()}] Q{q_id}: {question}")
    print(f"SQL: {sql_query}")

    try:
        cursor.execute(sql_query)
        rows = cursor.fetchall()

        # Get column names returned by the query
        col_names = [desc[0] for desc in cursor.description] if cursor.description else []
        print(f"Columns: {col_names}")

        # Print the first few rows (limited to 5 for readable terminal output)
        if rows:
            for row in rows[:5]:
                print(f"  -> {row}")
            if len(rows) > 5:
                print(f"  ... ({len(rows) - 5} more rows)")
        else:
            print("  -> (No rows returned)")

    except sqlite3.Error as e:
        print(f"  ERROR executing query: {e}")

    print("-" * 60)

# 5. Clean up connection
cursor.close()
conn.close()