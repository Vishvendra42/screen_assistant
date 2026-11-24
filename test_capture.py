"""
test_capture.py — Screen Assistant Capture & OCR Diagnostic Tool

Inspect exactly what the screen reader captures, review raw OCR output,
see the exact prompt payload constructed for the model, and test
the model's live response to evaluate and optimize accuracy.

Usage:
  python test_capture.py                 (Interactive mode)
  python test_capture.py --now           (Capture active window immediately)
  python test_capture.py --delay 3       (3-second countdown to switch windows)
  python test_capture.py --solve         (Capture & solve via Groq)
  python test_capture.py --last          (Test OCR & prompt on debug_last_capture.png)
  python test_capture.py --file img.png  (Test OCR & prompt on a custom image)
  python test_capture.py --fullscreen    (Capture all monitors instead of active window)
  python test_capture.py --open          (Open captured image & files in Explorer)
"""
import os
import sys
import time
import json
import ctypes
import argparse
from ctypes import wintypes
from pathlib import Path

# Ensure working directory is this script's directory
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

# Configure UTF-8 safe stdout/stderr for Windows terminal
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── 1. Set DPI Awareness ───────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

# ── 2. Load Environment & Groq ─────────────────────────────────
from dotenv import load_dotenv
load_dotenv(SCRIPT_DIR / ".env")

GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL       = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MAX_TOKENS  = int(os.getenv("GROQ_MAX_TOKENS", "4096"))
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
OCR_LANG         = os.getenv("SCREEN_OCR_LANG", "en")

# ── 3. Dependencies ───────────────────────────────────────────
try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

# Captures directory
CAPTURES_DIR = SCRIPT_DIR / "captures"
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

DEBUG_LAST_IMG     = SCRIPT_DIR / "debug_last_capture.png"
DEBUG_LAST_OCR     = SCRIPT_DIR / "debug_last_ocr.txt"
DEBUG_LAST_PROMPT  = SCRIPT_DIR / "debug_last_prompt.txt"
DEBUG_LAST_SESSION = SCRIPT_DIR / "debug_last_session.json"

SYSTEM_PROMPT = """You are an expert problem solver and assistant. The user provides text captured via OCR or API directly from their screen (e.g. online assessment, browser, IDE, exam, or LeetCode).

ABSOLUTE RULES — follow every rule without exception:
1. OCR NOISE & ACTIVE QUESTION DETECTION:
   - The captured text may include browser chrome, tabs, URLs, navigation buttons, question counters, running scores, or previous chat history.
   - Always focus on the CURRENT / ACTIVE question (typically the latest question presented at the bottom or the main prompt).
2. DETECT THE QUESTION TYPE AND ANSWER ACCORDINGLY:
   - CODING / PROGRAMMING / DSA PROBLEM:
     * Output ONLY the complete, optimal, bug-free solution code inside a single markdown code block (e.g. ```cpp ... ```).
     * Follow any language explicitly requested in the problem (default to C++ if none specified).
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


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def get_foreground_window_info():
    """Retrieve detailed info about the active foreground window."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"hwnd": 0, "title": "Desktop / Unknown", "exe": "explorer.exe", "pid": 0, "bbox": None}

    # Window Title
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    title = buf.value or "Untitled Window"

    # Process Name
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    exe = "unknown"
    hproc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if hproc:
        buf_p = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(hproc, 0, buf_p, ctypes.byref(size)):
            exe = Path(buf_p.value).name
        kernel32.CloseHandle(hproc)

    # Window Coordinates
    rect = wintypes.RECT()
    bbox = None
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        left = max(rect.left, vx)
        top = max(rect.top, vy)
        right = min(rect.right, vx + vw)
        bottom = min(rect.bottom, vy + vh)
        if right - left > 50 and bottom - top > 50:
            bbox = (left, top, right, bottom)

    return {
        "hwnd": hwnd,
        "title": title,
        "exe": exe,
        "pid": pid.value,
        "bbox": bbox,
    }


