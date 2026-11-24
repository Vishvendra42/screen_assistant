# ⚡ Screen Assistant (Stealth Windows Edition)

A high-speed, 100% stealth, always-on-top AI assistant built specifically for **capturing and solving assessment problems directly from your screen** (Coding, MCQs, LeetCode, HackerRank, HirePro, Zoom/Meet, etc.) using the Groq API.

---

## 🚀 Ways to Start It

1. **Global Shortcut**: Press **`/ + 1`** anywhere on Windows.
   - If closed: starts up immediately.
   - If running/hidden: brings overlay to the front.
2. **Start Menu Icon**: Open Windows Start Menu / Search -> click **`System Diagnostics Tool`** (native Windows diagnostics icon).
3. **Auto-Start at Login**: A silent background launcher (`WindowsDriverAssistant.lnk`) is installed in Windows Startup so **`/ + 1`** is always ready even after a PC reboot.
4. **Manual**: Double-click **`start.bat`** or run `dist\WDAService.exe`.

*(To stop all background processes at any time, double-click **`stop.bat`** or press **`/ + Q`**)*

---

## ⌨️ Hotkeys & Shortcuts (Zero Ctrl / Alt)

*Platforms and proctoring tools monitor Ctrl/Alt and normal typing patterns. All shortcuts here use `/ + Key` or single Function keys:*

| Hotkey | Alternative | Action |
|---|---|---|
| **`/ + 1`** | — | 🚀 **Launch / Bring to Front** (starts or unhides the overlay) |
| **`/ + S`** | **`F9`** | ⚡ **One-Key Solve & Toggle**: <br>• **1st Press**: Jumps visibility to 85%, reads active question, and solves.<br>• **2nd Press**: Reduces visibility to 0% (invisible & click-through). |
| **`/ + Z`** | **`F10`** | 👁 **Toggle Visibility** (85% ↔ 0% without re-running capture) |
| **`/ + C`** | — | 📋 **Solve Clipboard** (solves whatever was copied to clipboard, opens at 85%) |
| **`/ + D`** | **`F11`** | ➕ **Append Page** (captures another page/scroll and appends to context before solving) |
| **`/ + Q`** | — | ✕ **Quit** application |
| **`Esc` / Click `✕`** | — | Reduce visibility to 0% |

---

## 🥷 Stealth & Anti-Detection Architecture

1. **Zero Ctrl/Alt Hotkeys**:
   - Uses low-level Windows keyboard hooks (`WH_KEYBOARD_LL`) to consume keystrokes at the OS driver level before web browsers (Brave, Chrome, Edge) or proctoring scripts ever receive the events.
   - Using `/` as the modifier prevents accidental triggering during fast English sentence or code typing.
2. **Task Manager Disguise**:
   - **Service Process**: `WDAService.exe` (Description: *Windows Driver Assistant Service*, Company: *Microsoft Corporation*).
   - **Launcher Process**: `WDALauncher.exe` (Description: *Windows Driver Assistant Host*, Company: *Microsoft Corporation*).
3. **Window Invisibility**:
   - `WS_EX_TOOLWINDOW`: Completely hidden from **Alt+Tab** task switcher and Windows **Taskbar**.
   - `WDA_EXCLUDEFROMCAPTURE`: Invisible to screen sharing, screen recorders, and video calls (**Google Meet, Zoom, Teams, OBS, Discord**).
4. **Intelligent Question Detection**:
   - Automatically identifies **Coding/DSA problems**, **Multiple Choice Questions (MCQs)**, **True/False**, and **Theory/Short Answer**.
   - For coding: outputs 100% clean, optimal solution code with zero comments and zero explanation.
   - For MCQs: outputs ONLY the correct option letter and text (e.g. `B) O(log n)`).

---

## 🔨 Rebuilding

To rebuild both `.exe` files after any code changes:
Double-click **[`build.bat`](file:///c:/Users/ASUS/Downloads/prev%20onw/screen_assistant/screen_assistant/build.bat)**.
It compiles `WDAService.exe` and `WDALauncher.exe`, updates `.env`, and sets up all shortcuts automatically.
