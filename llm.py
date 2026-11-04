
import re
import json
import time
import sqlite3
import ollama

from pathlib import Path
from collections import Counter


# ==================================================
# 1. CONFIGURATION
# ==================================================

MODEL_NAME = "qwen-coder"

BASE_DIR = Path(__file__).resolve().parent

DATABASE_PATH = BASE_DIR / "data" / "chinook.db"
QUESTIONS_PATH = BASE_DIR / "data" / "chinook_questions.json"

RESULTS_DIR = BASE_DIR / "results"

RUN_NAME = "week1_baseline_v2"

RESULTS_JSON = RESULTS_DIR / f"{RUN_NAME}_results.json"
SUMMARY_FILE = RESULTS_DIR / f"{RUN_NAME}_summary.txt"


# ==================================================
# 2. GET FULL DATABASE SCHEMA
# ==================================================

def get_database_schema():

    connection = sqlite3.connect(
        f"file:{DATABASE_PATH.resolve().as_posix()}?mode=ro",
        uri=True
    )

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        tables = cursor.fetchall()

        schema = ""

        for table_name, create_statement in tables:

            schema += f"\nTABLE: {table_name}\n"

            cursor.execute(
                f'PRAGMA table_info("{table_name}")'
            )

            columns = cursor.fetchall()

            for column in columns:
                column_name = column[1]
                column_type = column[2]

                schema += f"  {column_name} ({column_type})\n"

            # Include foreign key relationships
            cursor.execute(
                f'PRAGMA foreign_key_list("{table_name}")'
            )

            foreign_keys = cursor.fetchall()

            for fk in foreign_keys:

                schema += (
                    f"  FOREIGN KEY: {fk[3]} "
                    f"REFERENCES {fk[2]}({fk[4]})\n"
                )

        return schema

    finally:
        connection.close()


# ==================================================
# 3. CLEAN GENERATED SQL
# ==================================================

def clean_sql(response):

    response = response.strip()

    # Remove Markdown code fences
    match = re.search(
        r"```(?:sql)?\s*(.*?)```",
        response,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        response = match.group(1).strip()

    # Extract SELECT or WITH query
    match = re.search(
        r"\b(SELECT|WITH)\b.*?(?:;|$)",
        response,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return match.group(0).strip()

    return response


# ==================================================
# 4. GENERATE SQL USING OLLAMA
# ==================================================

def generate_sql(question, schema_text):

    prompt = f"""
You are an expert SQLite Text-to-SQL assistant.

Your task is to convert a natural language question
into one correct SQLite SELECT query.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

RULES:
1. Return exactly one SQLite SELECT query.
2. Use only tables and columns present in the schema.
3. Never invent table names or column names.
4. Use correct JOIN conditions.
5. Use SQLite syntax.
6. Use aggregate functions when required.
7. Use GROUP BY when necessary.
8. Follow all conditions mentioned in the question.
9. Do not add unnecessary columns.
10. Return SQL only, without explanations.

SQL:
"""

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0
        }
    )

    return clean_sql(response.message.content)


# ==================================================
# 5. EXECUTE SQL SAFELY
# ==================================================

def execute_sql(query):

    query = query.strip()

    if not query:
        raise ValueError("Empty SQL query.")

    # Basic first-level read-only check
    if not re.match(
        r"^(SELECT|WITH)\b",
        query,
        re.IGNORECASE
    ):
        raise ValueError("Only SELECT queries are allowed.")

    connection = sqlite3.connect(
        f"file:{DATABASE_PATH.resolve().as_posix()}?mode=ro",
        uri=True
    )

    try:

        # Additional read-only protection
        connection.execute("PRAGMA query_only = ON")

        cursor = connection.cursor()

        cursor.execute(query)

        rows = cursor.fetchall()

        return rows

    finally:
        connection.close()


# ==================================================
# 6. NORMALIZE AND COMPARE RESULTS
# ==================================================

def normalize_value(value):

    if isinstance(value, float):
        return round(value, 6)

    return value


def compare_results(generated_rows, gold_rows,gold_sql):

    generated = [
        tuple(normalize_value(value) for value in row)
        for row in generated_rows
    ]

    expected = [
        tuple(normalize_value(value) for value in row)
        for row in gold_rows
    ]
    
    has_order_by = re.search(
        r"\bORDER\s+BY\b",
        gold_sql,
        re.IGNORECASE
    )

    if has_order_by:
        return generated == expected

    # Compare as multisets:
    # ignores row ordering but preserves duplicate counts.
    return Counter(generated) == Counter(expected)


# ==================================================
# 7. EVALUATE ONE QUESTION
# ==================================================