def _gdi_grab(bbox=None):
    """Fallback Win32 GDI capture if ImageGrab fails."""
    if bbox:
        x, y, r, b = bbox
        w, h = max(1, r - x), max(1, b - y)
    else:
        x, y = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
        w, h = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
        if w <= 0 or h <= 0:
            x, y = 0, 0
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbm)
    gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, 0x00CC0020 | 0x40000000)  # SRCCOPY | CAPTUREBLT

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bmi), 0)

    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)

    return Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)


def grab_screenshot(bbox=None, fullscreen=False):
    """Grab screenshot with automatic fallback chain."""
    if not HAS_PIL:
        raise RuntimeError("Pillow is not installed. Run: pip install Pillow")

    # 1. Try ImageGrab
    try:
        if fullscreen or bbox is None:
            return ImageGrab.grab(bbox=None, all_screens=True), "Full Desktop Screen (ImageGrab)"
        else:
            return ImageGrab.grab(bbox=bbox, all_screens=True), f"Window {bbox[2]-bbox[0]}x{bbox[3]-bbox[1]} (ImageGrab)"
    except Exception as e:
        # 2. Try Win32 GDI fallback
        try:
            img = _gdi_grab(bbox=None if fullscreen else bbox)
            desc = "Full Desktop Screen (GDI BitBlt)" if (fullscreen or bbox is None) else f"Window (GDI BitBlt)"
            return img, desc
        except Exception as e2:
            raise RuntimeError(f"Screen grab failed (screen may be locked or asleep). Error: {e2}")


def run_ocr(image):
    """Run Windows native OCR on the PIL image."""
    if not HAS_WINOCR:
        return "", "winocr not installed"
    t0 = time.time()
    try:
        res = winocr.recognize_pil_sync(image, OCR_LANG)
        raw_lines = []
        if isinstance(res, dict) and "lines" in res:
            raw_lines = [l.get("text", "").strip() for l in res["lines"] if l.get("text", "").strip()]
        elif hasattr(res, "lines"):
            raw_lines = [getattr(l, "text", "").strip() for l in res.lines if getattr(l, "text", "").strip()]
        else:
            raw_lines = str(res).splitlines()

        ocr_text = "\n".join(raw_lines).strip()
        elapsed_ms = int((time.time() - t0) * 1000)
        return ocr_text, f"winocr ({elapsed_ms}ms)"
    except Exception as e:
        return "", f"winocr error: {e}"


def analyze_question_type(text):
    """Heuristic helper to classify question type."""
    t_lower = text.lower()

    # Coding patterns
    code_indicators = [
        "class solution", "def ", "public static", "int main", "vector<",
        "constraints:", "example 1:", "input:", "output:", "explanation:",
        "leetcode", "hackerrank", "given an array", "return the number"
    ]
    if any(k in t_lower for k in code_indicators):
        return "Coding / DSA Problem", "Will generate 100% clean, optimal C++ code with zero comments."

    # MCQ patterns
    mcq_letters = [l for l in ["a)", "b)", "c)", "d)", "a.", "b.", "c.", "d."] if l in t_lower]
    if len(mcq_letters) >= 2 or ("which of the following" in t_lower) or ("choose the correct" in t_lower):
        return "Multiple Choice (MCQ)", "Will output ONLY the correct option letter & text (e.g. B) ...)."

    # True / False
    if "true or false" in t_lower or "true/false" in t_lower:
        return "True / False", "Will output ONLY True or False."

    # Numerical
    if any(k in t_lower for k in ["calculate", "evaluate", "compute", "find the value of"]):
        return "Numerical / Math", "Will output ONLY the final numeric result."

    return "Theory / Conceptual / Short Answer", "Will output a concise, direct, high-scoring answer."


