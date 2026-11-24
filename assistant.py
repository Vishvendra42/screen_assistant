"""
  Screen Assistant - Screen Problem Solver (C++ Edition)
A stealth always-on-top overlay that captures and solves coding problems
directly from your screen (LeetCode, Notepad, Zoom/Meet screen shares, etc.)
using the Groq API (Qwen 2.5 / 3 27B).

Hotkeys:
  / + S  or  F9  : Solve on-screen problem immediately (Vision AI / LeetCode)
  / + Z  or  F10 : Show / hide overlay
  / + 1          : Show overlay / bring to front
  / + D  or  F11 : Append next page to current question context
  / + C          : Solve copied clipboard text
  / + Q          : Quit application
"""
import os
import re
import sys
import time
import json
import queue
import atexit
import ctypes
import warnings
from ctypes import wintypes
from pathlib import Path
import threading
import tkinter as tk

warnings.filterwarnings("ignore", category=DeprecationWarning)

if sys.platform != "win32":
    raise SystemExit("Screen Assistant is configured for Windows. Please run on Windows.")

# When running as a compiled .exe (PyInstaller), store data files
# next to the .exe, not inside the temp extraction folder.
if getattr(sys, "frozen", False):
    SCRIPT_DIR = Path(sys.executable).resolve().parent
else:
    SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / ".drv.log"        # innocuous log name
PID_FILE = SCRIPT_DIR / ".drv.pid"

# Direct stdout/stderr to log when running in pythonw background mode
if sys.stdout is None or sys.stderr is None:
    _log = open(LOG_FILE, "a", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = _log
    sys.stderr = _log
else:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except Exception:
            pass

IS_BACKGROUND = os.path.basename(sys.executable).lower() == "pythonw.exe"


def fatal(msg):
    print(f"\n[FATAL] {msg}\n", file=sys.stderr)
    if IS_BACKGROUND:
        ctypes.windll.user32.MessageBoxW(None, msg, "Screen Assistant", 0x10)
    raise SystemExit(1)


# â”€â”€ Single Instance (Named Mutex + Show Event) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.OpenEventW.restype = wintypes.HANDLE
_kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.SetEvent.restype = wintypes.BOOL
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

_mutex = _kernel32.CreateMutexW(None, False, "Local\\ScreenAssistantWindowsApp")
if ctypes.get_last_error() == 183:
    # Already running: signal existing instance to show itself immediately
    _evt = _kernel32.OpenEventW(0x0002, False, "Local\\WDAShowEvent")  # EVENT_MODIFY_STATE
    if _evt:
        _kernel32.SetEvent(_evt)
        _kernel32.CloseHandle(_evt)
    raise SystemExit(0)

_show_event = _kernel32.CreateEventW(None, False, False, "Local\\WDAShowEvent")

try:
    PID_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))
except Exception:
    pass

# â”€â”€ DPI Awareness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# â”€â”€ Dependencies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    from groq import Groq
except ImportError:
    fatal("Missing dependency: pip install groq")

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
WINDOW_TITLE         = "System Diagnostics"    # shown nowhere visible (overrideredirect=True)
PREFERRED_LANGUAGE   = "C++"
MAX_CONTEXT_CHARS    = 14000
HIDE_FROM_SCREEN_SHARE = True

UI_FONT   = "Segoe UI"
CODE_FONT = "Consolas"

# Palette
PANEL   = "#1c1c1e"
FIELD   = "#2c2c2e"
BORDER  = "#3a3a3c"
TEXT    = "#ececf0"
MUTED   = "#8e8e93"
ACCENT  = "#0a84ff"
CODE_BG = "#0e0e10"
CODE_FG = "#d7e3ff"
ERROR   = "#ff6b6b"
SUCCESS = "#30d158"
KEY_COLOR = "#010101"

CDP_PORT = int(os.getenv("SCREEN_CDP_PORT", "9222"))
OCR_LANG = os.getenv("SCREEN_OCR_LANG", "en")

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

CHROMIUM_EXES = {"chrome.exe", "msedge.exe", "brave.exe", "vivaldi.exe", "opera.exe", "arc.exe"}
BROWSER_EXES  = CHROMIUM_EXES | {"firefox.exe"}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 1. Model Init â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
load_dotenv(SCRIPT_DIR / ".env")

AI_PROVIDER       = os.getenv("AI_PROVIDER", "gemini").lower()
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GROQ_MODEL        = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
GROQ_MAX_TOKENS   = int(os.getenv("GROQ_MAX_TOKENS", "4096"))
GROQ_TEMPERATURE  = float(os.getenv("GROQ_TEMPERATURE", "0.1"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = None
if GROQ_API_KEY and GROQ_API_KEY not in ("your_groq_api_key_here", "gsk_your_key_here"):
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as _e:
        print(f"[groq init error] {_e}")

if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
    fatal("No Gemini API key found in .env (GEMINI_API_KEY=...)")

CURRENT_MODE = os.getenv("DEFAULT_ENGINE_MODE", "hybrid").lower()  # "hybrid" or "gemini"
print(f"Initial AI Mode: {CURRENT_MODE.upper()} (Language: {PREFERRED_LANGUAGE})")

def call_groq_hybrid_pipeline(all_images: list[str], combined_text: str, instruction: str) -> str:
    """
    Groq Hybrid Pipeline:
    Step 1: Uses fast Qwen 27B Vision to visually read and transcribe all tables, diagrams, and text.
    Step 2: Feeds the clean structured problem to GPT-OSS 120B with deep reasoning for optimal solution.
    Total latency: ~1.5s - 2.0s.
    """
    if not groq_client:
        raise RuntimeError("Groq client not initialized (check GROQ_API_KEY in .env)")

    # Step 1: Vision Extraction
    if all_images:
        vision_parts = [{"type": "text", "text": "Transcribe verbatim the complete question, code/table/diagram context, and all options visible in the main problem area. Ignore browser chrome."}]
        for idx, img in enumerate(all_images):
            vision_parts.append({"type": "text", "text": f"--- Page {idx + 1} Image ---"})
            vision_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})

        v_resp = groq_client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[{"role": "user", "content": vision_parts}],
            max_tokens=600,
            temperature=0.0
        )
        extracted_problem = v_resp.choices[0].message.content.strip()
    else:
        extracted_problem = combined_text

    # Step 2: Reasoning & Solving via GPT-OSS 120B
    solver_prompt = f"{SYSTEM_PROMPT}\n\nProblem statement:\n{extracted_problem}\n\nInstructions:\n{instruction}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": solver_prompt}
    ]

    s_resp = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        max_tokens=1500,
        temperature=0.1
    )
    choice = s_resp.choices[0].message
    content = choice.content or ""
    if not content.strip() and choice.reasoning:
        # If output was captured in reasoning, extract the concluding answer
        content = choice.reasoning.strip().splitlines()[-1]
    return content.strip()

