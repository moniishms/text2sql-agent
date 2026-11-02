from database_verfication import schema_text
# pyrefly: ignore[missing-import]
import ollama
import sqlite3
import re


MODEL_NAME = "qwen-coder"
# pyrefly: ignore[name-defined] 
DATABASE_URI = "file:data/chinook.db?mode=ro"
MAX_ATTEMPTS = 3


# Remove Markdown fences and extract SQL from the model response
def clean_sql(response):
    response = response.strip()

    match = re.search(
        r"```(?:sql)?\s*(.*?)```",
        response,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return match.group(1).strip()

    match = re.search(
        r"\b(SELECT|WITH)\b.*?(?:;|$)",
        response,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return match.group(0).strip()

    return response

def handle_general_question(question):
    text = question.lower().strip().rstrip("?!.")

    general_responses = {
        "what is your name": "I'm your Text-to-SQL assistant.",
        "whats your name": "I'm your Text-to-SQL assistant.",
        "who are you": "I'm a Text-to-SQL assistant for the Chinook database.",
        "hello": "Hello! Ask me a question about the Chinook database.",
        "hi": "Hi! What would you like to know about the Chinook database?",
        "hey": "Hey! Ask me something about the Chinook database.",
        "thank you": "You're welcome!",
        "thanks": "You're welcome!",
        "help": "Ask questions about customers, artists, albums, tracks, invoices, and other data in the Chinook database."
    }

    return general_responses.get(text)
# Basic protection against destructive natural-language requests
def is_read_only_request(question):
    blocked_patterns = [
        r"\bdelete\b",
        r"\bdrop\b",
        r"\bupdate\b",
        r"\binsert\b",
        r"\balter\b",
        r"\btruncate\b",
        r"\bcreate\b",
        r"\breplace\b",
    ]

    return not any(
        re.search(pattern, question, re.IGNORECASE)
        for pattern in blocked_patterns
    )


# Validate the SQL structure before execution
def validate_sql(query):
    query = query.strip()

    if not re.match(r"^(SELECT|WITH)\b", query, re.IGNORECASE):
        raise ValueError("Only read-only SELECT queries are allowed.")

    # Allow one optional trailing semicolon, but reject multiple statements
    if ";" in query.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed.")

    if not query:
        raise ValueError("The generated SQL query is empty.")

    return query


# Detect simple requests such as "give me the top 5 customers"
def simple_top_query(question):
    question_lower = question.lower()

    # Do not apply this fallback when the user specifies a ranking metric
    ranking_terms = [
        "spent", "spending", "revenue", "sales", "profit",
        "most purchases", "most orders", "highest", "lowest",
        "maximum", "minimum", "most", "least", "best", "worst",
        "top-rated", "top rated"
    ]

    if any(term in question_lower for term in ranking_terms):
        return None

    patterns = [
        r"\btop\s+(\d+)\s+(?:of\s+the\s+)?([a-zA-Z_]+)",
        r"\b(\d+)\s+(?:of\s+the\s+)?([a-zA-Z_]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, question_lower)

        if not match:
            continue

        limit = int(match.group(1))
        requested_name = match.group(2).rstrip("s")

        if limit < 1 or limit > 100:
            return None

        # Match the requested entity to a real table in the database
        table_names = [
            row[0]
            for row in sqlite3.connect(DATABASE_URI, uri=True).execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]

        table_name = None

        for name in table_names:
            normalized = name.lower().rstrip("s")

            if normalized == requested_name:
                table_name = name
                break

        if table_name is None:
            continue

        # Quote the table identifier obtained from the database itself
        return f'SELECT * FROM "{table_name}" LIMIT {limit}'

    return None


# Correct failed SQL using the actual SQLite error
def recover_simple_top_query(question, query, error):
    if "no such column:" not in error.lower():
        return None

    fallback = simple_top_query(question)

    if fallback:
        return fallback

    return None


# Ask Qwen to generate SQL or correct a failed query
def generate_sql(question, error=None, failed_query=None):
    if error is None:
        prompt = f"""
You are a SQLite Text-to-SQL assistant.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

RULES:
- Return exactly one SQLite SELECT query.
- Use only tables and columns in the schema.
- Never invent columns, tables, or aliases.
- Do not use SQL Server TOP syntax. SQLite uses LIMIT.
- "Top N" without a ranking criterion means N records,
  not a spending or popularity ranking.
- If the user explicitly requests highest spending,
  calculate it using Invoice and/or InvoiceLine.
- Use joins and aggregate functions when necessary.
- Return SQL only, without Markdown fences or explanations.
"""
    else:
        prompt = f"""
You are correcting a failed SQLite query.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

FAILED QUERY:
{failed_query}

SQLITE ERROR:
{error}

Generate a corrected SQLite SELECT query.

Rules:
- Fix the specific error shown above.
- Do not repeat nonexistent columns from the failed query.
- Check every table and column against the schema.
- Do not invent names such as Total or InvoiceTotal.
- Use LIMIT for SQLite row limits.
- If ranking by spending was requested, calculate spending
  from the appropriate invoice tables.
- Return SQL only, without Markdown fences or explanations.
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return clean_sql(response.message.content)


def print_results(cursor, results):
    if cursor.description:
        columns = [item[0] for item in cursor.description]
        print(" | ".join(columns))
        print("-" * 60)

    for row in results:
        print(row)

    if not results:
        print("No results found.")


def main():
    conn = None

    try:
        # Keep the database read-only
        conn = sqlite3.connect(DATABASE_URI, uri=True)
        cursor = conn.cursor()

        print("Text-to-SQL Agent is ready!")
        print("Ask questions about the Chinook database.")
        print("Type 'exit' to quit.\n")

        while True:
            question = input("Ask a question: ").strip()

            if question.lower() == "exit":
                print("Goodbye!")
                break

            if not question:
                print("Please enter a question.\n")
                continue

            response = handle_general_question(question)

            if response:
                print(response, "\n")
                continue

            if not is_read_only_request(question):
                print(
                    "Rejected: this agent only supports "
                    "data-retrieval questions.\n"
                )
                continue

            # Handle straightforward top-N retrieval deterministically
            query = simple_top_query(question)

            if query:
                print("\nUsing a simple retrieval query.")
            else:
                try:
                    query = generate_sql(question)
                except Exception as e:
                    print("Could not generate SQL:", e, "\n")
                    continue

            success = False

            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"\nAttempt {attempt}/{MAX_ATTEMPTS}")
                print("Generated SQL:\n", query)

                try:
                    query = validate_sql(query)
                except ValueError as e:
                    print("Validation error:", e)
                    break

                try:
                    cursor.execute(query)
                    results = cursor.fetchall()

                    print("\nQuery executed successfully!")
                    print_results(cursor, results)

                    success = True
                    break

                except sqlite3.Error as e:
                    error = str(e)
                    print("SQL execution error:", error)

                    if attempt == MAX_ATTEMPTS:
                        print("Maximum attempts reached.")
                        break

                    # Try a deterministic fallback for simple top-N requests
                    fallback = recover_simple_top_query(
                        question, query, error
                    )

                    if fallback and fallback != query:
                        query = fallback
                        continue

                    # Otherwise ask the model to repair its SQL
                    try:
                        query = generate_sql(
                            question,
                            error=error,
                            failed_query=query
                        )
                    except Exception as model_error:
                        print(
                            "Could not generate correction:",
                            model_error
                        )
                        break

            if not success:
                print("The agent could not complete the query.")

            print()

    except sqlite3.Error as e:
        print("Database connection error:", e)

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
