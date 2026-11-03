import json
import time
import datetime
from collections import Counter
from pathlib import Path

from db import get_connection, get_schema_text, run_query
from llm import generate_sql, MODEL_NAME

QUESTIONS_FILE = "data/chinook_questions.json"
RUN_NAME = "week1_baseline"   # change this name for every new experiment


def clean_rows(rows):
    # round decimals so 5.6500001 and 5.65 count as equal
    return [tuple(round(v, 4) if isinstance(v, float) else v for v in row) for row in rows]


def same_result(gold_rows, pred_rows, ordered):
    gold, pred = clean_rows(gold_rows), clean_rows(pred_rows)
    if ordered:
        return gold == pred                 # row order matters
    return Counter(gold) == Counter(pred)   # row order does not matter


def main():
    conn = get_connection()
    schema_text = get_schema_text(conn)
    questions = json.load(open(QUESTIONS_FILE, encoding="utf-8"))

    results = []
    for q in questions:
        gold_sql = q["gold_sql"]
        ordered = "order by" in gold_sql.lower()
        pred_sql, correct, error = None, False, None

        start = time.time()
        try:
            pred_sql = generate_sql(q["question"], schema_text)
            gold_rows = run_query(conn, gold_sql)
            pred_rows = run_query(conn, pred_sql)
            correct = same_result(gold_rows, pred_rows, ordered)
        except Exception as e:
            error = str(e)
        seconds = round(time.time() - start, 1)

        print(f"{'PASS' if correct else 'FAIL'}  Q{q['id']} [{q['difficulty']}] ({seconds}s)")
        if not correct:
            print(f"      model SQL: {pred_sql}")
            if error:
                print(f"      error: {error}")

        results.append({
            "id": q["id"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "gold_sql": gold_sql,
            "pred_sql": pred_sql,
            "correct": correct,
            "error": error,
            "seconds": seconds,
        })

    total = sum(r["correct"] for r in results)
    print(f"\nScore: {total}/{len(results)}")
    for level in ["easy", "medium", "hard"]:
        group = [r for r in results if r["difficulty"] == level]
        print(f"  {level}: {sum(r['correct'] for r in group)}/{len(group)}")

    Path("results").mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    path = f"results/{today}_{RUN_NAME}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "run": RUN_NAME,
            "model": MODEL_NAME,
            "date": today,
            "score": f"{total}/{len(results)}",
            "results": results,
        }, f, indent=2)
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()