def call_gemini_vision(images: list[str] | str, text_prompt: str) -> str:
    """
    Calls Google Gemini with automatic model fallback if 3.8-flash is busy.
    Supports single image, multiple images (multi-page question), and pure text.
    """
    import requests
    models_to_try = [GEMINI_MODEL, "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
    parts = [{"text": text_prompt}]
    
    if isinstance(images, str) and images:
        images = [images]
    elif not isinstance(images, list):
        images = []
        
    for idx, img in enumerate(images):
        if img:
            parts.append({"text": f"--- Page {idx + 1} Image ---"})
            parts.append({"inline_data": {"mime_type": "image/png", "data": img}})
    
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 2048
        }
    }
    
    last_err = ""
    for m in models_to_try:
        if not m:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_API_KEY}"
        try:
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code == 200:
                data = r.json()
                cand = data.get("candidates", [])
                if cand:
                    parts_out = cand[0].get("content", {}).get("parts", [])
                    if parts_out:
                        return parts_out[0].get("text", "").strip()
            else:
                last_err = f"{m} HTTP {r.status_code}: {r.text[:150]}"
                print(f"[gemini fallback] {last_err}, trying next...")
        except Exception as ex:
            last_err = f"{m} exception: {ex}"
            print(f"[gemini fallback] {last_err}, trying next...")
    raise RuntimeError(f"All Gemini models failed: {last_err}")

SYSTEM_PROMPT = f"""You are an expert problem solver and assistant. The user provides text captured via OCR or API directly from their screen (e.g. online assessment, browser, IDE, exam, or LeetCode).

ABSOLUTE RULES â€” follow every rule without exception:
1. OCR NOISE & ACTIVE QUESTION DETECTION:
   - The captured text may include browser chrome, tabs, URLs, navigation buttons, question counters, running scores, or previous chat history.
   - Always focus on the CURRENT / ACTIVE question (typically the latest question presented at the bottom or the main prompt).
2. DETECT THE QUESTION TYPE AND ANSWER ACCORDINGLY:
   - CODING / PROGRAMMING / DSA PROBLEM:
     * Output ONLY the complete, optimal, bug-free solution code inside a single markdown code block (e.g. ```cpp ... ```).
     * Follow any language explicitly requested in the problem (default to {PREFERRED_LANGUAGE} if none specified).
     * Zero comments (// or /* */) inside the code block.
     * ZERO preamble, zero explanation, zero complexity analysis, zero notes before or after the code block.
     * The code must be 100% complete, compilable, and directly submittable (include necessary headers/includes).
   - MCQ (MULTIPLE CHOICE QUESTION):
     * Output ONLY the correct option letter and the option text (e.g. "B) O(log n)" or "A) SELECT MAX(Salary)...").
     * ZERO preamble, zero explanation, no "The correct answer is:", nothing else.
   - TRUE / FALSE:
     * Output ONLY "True" or "False".
   - FILL-IN-THE-BLANK / SHORT-ANSWER:
     * Output ONLY the direct answer word or phrase. No full sentences.
   - DESCRIPTIVE / CONCEPTUAL / THEORY:
     * Output ONLY a concise, direct, high-scoring answer. No filler.
   - NUMERICAL / MATH:
     * Output ONLY the final numeric result (or step-by-step only if specifically requested).
3. NEVER repeat, restate, or quote the question in your response.
4. ZERO preamble and ZERO post-explanation for coding and MCQ questions."""

# Accumulator for multi-page question text (Ctrl+Alt+D appends more pages)
pending_problem_parts: list[str] = []

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 2. Win32 Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
user32   = ctypes.windll.user32
kernel32 = _kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def _pid_of_hwnd(hwnd):
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _exe_of_pid(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)
    return ""


