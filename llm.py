import re
import ollama

MODEL_NAME = "qwen-coder"   # run `ollama list` to confirm the exact name


def clean_sql(response):
    response = response.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", response, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"\b(SELECT|WITH)\b.*?(?:;|$)", response, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(0).strip()
    return response


def generate_sql(question, schema_text):
    prompt = f"""You are an expert in SQLite.
Given the database schema and a question, write ONE SQLite query that answers it.
Return only the SQL, with no explanation.

Schema:
{schema_text}

Question: {question}

SQL:"""
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    return clean_sql(response.message.content)