def evaluate_question(item, schema_text):

    question_id = item["id"]
    question = item["question"]
    gold_sql = item["gold_sql"]
    difficulty = item["difficulty"].lower()

    if difficulty == "med":
        difficulty = "medium"

    print("\n" + "=" * 60)
    print(f"QUESTION {question_id} ({difficulty.upper()})")
    print("=" * 60)

    print("Question:", question)

    result = {
        "id": question_id,
        "question": question,
        "difficulty": difficulty,
        "gold_sql": gold_sql,
        "generated_sql": None,
        "execution_success": False,
        "result_correct": False,
        "generation_time_seconds": None,
        "error": None
    }

    try:

        # First execute reference SQL
        gold_rows = execute_sql(gold_sql)

    except Exception as error:

        result["error"] = (
            f"Reference SQL failed: {str(error)}"
        )

        print(result["error"])

        return result

    try:

        # Generate SQL
        start_time = time.time()

        generated_sql = generate_sql(
            question,
            schema_text
        )

        generation_time = time.time() - start_time

        result["generated_sql"] = generated_sql

        result["generation_time_seconds"] = round(
            generation_time, 3
        )

        print("\nGenerated SQL:")
        print(generated_sql)

        # Execute generated SQL
        generated_rows = execute_sql(generated_sql)

        result["execution_success"] = True

        # Compare generated result with reference result
        is_correct = compare_results(
            generated_rows,
            gold_rows,
            gold_sql
        )

        result["result_correct"] = is_correct

        result["generated_rows"] = generated_rows
        result["gold_rows"] = gold_rows

        if is_correct:
            print("\nResult: CORRECT")
        else:
            print("\nResult: INCORRECT")

        print("Generated rows:", generated_rows)
        print("Expected rows:", gold_rows)

    except Exception as error:

        result["error"] = str(error)

        print("\nEvaluation failed:", error)

    return result


# ==================================================
# 8. MAIN EVALUATION
# ==================================================

def main():

    # Check required files
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    if not QUESTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Questions JSON not found: {QUESTIONS_PATH}"
        )

    # Create results directory if necessary
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Load questions
    with open(
        QUESTIONS_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        questions = json.load(file)

    if not isinstance(questions, list):
        raise ValueError(
            "JSON must contain a list of question objects."
        )

    if len(questions) != 20:
        print(
            f"WARNING: Expected 20 questions, "
            f"but found {len(questions)}."
        )

    # Read complete database schema
    schema_text = get_database_schema()

    print("\n" + "=" * 60)
    print("TEXT-TO-SQL BASELINE EVALUATION")
    print("=" * 60)

    print("Model:", MODEL_NAME)
    print("Database:", DATABASE_PATH.name)
    print("Total questions:", len(questions))

    # Evaluate all questions
    results = []

    for item in questions:

        result = evaluate_question(
            item,
            schema_text
        )

        results.append(result)

    # ==================================================
    # 9. CALCULATE OVERALL SCORES
    # ==================================================

    total = len(results)

    correct = sum(
        1 for result in results
        if result["result_correct"]
    )

    executed = sum(
        1 for result in results
        if result["execution_success"]
    )

    accuracy = (
        (correct / total) * 100
        if total else 0
    )

    execution_rate = (
        (executed / total) * 100
        if total else 0
    )

    # Difficulty-wise performance
    difficulty_scores = {}

    for level in ["easy", "medium", "hard"]:

        level_results = [
            result for result in results
            if result["difficulty"] == level
        ]

        level_correct = sum(
            1 for result in level_results
            if result["result_correct"]
        )

        level_total = len(level_results)

        level_accuracy = (
            (level_correct / level_total) * 100
            if level_total else 0
        )

        difficulty_scores[level] = {
            "correct": level_correct,
            "total": level_total,
            "accuracy": round(level_accuracy, 2)
        }

    # ==================================================
    # 10. SAVE DETAILED RESULTS AS JSON
    # ==================================================

    output = {
        "model": MODEL_NAME,
        "total_questions": total,
        "executed_successfully": executed,
        "execution_rate": round(execution_rate, 2),
        "correct_answers": correct,
        "accuracy": round(accuracy, 2),
        "difficulty_scores": difficulty_scores,
        "results": results
    }

    with open(
        RESULTS_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            default=str
        )

    # ==================================================
    # 11. SAVE SUMMARY
    # ==================================================

    summary = f"""
TEXT-TO-SQL BASELINE EVALUATION
========================================

Model: {MODEL_NAME}
Database: {DATABASE_PATH.name}

TOTAL PERFORMANCE
----------------------------------------

Total Questions: {total}
Successfully Executed: {executed}
Execution Rate: {execution_rate:.2f}%

Correct Answers: {correct}
Overall Accuracy: {accuracy:.2f}%


DIFFICULTY-WISE PERFORMANCE
----------------------------------------

Easy:
{difficulty_scores['easy']['correct']}/{difficulty_scores['easy']['total']}
Accuracy: {difficulty_scores['easy']['accuracy']}%

Medium:
{difficulty_scores['medium']['correct']}/{difficulty_scores['medium']['total']}
Accuracy: {difficulty_scores['medium']['accuracy']}%

Hard:
{difficulty_scores['hard']['correct']}/{difficulty_scores['hard']['total']}
Accuracy: {difficulty_scores['hard']['accuracy']}%


========================================
"""

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(summary)

    # ==================================================
    # 12. DISPLAY FINAL RESULTS
    # ==================================================

    print("\n" + summary)

    print("Detailed results saved to:")
    print(RESULTS_JSON)

    print("\nSummary saved to:")
    print(SUMMARY_FILE)


# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    main()
