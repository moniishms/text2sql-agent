# Week 1 — Text-to-SQL Baseline

## 1. Objective

Establish a baseline for the Text-to-SQL system using a local Qwen model and the Chinook SQLite database.

The objective was to evaluate the model's ability to convert natural-language questions into executable SQL queries without schema retrieval or additional context-retrieval techniques.

## 2. Experimental Setup

- **LLM:** qwen-coder (Qwen2.5-Coder-3B-Instruct, Q4_K_M, 3.4B reported by Ollama)
- **Database:** Chinook SQLite
- **Evaluation dataset:** 20 questions
- **Difficulty levels:** Easy, Medium, Hard
- **Schema context:** Complete database schema supplied in the prompt
- **Temperature:** 0

## 3. Baseline Results

| Metric | Result |
|---|---:|
| Total questions | 20 |
| Successfully executed | 17 |
| Execution rate | 85.00% |
| Correct answers | 15 |
| Overall accuracy | 75.00% |

## 4. Failure Analysis

Five questions were classified as incorrect.

| Question | Difficulty | Failure category |
|---|---|---|
| Q9 | Medium | Incorrect column reference and unnecessary JOIN |
| Q12 | Medium | Incorrect table/column reference |
| Q16 | Hard | Ordering mismatch |
| Q17 | Hard | Incorrect JOIN path and column reference |
| Q18 | Hard | Incorrect month output format |

### Key Observations

1. The model sometimes references columns from the wrong tables.
2. JOIN generation becomes less reliable for multi-table questions.
3. The model can identify the correct records but may omit the required ordering.
4. Aggregation and date formatting require further improvement.

### Question 16 — Additional Observation

The generated query returned exactly the same 32 customers as the reference query. However, the generated query did not include `ORDER BY`, so the result order differed.

This was classified as incorrect by the current evaluation procedure.

## 5. Conclusion

The baseline achieved 75% overall accuracy and an 85% execution rate on the 20-question evaluation dataset.

The primary weaknesses identified were schema understanding, JOIN generation, and output formatting.

These findings motivate the next experimental phase: implementing Schema RAG to retrieve relevant tables, columns, and relationships instead of providing the complete database schema for every question.

## 6. Next Phase

**Week 2 — Schema Retrieval Augmented Generation**

- Build schema descriptions and embeddings.
- Retrieve relevant tables and columns based on the user question.
- Include relevant foreign-key relationships.
- Compare the RAG-based approach against the Week 1 baseline.
- Measure accuracy, execution rate, and prompt size.
## 7. Revised Baseline — Question Set v2

The evaluation dataset was revised to correct two inconsistencies:

- Q16: Removed an unrequested sorting requirement from the reference SQL.
- Q18: Explicitly specified the expected two-digit month format (01–12).

The model and generation configuration were kept unchanged.

### Results

| Metric | Result |
|---|---:|
| Total questions | 20 |
| Successfully executed | 17 |
| Execution rate | 85.00% |
| Correct answers | 17 |
| Overall accuracy | 85.00% |

### Difficulty-wise Performance

| Difficulty | Correct | Accuracy |
|---|---:|---:|
| Easy | 6/6 | 100.00% |
| Medium | 6/8 | 75.00% |
| Hard | 5/6 | 83.33% |

**Observation:** Easy questions achieved 100% accuracy. Medium questions remain the weakest category at 75%. The system still has three execution failures, indicating that SQL generation and schema understanding need improvement.

Question set v2: Removed an unrequested ORDER BY from Q16 and specified the month format in Q18.

This revised evaluation is the official Week 1 baseline. The original v1 results are retained for historical comparison.