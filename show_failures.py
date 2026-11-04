import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESULTS_FILE = BASE_DIR / "results" / "baseline_results.json"


def show_failures():

    with open(RESULTS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    results = data["results"]

    failures = [
        result for result in results
        if not result["result_correct"]
    ]

    print(f"\nTotal failures: {len(failures)}")

    for item in failures:

        print("\n" + "=" * 60)
        print(f"Question ID: {item['id']}")
        print(f"Difficulty: {item['difficulty']}")
        print(f"Question: {item['question']}")

        print("\nGold SQL:")
        print(item["gold_sql"])

        print("\nGenerated SQL:")
        print(item["generated_sql"])

        print("\nExecution successful:", item["execution_success"])

        if item["error"]:
            print("Error:", item["error"])

        print("=" * 60)


if __name__ == "__main__":
    show_failures()