def _window_title(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


state = {
    "front_app":        "",
    "front_hwnd":       0,
    "busy":             False,
    "last_code":        "",
    "pending_pages":    [],   # accumulated text pages
        "pending_images":   [],   # accumulated base64 screenshot images for multi-page vision
    "last_capture_img": "",
    "last_ocr_text":    "",
}


def remember_front_app():
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return
        pid = _pid_of_hwnd(hwnd)
        if pid == os.getpid():
            return
        state["front_hwnd"] = int(hwnd)
        exe = _exe_of_pid(pid)
        if exe:
            state["front_app"] = exe
    except Exception:
        pass


def remember_specific_hwnd(hwnd):
    try:
        if not hwnd:
            return
        pid = _pid_of_hwnd(hwnd)
        if pid == os.getpid():
            return
        state["front_hwnd"] = int(hwnd)
        exe = _exe_of_pid(pid)
        if exe:
            state["front_app"] = exe
    except Exception:
        pass


def poll_front_app():
    remember_front_app()
    root.after(400, poll_front_app)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 3. LeetCode GraphQL & Web Scraper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
LEETCODE_QUERY = """
query getQuestion($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    title
    difficulty
    content
    exampleTestcases
    topicTags { name }
    codeSnippets { langSlug code }
  }
}
"""


def _lc_slug_from_url(url):
    m = re.search(r"leetcode\.com/problems/([^/?#]+)", url)
    return m.group(1) if m else None


def fetch_leetcode_graphql(url):
    if not HAS_REQUESTS:
        return ""
    slug = _lc_slug_from_url(url)
    if not slug:
        return ""
    try:
        resp = requests.post(
            LEETCODE_GRAPHQL,
            json={"query": LEETCODE_QUERY, "variables": {"titleSlug": slug}},
            headers={
                **SCRAPE_HEADERS,
                "Content-Type": "application/json",
                "Referer": f"https://leetcode.com/problems/{slug}/",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {}).get("question")
        if not data:
            return ""
        soup = BeautifulSoup(data.get("content", "") or "", "html.parser")
        problem_text = soup.get_text(separator="\n", strip=True)
        tags = ", ".join(t["name"] for t in (data.get("topicTags") or []))
        snippets = data.get("codeSnippets") or []
        code_stub = ""
        # Prioritize C++ starter code snippet
        for s in snippets:
            if s.get("langSlug") in ("cpp", "c++"):
                code_stub = s.get("code", "")
                break
        if not code_stub and snippets:
            code_stub = snippets[0].get("code", "")
        parts = [
            f"LeetCode Problem: {data.get('title', slug)}",
            f"Difficulty: {data.get('difficulty', 'Unknown')}",
            f"Tags: {tags}" if tags else "",
            "",
            "Problem Statement:",
            problem_text,
            "",
            "Example Test Cases:",
            data.get("exampleTestcases", "") or "",
            "",
            f"Starter Code ({PREFERRED_LANGUAGE}):",
            code_stub,
        ]
        return "\n".join(p for p in parts if p is not None)
    except Exception as e:
        print(f"[leetcode graphql] {e}")
        return ""


def _uia_address_bar(hwnd):
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            win = auto.ControlFromHandle(hwnd)
            if not win:
                return None
            edit = auto.EditControl(
                searchFromControl=win, searchDepth=16,
                Compare=lambda c, _depth: "address" in (c.Name or "").lower() or "adresse" in (c.Name or "").lower()
            )
            if not edit.Exists(1, 0.2):
                return None
            val = edit.GetValuePattern().Value
            if val and "://" not in val and "." in val:
                val = "https://" + val
            return val
    except Exception:
        return None


def fetch_browser_url(app_name, hwnd):
    if app_name not in BROWSER_EXES:
        return None
    try:
        r = requests.get(f"http://127.0.0.1:{CDP_PORT}/json", timeout=0.8)
        tabs = [t for t in r.json() if t.get("type") == "page" and str(t.get("url", "")).startswith("http")]
        if tabs:
            return tabs[0]["url"]
    except Exception:
        pass
    if hwnd:
        return _uia_address_bar(hwnd)
    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 4. Screen OCR Engine (winocr) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CAPTURES_DIR = SCRIPT_DIR / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

DEBUG_CAPTURE_FILE = SCRIPT_DIR / "debug_last_capture.png"
DEBUG_OCR_FILE     = SCRIPT_DIR / "debug_last_ocr.txt"
DEBUG_PROMPT_FILE  = SCRIPT_DIR / "debug_last_prompt.txt"
DEBUG_SESSION_FILE = SCRIPT_DIR / "debug_last_session.json"


def _grab_screen_of_window(hwnd):
    bbox = None
    if hwnd and not user32.IsIconic(hwnd):
        r = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(r)):
            vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
            vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
            left, top = max(r.left, vx), max(r.top, vy)
            right, bottom = min(r.right, vx + vw), min(r.bottom, vy + vh)
            if right - left > 80 and bottom - top > 80:
                bbox = (left, top, right, bottom)
    try:
        return ImageGrab.grab(bbox=bbox, all_screens=True)
    except Exception as e:
        print(f"[grab window failed] {e}, grabbing full screen...")
        return ImageGrab.grab(bbox=None, all_screens=True)


def ocr_screen(hwnd):
    if not HAS_PIL:
        return ""
    img = None
    try:
        img = _grab_screen_of_window(hwnd)
    except Exception as e:
        print(f"[screenshot failed] {e}")
        try:
            img = ImageGrab.grab(bbox=None, all_screens=True)
        except Exception as e2:
            print(f"[full screenshot fallback failed] {e2}")
            return ""

    ts = time.strftime("%Y%m%d_%H%M%S")
    img_path = CAPTURES_DIR / f"capture_{ts}.png"

    if img is not None:
        try:
            img.save(DEBUG_CAPTURE_FILE)
            img.save(img_path)
            state["last_capture_img"] = str(img_path)
        except Exception:
            pass

    text = ""
    if HAS_WINOCR and img is not None:
        try:
            res = winocr.recognize_pil_sync(img, OCR_LANG)
            # Reconstruct lines preserving line breaks so code indentation & MCQ options are clear
            if isinstance(res, dict) and "lines" in res:
                raw_lines = [l.get("text", "").strip() for l in res["lines"] if l.get("text", "").strip()]
                text = "\n".join(raw_lines)
            elif hasattr(res, "lines"):
                raw_lines = [getattr(l, "text", "").strip() for l in res.lines if getattr(l, "text", "").strip()]
                text = "\n".join(raw_lines)
            else:
                text = res.get("text", "") if isinstance(res, dict) else str(res)
        except Exception as e:
            print(f"[winocr error] {e}")

    # Fallback to pytesseract if winocr produced nothing
    if not text.strip():
        try:
            import pytesseract
            text = pytesseract.image_to_string(img).strip()
        except Exception:
            pass

    # If the window grab gave very little text (< 25 chars), try a full screen grab as fallback
    if len(text.strip()) < 25 and HAS_WINOCR:
        try:
            print("[ocr_screen] Low text from window capture, falling back to full screen...")
            full_img = ImageGrab.grab(bbox=None, all_screens=True)
            full_res = winocr.recognize_pil_sync(full_img, OCR_LANG)
            if isinstance(full_res, dict) and "lines" in full_res:
                raw_lines = [l.get("text", "").strip() for l in full_res["lines"] if l.get("text", "").strip()]
                full_text = "\n".join(raw_lines)
            elif hasattr(full_res, "lines"):
                raw_lines = [getattr(l, "text", "").strip() for l in full_res.lines if getattr(l, "text", "").strip()]
                full_text = "\n".join(raw_lines)
            else:
                full_text = full_res.get("text", "") if isinstance(full_res, dict) else str(full_res)

            if len(full_text.strip()) > len(text.strip()):
                text = full_text
                try:
                    full_img.save(DEBUG_CAPTURE_FILE)
                    full_img.save(img_path)
                    state["last_capture_img"] = str(img_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"[ocr_screen full fallback error] {e}")

    result_text = text.strip()

    # Save raw OCR text for user inspection & optimization
    try:
        ocr_path = CAPTURES_DIR / f"ocr_{ts}.txt"
        ocr_path.write_text(result_text, encoding="utf-8", errors="replace")
        DEBUG_OCR_FILE.write_text(result_text, encoding="utf-8", errors="replace")
        state["last_ocr_text"] = result_text
    except Exception:
        pass

    print(f"[ocr_screen] Captured {len(result_text)} chars ({len(result_text.splitlines())} lines) -> {img_path.name}")
    if result_text:
        preview_sample = result_text[:160].replace("\n", " ")
        print(f"[ocr_screen sample] {preview_sample}")
    return result_text



import base64, io

def grab_screen_as_base64(hwnd=None) -> tuple[str, str]:
    """
    Captures the screen (active window or full screen) and returns
    (base64_png_string, saved_file_path).
    Returns ("", "") if capture fails.
    """
    if not HAS_PIL:
        return "", ""
    img = None
    try:
        img = _grab_screen_of_window(hwnd) if hwnd else ImageGrab.grab(bbox=None, all_screens=True)
    except Exception as e:
        print(f"[vision grab failed] {e}")
        try:
            img = ImageGrab.grab(bbox=None, all_screens=True)
        except Exception as e2:
            print(f"[vision full-screen fallback failed] {e2}")
            return "", ""

    if img is None:
        return "", ""

    ts = time.strftime("%Y%m%d_%H%M%S")
    img_path = CAPTURES_DIR / f"capture_{ts}.png"
    try:
        img.save(DEBUG_CAPTURE_FILE)
        img.save(img_path)
        state["last_capture_img"] = str(img_path)
    except Exception:
        pass

    # Encode to base64
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    print(f"[vision grab] Saved {img_path.name}  ({len(b64)//1024} KB base64)")
    return b64, str(img_path)


def vision_solve(img_b64: str, source_name: str) -> str | None:
    """
    Sends the screenshot directly to the Groq vision model.
    Returns the model's raw text response, or None on failure.
    """
    if not img_b64:
        return None
    try:
        instruction = (
            "Look at this screenshot carefully. Identify the question/problem in the main content area "
            "(ignore browser UI, sidebars, tabs). "
            "Detect the question type and respond with ONLY the direct answer. "
            "If coding/DSA: output ONLY the complete solution code block with zero comments. "
            "If MCQ/SQL/Aptitude: output ONLY the correct option letter and text. "
            "No preamble, no explanation, no restating the question."
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}"
                        },
                    },
                ],
            },
        ]
        response = groq_client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=messages,
            max_tokens=GROQ_MAX_TOKENS,
            temperature=GROQ_TEMPERATURE,
            stream=False,
        )
        answer = response.choices[0].message.content or ""
        print(f"[vision_solve] Got {len(answer)} chars from {GROQ_VISION_MODEL}")
        return answer.strip() if answer.strip() else None
    except Exception as e:
        print(f"[vision_solve error] {e}")
        return None