def format_llm_prompt(screen_text):
    """Format prompt payload identically to assistant.py."""
    return (
        f"<screen_problem>\n{screen_text[:14000]}\n</screen_problem>\n\n"
        f"Detect the question type and respond with ONLY the direct answer. "
        f"If coding: output ONLY the optimal complete solution code block with zero comments and no preamble/explanation. "
        f"If MCQ: output ONLY the correct option letter and text (e.g. B) ...). "
        f"No preamble, no explanation, no restating the question."
    )


def execute_test(delay=3, fullscreen=False, solve=False, open_files=False, custom_file=None, use_last=False):
    """Perform a complete test capture, OCR, analysis, and optional solve."""
    print("\n" + "=" * 65)
    print(" [SCREEN ASSISTANT — CAPTURE & INPUT OPTIMIZER]")
    print("=" * 65)

    img = None
    win = {"title": "Image File", "exe": "file", "pid": 0, "bbox": None}
    grab_desc = "Custom Image"

    if use_last:
        if not DEBUG_LAST_IMG.exists():
            print(f"❌ Error: {DEBUG_LAST_IMG} does not exist yet.")
            return None
        print(f"🖼️ Loading last capture: {DEBUG_LAST_IMG}")
        img = Image.open(DEBUG_LAST_IMG)
        grab_desc = f"Loaded from {DEBUG_LAST_IMG.name}"
    elif custom_file:
        p = Path(custom_file)
        if not p.exists():
            print(f"❌ Error: File {custom_file} not found.")
            return None
        print(f"🖼️ Loading custom image: {p}")
        img = Image.open(p)
        grab_desc = f"Loaded from {p.name}"
    else:
        if delay > 0:
            print(f"\n⏳ Switch to your target window now (LeetCode, Test, IDE, PDF)...")
            for i in range(delay, 0, -1):
                print(f"   Capturing in {i}...", end="\r", flush=True)
                time.sleep(1)
            print("   Capturing NOW!                    \n")

        # 1. Target window info
        win = get_foreground_window_info()
        print(f"🎯 Target Window : {win['title']}")
        print(f"📁 Process       : {win['exe']} (PID: {win['pid']})")
        if win['bbox']:
            w = win['bbox'][2] - win['bbox'][0]
            h = win['bbox'][3] - win['bbox'][1]
            print(f"📐 Geometry      : {w}x{h} at ({win['bbox'][0]}, {win['bbox'][1]})")

        # 2. Capture screenshot
        bbox = None if fullscreen else win['bbox']
        try:
            img, grab_desc = grab_screenshot(bbox=bbox, fullscreen=fullscreen)
        except Exception as e:
            print(f"\n⚠️  Screen capture notice: {e}")
            if DEBUG_LAST_IMG.exists():
                print(f"   Falling back to testing OCR on last saved capture: {DEBUG_LAST_IMG.name}")
                img = Image.open(DEBUG_LAST_IMG)
                grab_desc = f"Fallback to {DEBUG_LAST_IMG.name}"
            else:
                return None

    print(f"🖼️ Capture Mode  : {grab_desc}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    img_path = CAPTURES_DIR / f"test_{ts}.png"
    img.save(img_path)
    img.save(DEBUG_LAST_IMG)
    print(f"💾 Saved Image   : {img_path}")

    # 3. Run OCR
    print("\n" + "─" * 65)
    print("🔍 RUNNING WINDOWS OCR...")
    print("─" * 65)
    ocr_text, ocr_engine = run_ocr(img)

    lines = [l for l in ocr_text.splitlines() if l.strip()]
    chars = len(ocr_text)
    print(f"⚙️  Engine       : {ocr_engine}")
    print(f"📊 Extracted     : {len(lines)} lines | {chars} characters")

    # Save raw OCR
    ocr_path = CAPTURES_DIR / f"test_{ts}_ocr.txt"
    ocr_path.write_text(ocr_text, encoding="utf-8", errors="replace")
    DEBUG_LAST_OCR.write_text(ocr_text, encoding="utf-8", errors="replace")
    print(f"💾 Saved OCR     : {ocr_path}")

    # 4. Show OCR Content
    print("\n" + "─" * 65)
    print("📝 RAW OCR TEXT CAPTURED FROM SCREEN (Line-by-Line):")
    print("─" * 65)
    if not lines:
        print("⚠️ [WARNING] No text could be recognized! Check the screenshot to ensure text is visible.")
    else:
        for idx, line in enumerate(lines, 1):
            print(f" {idx:02d} | {line}")

    # 5. Question type & heuristic
    q_type, q_behavior = analyze_question_type(ocr_text)
    print("\n" + "─" * 65)
    print("🧠 QUESTION TYPE DETECTION & HEURISTICS:")
    print("─" * 65)
    print(f"📌 Detected Type : {q_type}")
    print(f"💡 AI Directive  : {q_behavior}")

    # 6. Exact Prompt Assembly
    user_prompt = format_llm_prompt(ocr_text)
    prompt_path = CAPTURES_DIR / f"test_{ts}_prompt.txt"
    prompt_path.write_text(
        f"=== SYSTEM PROMPT ===\n{SYSTEM_PROMPT}\n\n=== USER PROMPT ===\n{user_prompt}\n",
        encoding="utf-8",
        errors="replace"
    )
    DEBUG_LAST_PROMPT.write_text(prompt_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"💾 Saved Prompt  : {prompt_path}")

    # 7. Complete Session Bundle
    session_data = {
        "timestamp": ts,
        "window": {
            "title": win["title"],
            "process": win["exe"],
            "pid": win["pid"],
            "bbox": win["bbox"],
        },
        "capture_mode": grab_desc,
        "image_file": str(img_path.resolve()),
        "ocr_metrics": {
            "engine": ocr_engine,
            "lines_count": len(lines),
            "chars_count": chars,
        },
        "detected_question_type": q_type,
        "raw_ocr_text": ocr_text,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "groq_config": {
            "model": GROQ_MODEL,
            "max_tokens": GROQ_MAX_TOKENS,
            "temperature": GROQ_TEMPERATURE,
        },
        "solution": None,
    }

    bundle_path = CAPTURES_DIR / f"test_{ts}_bundle.json"

    # 8. Optional Solve via Groq
    if solve:
        print("\n" + "─" * 65)
        print(f"🤖 SOLVING VIA GROQ ({GROQ_MODEL})...")
        print("─" * 65)
        if not GROQ_API_KEY:
            print("❌ Error: GROQ_API_KEY is not set in .env")
        else:
            try:
                client = Groq(api_key=GROQ_API_KEY)
                t_solve0 = time.time()
                stream = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=GROQ_MAX_TOKENS,
                    temperature=GROQ_TEMPERATURE,
                    stream=True,
                )
                print("\n" + "┌" + "─" * 63 + "┐")
                print("│ MODEL SOLUTION:                                               │")
                print("└" + "─" * 63 + "┘")

                collected_chunks = []
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        collected_chunks.append(delta)
                        print(delta, end="", flush=True)
                print("\n")

                full_solution = "".join(collected_chunks)
                solve_time = round(time.time() - t_solve0, 2)
                print(f"⏱️  Response Time : {solve_time}s")

                session_data["solution"] = {
                    "text": full_solution,
                    "duration_sec": solve_time,
                }

                resp_path = CAPTURES_DIR / f"test_{ts}_response.txt"
                resp_path.write_text(full_solution, encoding="utf-8", errors="replace")
                print(f"💾 Saved Response: {resp_path}")

            except Exception as e:
                print(f"❌ Groq API Error: {e}")
                session_data["solution"] = {"error": str(e)}

    # Save bundle JSON
    bundle_path.write_text(json.dumps(session_data, indent=2, ensure_ascii=False), encoding="utf-8")
    DEBUG_LAST_SESSION.write_text(json.dumps(session_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"📦 Saved Bundle  : {bundle_path}")

    print("\n" + "=" * 65)
    print(" [TEST CAPTURE COMPLETE!]")
    print(f" 📂 Captures Folder : {CAPTURES_DIR.resolve()}")
    print(f" 📝 Last Prompt File : {DEBUG_LAST_PROMPT.resolve()}")
    print("=" * 65)

    if open_files:
        try:
            os.startfile(img_path)
            os.startfile(ocr_path)
            os.startfile(CAPTURES_DIR)
        except Exception:
            pass

    return session_data


def interactive_menu():
    """Simple interactive CLI menu for ease of use."""
    while True:
        print("\n" + "=" * 65)
        print("  SCREEN ASSISTANT — CAPTURE & PROMPT OPTIMIZER MENU")
        print("=" * 65)
        print(" [1] Capture Active Window (3-second countdown)")
        print(" [2] Capture Active Window & SOLVE via Groq")
        print(" [3] Capture Full Desktop Screen (3-second countdown)")
        print(" [4] Test OCR & Prompt on Last Capture (debug_last_capture.png)")
        print(" [5] Test OCR & Prompt on Last Capture + SOLVE via Groq")
        print(" [6] Open Captures Folder in Windows Explorer")
        print(" [7] View Last Captured Raw OCR Text")
        print(" [8] View Last Assembled Prompt")
        print(" [Q] Exit")
        print("=" * 65)

        choice = input(" Choose an option (1-8, Q): ").strip().upper()

        if choice == "1":
            execute_test(delay=3, fullscreen=False, solve=False, open_files=False)
        elif choice == "2":
            execute_test(delay=3, fullscreen=False, solve=True, open_files=False)
        elif choice == "3":
            execute_test(delay=3, fullscreen=True, solve=False, open_files=False)
        elif choice == "4":
            execute_test(use_last=True, solve=False, open_files=False)
        elif choice == "5":
            execute_test(use_last=True, solve=True, open_files=False)
        elif choice == "6":
            os.startfile(CAPTURES_DIR)
        elif choice == "7":
            if DEBUG_LAST_OCR.exists():
                print("\n" + "─" * 60)
                print("LAST CAPTURED OCR TEXT:")
                print("─" * 60)
                print(DEBUG_LAST_OCR.read_text(encoding="utf-8", errors="replace"))
            else:
                print("\nNo capture found yet. Run option 1 first.")
        elif choice == "8":
            if DEBUG_LAST_PROMPT.exists():
                print("\n" + "─" * 60)
                print("LAST ASSEMBLED PROMPT:")
                print("─" * 60)
                print(DEBUG_LAST_PROMPT.read_text(encoding="utf-8", errors="replace"))
            else:
                print("\nNo prompt found yet. Run option 1 first.")
        elif choice in ("Q", "QUIT", "EXIT"):
            print("Exiting...")
            break
        else:
            print("Invalid choice, please select 1-8 or Q.")


def main():
    parser = argparse.ArgumentParser(description="Screen Assistant Capture & OCR Optimizer")
    parser.add_argument("--now", action="store_true", help="Capture immediately without countdown")
    parser.add_argument("--delay", type=int, default=None, help="Countdown delay in seconds (default: 3)")
    parser.add_argument("--fullscreen", action="store_true", help="Capture full screen instead of active window")
    parser.add_argument("--solve", action="store_true", help="Send captured input to Groq API and print solution")
    parser.add_argument("--last", action="store_true", help="Use last saved capture (debug_last_capture.png)")
    parser.add_argument("--file", type=str, default=None, help="Path to custom image file to test OCR on")
    parser.add_argument("--open", action="store_true", help="Open captured files in Explorer after execution")

    args = parser.parse_args()

    # If any specific command line flag was provided, run directly
    if args.now or (args.delay is not None) or args.fullscreen or args.solve or args.last or args.file or args.open:
        delay = 0 if args.now else (args.delay if args.delay is not None else 3)
        execute_test(
            delay=delay,
            fullscreen=args.fullscreen,
            solve=args.solve,
            open_files=args.open,
            custom_file=args.file,
            use_last=args.last,
        )
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
