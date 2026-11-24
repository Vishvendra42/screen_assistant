import os, base64, time
from dotenv import load_dotenv
from pathlib import Path
from groq import Groq

load_dotenv(Path(__file__).parent / ".env")
MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=API_KEY)

SYSTEM_PROMPT = (
    "You are an expert problem solver and assistant.\n\n"
    "ABSOLUTE RULES:\n"
    "1. For CODING/DSA: output ONLY the optimal complete solution code block with zero comments and no preamble/explanation.\n"
    "2. For SQL: output ONLY the optimal complete SQL query or option letter and text. No explanation.\n"
    "3. For MCQ (Aptitude, Logic, CS): output ONLY the correct option letter and text (e.g. B) 24). No preamble.\n"
    "4. For Numerical/Math: output ONLY the final answer.\n"
    "5. ZERO preamble, ZERO explanation, NEVER repeat the question."
)

tests = [
    # ── SQL ──────────────────────────────────────────────────────────
    {
        "id": 1,
        "cat": "SQL",
        "type": "Second Highest Salary",
        "q": (
            "Write an SQL query to find the second highest salary from the Employee table.\n"
            "Table: Employee (id INT, salary INT)"
        ),
        "expected": ["LIMIT 1 OFFSET 1", "OFFSET", "DENSE_RANK", "MAX(salary)"],
        "hint": "SELECT MAX(salary) FROM Employee WHERE salary < ... OR LIMIT 1 OFFSET 1",
    },
    {
        "id": 2,
        "cat": "SQL",
        "type": "MCQ - Indexing",
        "q": (
            "Which type of index is most suitable for range queries (e.g., WHERE age BETWEEN 20 AND 30)?\n"
            "A) Hash Index\n"
            "B) B-Tree Index\n"
            "C) Bitmap Index\n"
            "D) Full-Text Index"
        ),
        "expected": ["B", "B-Tree"],
        "hint": "B) B-Tree Index",
    },
    {
        "id": 3,
        "cat": "SQL",
        "type": "MCQ - Window Functions",
        "q": (
            "Which window function assigns a rank to each row with no gaps in ranking values?\n"
            "A) RANK()\n"
            "B) DENSE_RANK()\n"
            "C) ROW_NUMBER()\n"
            "D) NTILE()"
        ),
        "expected": ["B", "DENSE_RANK"],
        "hint": "B) DENSE_RANK()",
    },
    # ── Aptitude & Math ──────────────────────────────────────────────
    {
        "id": 4,
        "cat": "Aptitude",
        "type": "Time and Work",
        "q": (
            "A can complete a work in 12 days and B in 24 days. "
            "If they work together, in how many days will they finish the work?\n"
            "A) 6 days\n"
            "B) 8 days\n"
            "C) 10 days\n"
            "D) 16 days"
        ),
        "expected": ["B", "8"],
        "hint": "B) 8 days",
    },
    {
        "id": 5,
        "cat": "Aptitude",
        "type": "Speed and Distance",
        "q": (
            "A train 150 meters long passes a pole in 15 seconds. What is the speed of the train in km/h?\n"
            "A) 36 km/h\n"
            "B) 45 km/h\n"
            "C) 54 km/h\n"
            "D) 72 km/h"
        ),
        "expected": ["A", "36"],
        "hint": "A) 36 km/h",
    },
    {
        "id": 6,
        "cat": "Aptitude",
        "type": "Probability",
        "q": (
            "Two dice are thrown simultaneously. What is the probability of getting a sum of 7?\n"
            "A) 1/6\n"
            "B) 1/12\n"
            "C) 7/36\n"
            "D) 5/36"
        ),
        "expected": ["A", "1/6"],
        "hint": "A) 1/6",
    },
    {
        "id": 7,
        "cat": "Aptitude",
        "type": "Permutations",
        "q": (
            "In how many different ways can the letters of the word 'LEADER' be arranged?\n"
            "A) 720\n"
            "B) 360\n"
            "C) 120\n"
            "D) 48"
        ),
        "expected": ["B", "360"],
        "hint": "B) 360 (6! / 2! = 360)",
    },
    # ── Logical Reasoning ────────────────────────────────────────────
    {
        "id": 8,
        "cat": "Logical Reasoning",
        "type": "Number Series",
        "q": (
            "Find the next number in the series: 2, 6, 12, 20, 30, ?\n"
            "A) 40\n"
            "B) 42\n"
            "C) 44\n"
            "D) 46"
        ),
        "expected": ["B", "42"],
        "hint": "B) 42 (n*(n+1))",
    },
    {
        "id": 9,
        "cat": "Logical Reasoning",
        "type": "Coding Decoding",
        "q": (
            "In a certain code, 'COMPUTER' is written as 'RFUVQNPC'. "
            "How is 'MEDICINE' written in that code?\n"
            "A) EOJDJEFM\n"
            "B) EOJDEJFM\n"
            "C) MFEJDJOE\n"
            "D) MFEDJJOE"
        ),
        "expected": ["A", "EOJDJEFM"],
        "hint": "A) EOJDJEFM",
    },
    # ── DSA (Hard) ───────────────────────────────────────────────────
    {
        "id": 10,
        "cat": "DSA",
        "type": "Invert Binary Tree (C++)",
        "q": (
            "Given the root of a binary tree, invert the tree, and return its root.\n"
            "struct TreeNode { int val; TreeNode *left; TreeNode *right; };\n"
            "class Solution { public: TreeNode* invertTree(TreeNode* root) { } };"
        ),
        "expected": ["swap", "invertTree", "left", "right"],
        "hint": "swap(root->left, root->right) and recurse",
    },
    {
        "id": 11,
        "cat": "DSA",
        "type": "Detect Cycle in Directed Graph",
        "q": (
            "Which algorithm can detect a cycle in a directed graph in O(V + E) time?\n"
            "A) Dijkstra's Algorithm\n"
            "B) DFS with recursion stack / Kahn's Topological Sort\n"
            "C) Kruskal's Algorithm\n"
            "D) Prim's Algorithm"
        ),
        "expected": ["B", "DFS", "Kahn", "Topological"],
        "hint": "B) DFS / Kahn's",
    },
]