def capture_screen_problem():
    """
    Intelligently retrieves the coding or MCQ problem from the active window:
    1. If on LeetCode in a browser -> gets GraphQL problem statement & C++ stubs.
    2. Vision LLM: captures screenshot and sends directly to Llama-4-Maverick vision model.
    3. OCR fallback: if vision fails, runs Windows Media OCR as backup.
    """
    app = state.get("front_app", "")
    hwnd = state.get("front_hwnd", 0)

    # 1. Check if browser has LeetCode open (most accurate source)
    if app in BROWSER_EXES:
        url = fetch_browser_url(app, hwnd)
        if url and "leetcode.com/problems/" in url:
            lc_text = fetch_leetcode_graphql(url)
            if lc_text:
                return lc_text, "LeetCode GraphQL API"

    # 2. Vision capture: grab screenshot and store base64 for vision model
    img_b64, img_path = grab_screen_as_base64(hwnd)
    if img_b64:
        # Store for solve_problem() worker to use in vision API call
        state["vision_img_b64"] = img_b64
        app_label = app if app else "Screen"
        return "__VISION__", f"{app_label} (Vision AI)"

    # 3. OCR fallback if screenshot failed entirely
    state["vision_img_b64"] = ""
    ocr_text = ocr_screen(hwnd)
    if ocr_text and len(ocr_text) > 12:
        app_label = app if app else "Screen"
        return ocr_text, f"{app_label} (Screen OCR)"

    return "", "No text detected on screen"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 5. GUI Setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
root = tk.Tk()
root.title(WINDOW_TITLE)

SC = max(1.0, root.winfo_fpixels("1i") / 96.0)


def S(v):
    return int(round(v * SC))


W, H = S(640), S(460)
root.overrideredirect(True)

# Place in the left bottom corner with lower line touching the bottom of the screen
work_rect = wintypes.RECT()
user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_rect), 0)
screen_h = user32.GetSystemMetrics(1)
bottom_y = work_rect.bottom if (work_rect.bottom and work_rect.bottom > 200) else screen_h
pos_x = 0
pos_y = max(0, bottom_y - H)

root.geometry(f"{W}x{H}+{pos_x}+{pos_y}")
root.minsize(S(400), S(300))
root.attributes("-topmost", True)
TARGET_ALPHA = 0.85
current_alpha = 0.0
root.attributes("-alpha", current_alpha)
root.config(bg=KEY_COLOR)
root.attributes("-transparentcolor", KEY_COLOR)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


def get_overlay_hwnd():
    child = root.winfo_id()
    return user32.GetAncestor(child, 2) or child


def set_click_through(enable: bool):
    try:
        hwnd = get_overlay_hwnd()
        if not hwnd:
            return
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        else:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style & ~WS_EX_TRANSPARENT) | WS_EX_LAYERED)
    except Exception as e:
        print(f"[set_click_through error] {e}")


def is_visible():
    return current_alpha > 0.05


def set_alpha(new_a, from_slider=False):
    global current_alpha, TARGET_ALPHA
    val = max(0.0, min(1.0, round(float(new_a), 2)))
    current_alpha = val
    if current_alpha > 0.1:
        TARGET_ALPHA = current_alpha
    root.attributes("-alpha", current_alpha)
    if current_alpha <= 0.05:
        set_click_through(True)
    else:
        set_click_through(False)
        root.attributes("-topmost", True)
    pct = int(round(current_alpha * 100))
    if "alpha_val_lbl" in globals():
        alpha_val_lbl.config(text=f"{pct}%")
    if not from_slider and "alpha_slider" in globals():
        alpha_slider.set(pct)


def show_window(target_alpha=None):
    if target_alpha is None:
        target_alpha = TARGET_ALPHA
    root.deiconify()
    set_alpha(target_alpha)
    root.lift()
    root.after(60, prompt_entry.focus_force)


def hide_window():
    set_alpha(0.0)


def toggle_window():
    if is_visible():
        hide_window()
    else:
        show_window(TARGET_ALPHA)


def setup_overlay():
    hwnd = get_overlay_hwnd()

    # â”€â”€ 1. Hide from Alt+Tab switcher & Taskbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW  = 0x00040000
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    # â”€â”€ 2. Hide from screen recording & video calls â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if HIDE_FROM_SCREEN_SHARE:
        if not user32.SetWindowDisplayAffinity(hwnd, 0x11):   # WDA_EXCLUDEFROMCAPTURE
            user32.SetWindowDisplayAffinity(hwnd, 0x01)       # WDA_MONITOR fallback

    # â”€â”€ 3. Start transparent & click-through â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    set_click_through(True)


# Rounded glass canvas
bg = tk.Canvas(root, bg=KEY_COLOR, highlightthickness=0, bd=0)
bg.pack(fill=tk.BOTH, expand=True)

PAD_X, PAD_TOP, PAD_BOTTOM = S(18), S(24), S(18)
main = tk.Frame(bg, bg=PANEL)
inner_id = bg.create_window(PAD_X, PAD_TOP, anchor="nw", window=main)


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def redraw_bg(_event=None):
    w, h = bg.winfo_width(), bg.winfo_height()
    bg.delete("rr")
    round_rect(bg, 2, 2, w - 2, h - 2, S(22), fill=PANEL, outline=BORDER, tags="rr")
    bg.tag_lower("rr")
    bg.coords(inner_id, PAD_X, PAD_TOP)
    bg.itemconfigure(inner_id, width=max(100, w - 2 * PAD_X), height=max(100, h - PAD_TOP - PAD_BOTTOM))


bg.bind("<Configure>", redraw_bg)

drag = {"x": 0, "y": 0}


def start_drag(e):
    drag["x"] = e.x_root - root.winfo_x()
    drag["y"] = e.y_root - root.winfo_y()


def do_drag(e):
    root.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")


bg.bind("<ButtonPress-1>", start_drag)
bg.bind("<B1-Motion>", do_drag)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Header Row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
header = tk.Frame(main, bg=PANEL)
header.pack(fill=tk.X, pady=(0, 6))

slider_box = tk.Frame(header, bg=PANEL)
slider_box.pack(side=tk.LEFT, padx=(2, 6))

