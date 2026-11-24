from dotenv import load_dotenv
from pathlib import Path
import os
from groq import Groq

load_dotenv(Path(__file__).parent / ".env")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "You are an expert problem solver and assistant. "
    "The user will give you a question or problem captured from their screen.\n\n"
    "ABSOLUTE RULES:\n"
    "1. DETECT the question type first, then respond accordingly:\n"
    "   - CODING/DSA problem -> Output ONLY the C++ solution in a single fenced code block. Zero comments. No text before or after.\n"
    "   - MCQ / Multiple Choice -> Output ONLY the correct option letter and its text. Nothing else.\n"
    "   - Fill-in-the-blank / short-answer -> Output ONLY the direct answer word or phrase.\n"
    "   - Descriptive / conceptual -> Output ONLY a concise direct answer.\n"
    "   - True/False -> Output ONLY True or False.\n"
    "   - Math/numerical -> Output ONLY the final result.\n"
    "2. NEVER repeat or restate the question.\n"
    "3. ZERO preamble, ZERO post-explanation unless steps are needed.\n"
    "4. For coding: zero // comments, zero /* */ comments inside the code block."
)

questions = [
    # ── SDE ──────────────────────────────────────────────────────────
    {
        "id": 1,
        "cat": "SDE",
        "type": "Coding - Two Sum",
        "q": (
            "Given an array of integers nums and an integer target, return indices of the two numbers "
            "such that they add up to target. Assume exactly one solution exists.\n"
            "class Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n    }\n};"
        ),
        "expected_keywords": ["unordered_map", "map", "find"],
        "expected_hint": "hash map approach",
    },
    {
        "id": 2,
        "cat": "SDE",
        "type": "MCQ - Time Complexity",
        "q": "What is the time complexity of binary search?\nA) O(n)\nB) O(log n)\nC) O(n log n)\nD) O(1)",
        "expected_keywords": ["b", "log n"],
        "expected_hint": "B) O(log n)",
    },
    {
        "id": 3,
        "cat": "SDE",
        "type": "True/False - Stack",
        "q": "A stack follows LIFO (Last In First Out) principle. True or False?",
        "expected_keywords": ["true"],
        "expected_hint": "True",
    },
    {
        "id": 4,
        "cat": "SDE",
        "type": "MCQ - OS Scheduling",
        "q": (
            "Which scheduling algorithm gives minimum average waiting time?\n"
            "A) FCFS\nB) Round Robin\nC) SJF (Shortest Job First)\nD) Priority Scheduling"
        ),
        "expected_keywords": ["c", "sjf", "shortest"],
        "expected_hint": "C) SJF",
    },
    {
        "id": 5,
        "cat": "SDE",
        "type": "Fill-in-blank - Serialization",
        "q": "The process of converting an object into a byte stream for storage or transmission is called ___.",
        "expected_keywords": ["serial"],
        "expected_hint": "Serialization",
    },
    {
        "id": 6,
        "cat": "SDE",
        "type": "MCQ - DB Normalization",
        "q": (
            "Which normal form eliminates transitive dependency?\n"
            "A) 1NF\nB) 2NF\nC) 3NF\nD) BCNF"
        ),
        "expected_keywords": ["c", "3nf", "third"],
        "expected_hint": "C) 3NF",
    },
    {
        "id": 7,
        "cat": "SDE",
        "type": "Short Answer - Deadlock",
        "q": "What are the four necessary conditions for a deadlock to occur?",
        "expected_keywords": ["mutual exclusion", "hold", "circular"],
        "expected_hint": "Mutual exclusion, Hold and wait, No preemption, Circular wait",
    },
    # ── Data Science ──────────────────────────────────────────────────
    {
        "id": 8,
        "cat": "Data Science",
        "type": "MCQ - Classification",
        "q": (
            "Which algorithm is used for classification?\n"
            "A) Linear Regression\nB) K-Means Clustering\nC) Random Forest\nD) PCA"
        ),
        "expected_keywords": ["c", "random forest"],
        "expected_hint": "C) Random Forest",
    },
    {
        "id": 9,
        "cat": "Data Science",
        "type": "Short Answer - Overfitting",
        "q": "What does overfitting mean in machine learning?",
        "expected_keywords": ["train", "test", "generaliz", "unseen"],
        "expected_hint": "model performs well on training but poorly on unseen/test data",
    },
    {
        "id": 10,
        "cat": "Data Science",
        "type": "Numerical - Mean",
        "q": "Calculate the mean of: 4, 8, 15, 16, 23, 42",
        "expected_keywords": ["18"],
        "expected_hint": "18",
    },
    {
        "id": 11,
        "cat": "Data Science",
        "type": "MCQ - Outliers",
        "q": (
            "Which measure of central tendency is most affected by outliers?\n"
            "A) Mean\nB) Median\nC) Mode\nD) None"
        ),
        "expected_keywords": ["a", "mean"],
        "expected_hint": "A) Mean",
    },
    {
        "id": 12,
        "cat": "Data Science",
        "type": "True/False - Gradient Descent",
        "q": "Gradient descent always converges to the global minimum. True or False?",
        "expected_keywords": ["false"],
        "expected_hint": "False",
    },
    {
        "id": 13,
        "cat": "Data Science",
        "type": "MCQ - Bias-Variance",
        "q": (
            "A model with high bias and low variance is said to be:\n"
            "A) Overfitting\nB) Underfitting\nC) Well-fitted\nD) None of the above"
        ),
        "expected_keywords": ["b", "underfitting", "underfit"],
        "expected_hint": "B) Underfitting",
    },
    {
        "id": 14,
        "cat": "Data Science",
        "type": "Short Answer - P-value",
        "q": "What is a p-value in hypothesis testing?",
        "expected_keywords": ["null", "probabilit", "hypothesis"],
        "expected_hint": "probability of obtaining test results at least as extreme as observed, assuming null hypothesis is true",
    },
    {
        "id": 15,
        "cat": "Data Science",
        "type": "MCQ - Missing Values",
        "q": (
            "Which technique is best for handling missing values in a dataset?\n"
            "A) Delete rows with missing values\n"
            "B) Replace with mean/median/mode\n"
            "C) Use imputation techniques\n"
            "D) Both B and C"
        ),
        "expected_keywords": ["d", "both", "b and c", "imputation"],
        "expected_hint": "D) Both B and C",
    },
]