print(f"\n========================================================================")
print(f"BENCHMARK: SQL, Quantitative Aptitude, Logical Reasoning, DSA")
print(f"Model: {MODEL}")
print(f"========================================================================\n")

passed = 0
cat_scores = {}

for t in tests:
    cat = t["cat"]
    if cat not in cat_scores:
        cat_scores[cat] = [0, 0]
    cat_scores[cat][1] += 1

    prompt = (
        f"<screen_problem>\n{t['q']}\n</screen_problem>\n\n"
        "Detect the question type and respond with ONLY the direct answer. "
        "No preamble, no explanation, no restating the question."
    )
    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
        temperature=0.1,
    )
    duration = round(time.time() - t0, 2)
    ans = resp.choices[0].message.content.strip()

    ok = any(e.lower() in ans.lower() for e in t["expected"])
    if ok:
        passed += 1
        cat_scores[cat][0] += 1

    status = "[PASS]" if ok else "[FAIL]"
    print(f"{status} [{t['id']:02d}] [{cat}] {t['type']} ({duration}s)")
    print(f"     Expected: {t['hint']}")
    disp = ans if len(ans) < 110 else ans[:107] + "..."
    disp = disp.replace("\n", " ")
    print(f"     Got     : {disp}")
    print()

print("=" * 72)
for cat, (c, tot) in cat_scores.items():
    pct = int(c / tot * 100)
    print(f"  {cat:<20} : {c}/{tot} ({pct}%)")
print("-" * 72)
total_pct = int(passed / len(tests) * 100)
print(f"  OVERALL SCORE        : {passed}/{len(tests)} ({total_pct}%)")
print("=" * 72)