eye_lbl = tk.Label(slider_box, text="o", font=(UI_FONT, 10), bg=PANEL, fg=MUTED, cursor="hand2")
eye_lbl.pack(side=tk.LEFT, padx=(0, 3))
eye_lbl.bind("<Button-1>", lambda _e: toggle_window())





def on_slider_change(val):
    try:
        set_alpha(int(float(val)) / 100.0, from_slider=True)
    except Exception:
        pass


alpha_slider = tk.Scale(
    slider_box, from_=0, to=100, orient=tk.HORIZONTAL, bg=PANEL, fg=TEXT,
    troughcolor=FIELD, activebackground=ACCENT, highlightthickness=0, bd=0,
    sliderrelief=tk.FLAT, showvalue=0, length=S(85), sliderlength=S(14),
    command=on_slider_change,
)
alpha_slider.set(int(current_alpha * 100))
alpha_slider.pack(side=tk.LEFT, padx=(0, 4))

alpha_val_lbl = tk.Label(slider_box, text=f"{int(current_alpha * 100)}%", font=(UI_FONT, 9),
                         bg=PANEL, fg=MUTED, width=4)
alpha_val_lbl.pack(side=tk.LEFT)


def make_link(text, command):
    lbl = tk.Label(header, text=text, font=(UI_FONT, 10), bg=PANEL, fg=MUTED, cursor="hand2", padx=6)
    lbl.pack(side=tk.RIGHT)
    lbl.bind("<Button-1>", lambda _e: command())
    lbl.bind("<Enter>", lambda _e: lbl.config(fg=TEXT))
    lbl.bind("<Leave>", lambda _e: lbl.config(fg=MUTED))
    return lbl


def clear_chat():
    output.config(state=tk.NORMAL)
    output.delete("1.0", tk.END)
    output.config(state=tk.DISABLED)
    state["last_code"] = ""
    state["pending_pages"] = []
    state["pending_images"] = []   # also discard queued vision images
    set_status("")


def copy_code():
    if not state["last_code"]:
        set_status("No code generated yet")
    else:
        root.clipboard_clear()
        root.clipboard_append(state["last_code"])
        root.update()
        set_status("Code copied to clipboard")
    root.after(1800, lambda: set_status(""))


def open_captures_folder():
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.startfile(CAPTURES_DIR)
        set_status("Opened captures folder")
    except Exception as e:
        set_status(f"Could not open captures: {e}")
    root.after(2000, lambda: set_status(""))


make_link("X", hide_window)
make_link("Clear", clear_chat)
make_link("Copy Code", copy_code)
make_link("Captures", open_captures_folder)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Quick Action Bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
action_bar = tk.Frame(main, bg=PANEL)
action_bar.pack(fill=tk.X, pady=(0, 6))


def make_action_btn(text, cmd, color=ACCENT):
    lbl = tk.Label(action_bar, text=text, font=(UI_FONT, 9, "bold"), bg=FIELD, fg=color,
                   cursor="hand2", padx=8, pady=3)
    lbl.pack(side=tk.LEFT, padx=(0, 6))
    lbl.bind("<Button-1>", lambda _e: cmd())
    return lbl


make_action_btn("Solve Screen  (/+S / F9)", lambda: solve_screen_action(), ACCENT)
make_action_btn("Append  (/+D / F11)", lambda: append_page_action(), "#ff9f0a")
make_action_btn("Clip  (/+C)", lambda: solve_clip_action(), SUCCESS)

lang_lbl = tk.Label(action_bar, text="C++ (Optimal)", font=(UI_FONT, 9, "bold"), bg=FIELD, fg=MUTED, padx=6, pady=3)
lang_lbl.pack(side=tk.RIGHT)

def toggle_ai_mode():
    global CURRENT_MODE
    if CURRENT_MODE == "hybrid":
        CURRENT_MODE = "gemini"
        mode_btn.config(text="Mode: Gemini 3.8", fg="#30d158")
        set_status("Switched to Google Gemini 3.8 Mode")
    else:
        CURRENT_MODE = "hybrid"
        mode_btn.config(text="Mode: Hybrid (Groq 120B)", fg=ACCENT)
        set_status("Switched to Fast Hybrid Mode (Qwen Vision + GPT-OSS 120B)")
    root.after(2000, lambda: set_status(""))

init_text = "Mode: Hybrid (Groq 120B)" if CURRENT_MODE == "hybrid" else "Mode: Gemini 3.8"
init_color = ACCENT if CURRENT_MODE == "hybrid" else "#30d158"
mode_btn = tk.Label(action_bar, text=init_text, font=(UI_FONT, 9, "bold"), bg=FIELD, fg=init_color,
                    cursor="hand2", padx=8, pady=3)
mode_btn.pack(side=tk.RIGHT, padx=(0, 8))
mode_btn.bind("<Button-1>", lambda _e: toggle_ai_mode())

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Output Text Display â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
output_frame = tk.Frame(main, bg=PANEL)
output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