def check(answer: str, keywords: list[str]) -> bool:
    ans_low = answer.lower()
    return any(kw.lower() in ans_low for kw in keywords)


print(f"\nModel : {GROQ_MODEL}")
print(f"Total : {len(questions)} questions  (SDE + Data Science)")
print("=" * 72)

correct = 0
sde_c, sde_t = 0, 0
ds_c, ds_t = 0, 0

for q in questions:
    prompt = (
        f"<screen_problem>\n{q['q']}\n</screen_problem>\n\n"
        "Detect the question type and respond with ONLY the answer "
        "(no preamble, no restating the question, no explanation unless required)."
    )
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
        temperature=0.2,
    )
    answer = resp.choices[0].message.content.strip()
    ok = check(answer, q["expected_keywords"])

    if ok:
        correct += 1
    if q["cat"] == "SDE":
        sde_t += 1
        if ok:
            sde_c += 1
    else:
        ds_t += 1
        if ok:
            ds_c += 1

    status = "[PASS]" if ok else "[FAIL]"
    print(f'{status} [{q["id"]:02d}] [{q["cat"]}] {q["type"]}')
    print(f'     Expected : {q["expected_hint"]}')
    display = answer if len(answer) < 120 else answer[:117] + "..."
    print(f'     Got      : {display}')
    print()

print("=" * 72)
print(f"  SDE Score          : {sde_c}/{sde_t}  ({int(sde_c/sde_t*100)}%)")
print(f"  Data Science Score : {ds_c}/{ds_t}  ({int(ds_c/ds_t*100)}%)")
print(f"  OVERALL            : {correct}/{len(questions)}  ({int(correct/len(questions)*100)}%)")
print("=" * 72)