output = tk.Text(
    output_frame, wrap=tk.WORD, bg=PANEL, fg=TEXT, insertbackground=TEXT,
    font=(UI_FONT, 11), bd=0, highlightthickness=0, padx=4, pady=4,
    selectbackground="#3a3a4c", selectforeground="#ffffff",
)
scrollbar = tk.Scrollbar(output_frame, command=output.yview, bg=PANEL, bd=0, troughcolor=PANEL, highlightthickness=0)
output.config(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

output.tag_configure("user", font=(UI_FONT, 10, "italic"), foreground=MUTED)
output.tag_configure("label_ai", font=(UI_FONT, 9, "bold"), foreground=ACCENT)
output.tag_configure("meta", font=(UI_FONT, 9), foreground=MUTED)
output.tag_configure("error", font=(UI_FONT, 10), foreground=ERROR)
output.tag_configure("bold", font=(UI_FONT, 11, "bold"), foreground=TEXT)
output.tag_configure("code_block", font=(CODE_FONT, 10), background=CODE_BG, foreground=CODE_FG,
                     lmargin1=10, lmargin2=10, rmargin=10, spacing1=4, spacing3=4)

status_lbl = tk.Label(main, text="", font=(UI_FONT, 9), bg=PANEL, fg=MUTED, anchor="w")
status_lbl.pack(fill=tk.X, pady=(0, 3))


def set_status(text):
    status_lbl.config(text=text)


entry_frame = tk.Frame(main, bg=FIELD, padx=10, pady=6)
entry_frame.pack(fill=tk.X)

prompt_entry = tk.Entry(
    entry_frame, bg=FIELD, fg=TEXT, insertbackground=TEXT, font=(UI_FONT, 11),
    bd=0, highlightthickness=0, selectbackground="#3a3a4c",
)
prompt_entry.pack(fill=tk.X)

# Resize Grip
grip = tk.Label(bg, text="[]", font=(UI_FONT, 8), bg=PANEL, fg=MUTED, cursor="arrow")
grip.place(relx=1.0, rely=1.0, x=-14, y=-14, anchor="center")

resize_data = {"x": 0, "y": 0, "w": 0, "h": 0}


def start_resize(e):
    resize_data["x"] = e.x_root
    resize_data["y"] = e.y_root
    resize_data["w"] = root.winfo_width()
    resize_data["h"] = root.winfo_height()


def do_resize(e):
    nw = max(S(440), resize_data["w"] + (e.x_root - resize_data["x"]))
    nh = max(S(360), resize_data["h"] + (e.y_root - resize_data["y"]))
    root.geometry(f"{nw}x{nh}")


grip.bind("<ButtonPress-1>", start_resize)
grip.bind("<B1-Motion>", do_resize)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 6. Rendering & Execution â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def write(text, tag=None):
    output.config(state=tk.NORMAL)
    if tag:
        output.insert(tk.END, text, tag)
    else:
        output.insert(tk.END, text)
    output.see(tk.END)
    output.config(state=tk.DISABLED)


def render_response(text):
    output.config(state=tk.NORMAL)
    parts = re.split(r"(```[\s\S]*?```)", text)
    codes = []
    for part in parts:
        if part.startswith("```"):
            lines = part.split("\n")
            body = "\n".join(lines[1:-1]) if len(lines) > 2 else part.strip("`")
            codes.append(body.strip())
            output.insert(tk.END, "\n" + body + "\n\n", "code_block")
        else:
            bold_parts = re.split(r"(\*\*.*?\*\*)", part)
            for b in bold_parts:
                if b.startswith("**") and b.endswith("**") and len(b) >= 4:
                    output.insert(tk.END, b[2:-2], "bold")
                else:
                    output.insert(tk.END, b)
    output.see(tk.END)
    output.config(state=tk.DISABLED)
    return codes


def solve_problem(problem_text, source_name):
    if state["busy"]:
        set_status("Already solvingâ€¦ please wait")
        return

    # Merge any accumulated pages and images with the current page
    curr_img = state.get("vision_img_b64", "")
    all_images = list(state.get("pending_images", []))
    if curr_img and (problem_text == "__VISION__" or not all_images):
        all_images.append(curr_img)
    
    all_parts = [p for p in state["pending_pages"] if p and p.strip() and p != "__VISION__"]
    if problem_text and problem_text != "__VISION__":
        all_parts.append(problem_text.strip())
        
    combined_text = "\n\n--- (next page) ---\n\n".join(all_parts) if all_parts else "__VISION__"
    total_pages_count = max(len(all_images), len(all_parts), 1)
    
    # Reset pending queues
    state["pending_pages"] = []
    state["pending_images"] = []

    if not combined_text or len(combined_text.strip()) < 5:
        set_status(f"Could not read problem text from {source_name}")
        write(f"\n[Could not detect question on screen. Check debug_last_capture.png]\n", "error")
        return

    state["busy"] = True
    prompt_entry.delete(0, tk.END)

    pages_note = f" [{total_pages_count} pages]" if total_pages_count > 1 else ""
    write(f"\n[Source: {source_name}{pages_note}]\n", "user")

    # Preview what was captured so user can verify immediately
    first_lines = [l.strip() for l in combined_text.strip().splitlines() if l.strip()]
    preview = " ".join(first_lines[:3])
    if len(preview) > 130:
        preview = preview[:127] + "..."
    write(f"Question preview: \"{preview}\"\n", "meta")

    write("Assistant\n", "label_ai")
    output.mark_set("resp_start", "end-1c")
    output.mark_gravity("resp_start", tk.LEFT)

    set_status(f"Solving via {GROQ_MODEL}â€¦")

    def worker():
        try:
            t0 = time.time()
            solve_ts = time.strftime("%Y%m%d_%H%M%S")
            prompt_content = (
                f"<screen_problem>\n{combined_text[:MAX_CONTEXT_CHARS]}\n</screen_problem>\n\n"
                f"Detect the question type and respond with ONLY the direct answer. "
                f"If coding: output ONLY the optimal complete solution code block with zero comments and no preamble/explanation. "
                f"If MCQ: output ONLY the correct option letter and text (e.g. B) ...). "
                f"No preamble, no explanation, no restating the question."
            )

            # Save full prompt and session bundle for inspection & optimization
            prompt_file = CAPTURES_DIR / f"prompt_{solve_ts}.txt"
            session_file = CAPTURES_DIR / f"session_{solve_ts}.json"
            session_record = {
                "timestamp": solve_ts,
                "source": source_name,
                "pages_count": total_pages_count,
                "front_app": state.get("front_app", ""),
                "front_title": _window_title(state.get("front_hwnd", 0)) if state.get("front_hwnd") else "",
                "capture_image": state.get("last_capture_img", ""),
                "raw_combined_text": combined_text,
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": prompt_content,
                "model": GROQ_MODEL,
                "temperature": GROQ_TEMPERATURE,
                "max_tokens": GROQ_MAX_TOKENS,
                "solution": None,
                "duration_sec": 0.0,
            }

            try:
                full_prompt_text = f"=== SYSTEM PROMPT ===\n{SYSTEM_PROMPT}\n\n=== USER PROMPT ===\n{prompt_content}\n"
                prompt_file.write_text(full_prompt_text, encoding="utf-8", errors="replace")
                DEBUG_PROMPT_FILE.write_text(full_prompt_text, encoding="utf-8", errors="replace")
                session_file.write_text(json.dumps(session_record, indent=2, ensure_ascii=False), encoding="utf-8")
                DEBUG_SESSION_FILE.write_text(json.dumps(session_record, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

            is_vision_mode = bool(all_images)
            
            multi_note = f" NOTE: This question spans {len(all_images)} pages/screenshots. Carefully read ALL pages across all images before answering." if len(all_images) > 1 else ""
            instruction = (
                f"You are an expert test assistant and problem solver.{multi_note} "
                "Analyze this problem carefully and solve it step-by-step internally. "
                "Output ONLY the final direct answer: "
                "1. If MCQ / Aptitude / Math / SQL: Output ONLY the correct option letter and option text (e.g. B) 12 days). No preamble, no explanation. "
                "2. If Coding / DSA: Output ONLY the complete, optimal, bug-free C++ code block. Include needed headers/includes. Zero comments, zero preamble, zero notes. "
                "3. If Short-Answer / True-False: Output ONLY the direct answer."
            )

            full_text = ""

            if CURRENT_MODE == "hybrid":
                set_status("Solving via Fast Hybrid (Qwen Vision + GPT-OSS 120B)...")
                try:
                    full_text = call_groq_hybrid_pipeline(all_images if is_vision_mode else [], combined_text, instruction)
                    def render_hybrid(txt=full_text):
                        output.config(state=tk.NORMAL)
                        output.insert("end-1c", txt)
                        output.see(tk.END)
                        output.config(state=tk.DISABLED)
                    root.after(0, render_hybrid)
                except Exception as h_err:
                    print(f"[Hybrid failed: {h_err}] -> Fallback to direct Groq...")
                    CURRENT_MODE = "gemini"

            if CURRENT_MODE == "gemini":
                set_status("Solving via Gemini 3.8 Flash...")
                gemini_prompt = f"{SYSTEM_PROMPT}\n\n{instruction}"
                if combined_text and combined_text != "__VISION__":
                    gemini_prompt += f"\n\n<problem_text>\n{combined_text}\n</problem_text>"
                try:
                    full_text = call_gemini_vision(all_images if is_vision_mode else [], gemini_prompt)
                    def render_gemini(txt=full_text):
                        output.config(state=tk.NORMAL)
                        output.insert("end-1c", txt)
                        output.see(tk.END)
                        output.config(state=tk.DISABLED)
                    root.after(0, render_gemini)
                except Exception as g_err:
                    print(f"[Gemini failed: {g_err}] -> Emergency Groq fallback...")
                    full_text = call_groq_hybrid_pipeline(all_images if is_vision_mode else [], combined_text, instruction)
                    def render_emer(txt=full_text):
                        output.config(state=tk.NORMAL)
                        output.insert("end-1c", txt)
                        output.see(tk.END)
                        output.config(state=tk.DISABLED)
                    root.after(0, render_emer)

            def finish():
                t_solve = round(time.time() - t0, 2)
                session_record["solution"] = full_text
                session_record["duration_sec"] = t_solve
                try:
                    session_file.write_text(json.dumps(session_record, indent=2, ensure_ascii=False), encoding="utf-8")
                    DEBUG_SESSION_FILE.write_text(json.dumps(session_record, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass

                output.config(state=tk.NORMAL)
                output.delete("resp_start", tk.END)
                output.config(state=tk.DISABLED)
                codes = render_response(full_text)
                if codes:
                    state["last_code"] = codes[-1]
                write(f"\nDone - {source_name} ({t_solve}s)\n", "meta")
                write(f"Inputs saved: captures/{session_file.name}\n", "meta")
                state["busy"] = False
                set_status("Done! /+S=solve  /+D=append page")
                root.after(3000, lambda: set_status(""))

            root.after(0, finish)

        except Exception as err:
            err_msg = str(err)
            def err_finish(msg=err_msg):
                output.config(state=tk.NORMAL)
                output.delete("resp_start", tk.END)
                output.config(state=tk.DISABLED)
                write(f"\nError: {msg}\n", "error")
                state["busy"] = False
                set_status("Error occurred")
            root.after(0, err_finish)

    threading.Thread(target=worker, daemon=True).start()


def solve_screen_action(target_hwnd=None):
    if target_hwnd:
        remember_specific_hwnd(target_hwnd)

    import time

    def do_capture():
        # If overlay is currently visible, temporarily make it transparent so it doesn't block the screen capture
        was_visible = is_visible()
        saved_alpha = current_alpha if was_visible else TARGET_ALPHA

        if was_visible:
            root.after(0, lambda: root.attributes("-alpha", 0.0))
            time.sleep(0.04)

        problem_text, source = capture_screen_problem()

        # Restore visibility and update UI
        def on_captured():
            show_window(saved_alpha)
            solve_problem(problem_text, source)

        root.after(0, on_captured)

    set_status("Capturing screen problemâ€¦")
    threading.Thread(target=do_capture, daemon=True).start()


def handle_screen_shortcut(fg_hwnd=None):
    """
    One-shortcut toggle & solve (/ + S / F9):
    - If currently invisible (0%):
        Captures clean screen unobstructed, shows overlay at 85%, and displays solution.
    - If currently visible (>= 85%):
        Reduces visibility to 0% (invisible & click-through).
    """
    if is_visible():
        hide_window()
    else:
        if fg_hwnd:
            remember_specific_hwnd(fg_hwnd)
        else:
            remember_front_app()
        solve_screen_action(target_hwnd=fg_hwnd)


def solve_clip_action():
    if not is_visible():
        show_window(TARGET_ALPHA)
    try:
        clip_txt = root.clipboard_get().strip()
        if clip_txt:
            solve_problem(clip_txt, "Clipboard text")
        else:
            set_status("Clipboard is empty (copy problem first)")
    except Exception:
        set_status("Clipboard is empty (copy problem first)")


def handle_prompt_submit(_event=None):
    query = prompt_entry.get().strip()
    if query:
        solve_problem(query, "Manual input")
    else:
        solve_screen_action()


def append_page_action(fg_hwnd=None):
    """/ + D / F11 â€” capture another page and append to pending context without solving yet."""
    if state["busy"]:
        set_status("Busy solvingâ€¦ wait before appending another page")
        return
    if fg_hwnd:
        remember_specific_hwnd(fg_hwnd)

    import time

    def do_append():
        was_visible = is_visible()
        saved_alpha = current_alpha if was_visible else TARGET_ALPHA

        if was_visible:
            root.after(0, lambda: root.attributes("-alpha", 0.0))
            time.sleep(0.04)

        ocr_text, source = capture_screen_problem()

        def on_appended():
            show_window(saved_alpha)
            if ocr_text and len(ocr_text.strip()) > 5:
                state["pending_pages"].append(ocr_text.strip())
                count = len(state["pending_pages"])
                set_status(f"Page {count} appended - press /+S to solve all {count + 1} pages")
                write(f"\n[Page {count} appended from {source} - press /+S to solve]\n", "meta")
                root.after(4000, lambda: set_status(""))
            else:
                set_status("Could not capture page text â€” try again")

        root.after(0, on_appended)

    set_status("Capturing next page to appendâ€¦")
    threading.Thread(target=do_append, daemon=True).start()


prompt_entry.bind("<Return>", handle_prompt_submit)
root.bind("<Escape>", lambda _e: hide_window())

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 7. Global Hotkeys (Win32) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
hotkey_queue = queue.Queue()
WM_HOTKEY, MOD_NOREPEAT = 0x0312, 0x4000
HK_TOGGLE, HK_QUIT, HK_SCREEN, HK_CLIP, HK_APPEND = 1, 2, 3, 4, 5

VK_F9  = 0x78  # Solve screen
VK_F10 = 0x79  # Toggle overlay
VK_F11 = 0x7A  # Append page

ULONG_PTR = ctypes.c_size_t

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

VK_SLASH   = 0xBF  # '/' key (VK_OEM_2)
VK_DIVIDE = 0x6F  # numpad '/' key
VK_CONTROL = 0x11
VK_MENU    = 0x12  # Alt
VK_LWIN    = 0x5B
VK_RWIN    = 0x5C

_hhook = None
_slash_down = False
_slash_count = 0
_slash_time = 0.0
_swallow_slash_up = False
_blocked_keys = set()


def _low_level_keyboard_proc(nCode, wParam, lParam):
    global _slash_down, _slash_count, _slash_time, _swallow_slash_up, _blocked_keys
    if nCode >= 0:
        kbd = KBDLLHOOKSTRUCT.from_address(lParam)
        # Ignore simulated keys (e.g. Backspace cleanup)
        if kbd.flags & 0x10:  # LLKHF_INJECTED
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        vk = kbd.vkCode
        is_down = (wParam in (0x0100, 0x0104))  # WM_KEYDOWN, WM_SYSKEYDOWN
        is_up = (wParam in (0x0101, 0x0105))    # WM_KEYUP, WM_SYSKEYUP

        # If Ctrl, Alt, or Win is pressed, this is an IDE/system shortcut (e.g. Ctrl + / in VS Code, Ctrl + S, etc.).
        # Screen Assistant hotkeys NEVER use Ctrl/Alt/Win. Pass through immediately and clean up chord state.
        is_modifier_active = (
            (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0 or
            (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0 or
            (user32.GetAsyncKeyState(VK_LWIN) & 0x8000) != 0 or
            (user32.GetAsyncKeyState(VK_RWIN) & 0x8000) != 0
        )
        if is_modifier_active:
            _slash_down = False
            _slash_count = 0
            _swallow_slash_up = False
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        # Support both standard '/' (0xBF) and Numpad '/' (0x6F)
        is_slash_physically_down = (
            ((user32.GetAsyncKeyState(VK_SLASH) & 0x8000) != 0) or
            ((user32.GetAsyncKeyState(VK_DIVIDE) & 0x8000) != 0)
        )

        if vk in (VK_SLASH, VK_DIVIDE):
            if is_down:
                if not _slash_down:
                    _slash_down = True
                    _slash_count = 1
                    _slash_time = time.time()
                else:
                    _slash_count += 1
            elif is_up:
                _slash_down = False
                _slash_count = 0
                if _swallow_slash_up:
                    _swallow_slash_up = False
                    return 1  # Swallow slash keyup after chord triggered

        elif is_down:
            # Chord trigger: valid if slash is physically held OR if slash was pressed within last 1.5 seconds!
            now = time.time()
            is_recent_slash = _slash_down and ((now - _slash_time) <= 1.5)
            is_active_chord = is_slash_physically_down or is_recent_slash

            if not is_active_chord:
                _slash_down = False
                _slash_count = 0
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            action = None
            if vk in (ord('S'), ord('s')):     # / + S -> solve screen
                action = "screen"
            elif vk in (ord('Z'), ord('z')):    # / + Z -> toggle visibility
                action = "toggle"
            elif vk in (ord('D'), ord('d')):    # / + D -> append page
                action = "append"
            elif vk in (ord('C'), ord('c')):    # / + C -> clip
                action = "clip"
            elif vk in (ord('Q'), ord('q')):    # / + Q -> quit
                action = "quit"
            elif vk == 0x31:                     # / + 1 -> show / bring to front
                action = "show"

            if action:
                _blocked_keys.add(vk)
                _swallow_slash_up = True
                _slash_down = False  # Reset chord so subsequent presses don't misfire
                fg = user32.GetForegroundWindow()
                # Clean up the '/' character(s) typed while slash was held down
                for _ in range(max(1, _slash_count)):
                    user32.keybd_event(0x08, 0, 0, 0)  # Backspace down
                    user32.keybd_event(0x08, 0, 2, 0)  # Backspace up
                _slash_count = 0
                hotkey_queue.put((action, fg))
                return 1  # Block the triggered key from typing

        elif is_up:
            if vk in _blocked_keys:
                _blocked_keys.discard(vk)
                return 1  # Block the keyup of the chord key

    return user32.CallNextHookEx(None, nCode, wParam, lParam)


_c_hook = HOOKPROC(_low_level_keyboard_proc)


def poll_hotkey_queue():
    try:
        while True:
            item = hotkey_queue.get_nowait()
            action, fg = item if isinstance(item, tuple) else (item, 0)
            if action == "screen":
                handle_screen_shortcut(fg)
            elif action == "toggle":
                toggle_window()
            elif action == "show":
                show_window(TARGET_ALPHA)
            elif action == "quit":
                root.destroy()
                return
            elif action == "clip":
                solve_clip_action()
            elif action == "append":
                append_page_action(fg)
    except queue.Empty:
        pass
    root.after(50, poll_hotkey_queue)


def hotkey_thread():
    global _hhook
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.CallNextHookEx.restype = ctypes.c_longlong
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

    # 1. Install low-level keyboard hook for / + S / D / Z / C / Q / 1
    _hhook = user32.SetWindowsHookExW(13, _c_hook, None, 0)
    atexit.register(lambda: user32.UnhookWindowsHookEx(_hhook) if _hhook else None)

    # 2. Also register safe single keys (no Ctrl, no Alt, no F1-F4, F7, F8) as alternative
    ok_s = user32.RegisterHotKey(None, HK_SCREEN, MOD_NOREPEAT, VK_F9)
    ok_z = user32.RegisterHotKey(None, HK_TOGGLE, MOD_NOREPEAT, VK_F10)
    ok_d = user32.RegisterHotKey(None, HK_APPEND, MOD_NOREPEAT, VK_F11)

    print(f"Hotkeys active: /+S/F9 ({bool(ok_s)}) | /+Z/F10 ({bool(ok_z)}) | /+D/F11 ({bool(ok_d)}) | /+C | /+Q (Zero Ctrl/Alt)")

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            fg = user32.GetForegroundWindow()
            if msg.wParam == HK_TOGGLE:
                hotkey_queue.put(("toggle", fg))
            elif msg.wParam == HK_QUIT:
                hotkey_queue.put(("quit", fg))
            elif msg.wParam == HK_SCREEN:
                hotkey_queue.put(("screen", fg))
            elif msg.wParam == HK_CLIP:
                hotkey_queue.put(("clip", fg))
            elif msg.wParam == HK_APPEND:
                hotkey_queue.put(("append", fg))
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    if _hhook:
        user32.UnhookWindowsHookEx(_hhook)


threading.Thread(target=hotkey_thread, daemon=True).start()

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ 8. Launch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
write(
    "Screen Assistant Ready  [Vision AI: Gemini 3.8 Flash]\n"
    "  F9  / +S  ->  Solve screen question\n"
    "  F10 / +Z  ->  Toggle show / hide\n"
    "  F11 / +D  ->  Append next page\n"
    "  /+C        ->  Solve clipboard text\n"
    "  /+1        ->  Show overlay\n"
    "  /+Q        ->  Quit\n\n",
    "meta",
)

def _listen_show_event():
    while True:
        try:
            res = _kernel32.WaitForSingleObject(_show_event, 500)
            if res == 0:  # WAIT_OBJECT_0
                root.after(0, lambda: show_window(TARGET_ALPHA))
        except Exception:
            break

threading.Thread(target=_listen_show_event, daemon=True).start()

root.update()
setup_overlay()
if "--show" in sys.argv or "-s" in sys.argv:
    root.after(100, lambda: show_window(TARGET_ALPHA))
root.after(60, prompt_entry.focus_force)
root.after(50, poll_hotkey_queue)
root.after(400, poll_front_app)
root.mainloop()

