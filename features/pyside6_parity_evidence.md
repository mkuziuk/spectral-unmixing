# QT-020: PySide6 Parity Evidence Capture

Use this document to execute manual parity validation against `features/pyside6_parity_checklist.md`.

**Date:** _______________  
**Tester:** _______________  
**App Version:** _______________  
**Reference Build (Qt5/legacy):** _______________  
**Qt Build Under Test:** _______________

## Quick workflow

1. Capture required screenshots for each state in **Section 1**.
2. Complete evidence mapping in **Section 2** while executing checklist items.
3. Mark each row **PASS**, **BLOCK**, or **PENDING**.
4. Add blocker details and follow-up actions in notes.

---

## 1) Required screenshot set (placeholders)

> No screenshots are required now; keep placeholder paths so QA can fill them during execution.

| State (required) | What to show | Screenshot placeholder reference | Captured (Y/N) | Notes |
|---|---|---|---|---|
| startup | Fresh app launch before loading data; toolbar + tabs + status visible | `screenshots/qt/startup.png` | N | |
| data-loaded | Dataset loaded and UI enabled for analysis | `screenshots/qt/data-loaded.png` | N | |
| running | Active processing state with progress/status and button gating | `screenshots/qt/running.png` | N | |
| run-complete | Successful completion state with results/export enabled | `screenshots/qt/run-complete.png` | N | |
| error | Error surfaced with message/details visible | `screenshots/qt/error.png` | N | |

---

## 2) Checklist-to-evidence mapping

### 2.1 Toolbar Order & Behavior

| Ref | Criterion | Disposition (PASS/BLOCK/PENDING) | Evidence placeholder(s) | Notes |
|---|---|---|---|---|
| TB-01 | File menu is first | | `screenshots/qt/startup.png` | |
| TB-02 | View menu follows File | | `screenshots/qt/startup.png` | |
| TB-03 | Tools menu follows View | | `screenshots/qt/startup.png` | |
| TB-04 | Help menu is last | | `screenshots/qt/startup.png` | |
| TB-05 | Toolbar icons order matches reference | | `screenshots/qt/startup.png` | |
| TB-06 | Toolbar separators placement correct | | `screenshots/qt/startup.png` | |
| TB-07 | Toolbar float/dock behavior matches reference | | `screenshots/qt/startup.png` | |

### 2.2 Tab Order (Focus Navigation)

| Ref | Criterion | Disposition (PASS/BLOCK/PENDING) | Evidence placeholder(s) | Notes |
|---|---|---|---|---|
| TAB-01 | Main window tab sequence follows Input → Options → Output flow | | `screenshots/qt/startup.png` | Include keyboard traversal observations |
| TAB-02 | Per-tab widget focus order is preserved | | `screenshots/qt/startup.png`, `screenshots/qt/data-loaded.png` | |
| TAB-03 | Focus indication is visible during keyboard navigation | | `screenshots/qt/startup.png` | |
| TAB-04 | Shortcut keys (Alt+X) match reference behavior | | `screenshots/qt/startup.png` | |

### 2.3 Splitter Ratios & Behavior

| Ref | Criterion | Disposition (PASS/BLOCK/PENDING) | Evidence placeholder(s) | Notes |
|---|---|---|---|---|
| SPL-01 | Main horizontal splitter ratio matches baseline | | `screenshots/qt/startup.png` | Record observed ratio/tolerance |
| SPL-02 | Options vertical splitter ratio matches baseline | | `screenshots/qt/startup.png` | Record observed ratio/tolerance |
| SPL-03 | Splitters resize proportionally without layout breakage | | `screenshots/qt/data-loaded.png` | |
| SPL-04 | Minimum size constraints are enforced | | `screenshots/qt/startup.png` | |

### 2.4 State Matrix (Widget States)

| Ref | Criterion | Disposition (PASS/BLOCK/PENDING) | Evidence placeholder(s) | Notes |
|---|---|---|---|---|
| ST-01 | No data loaded: expected disabled/enabled controls match checklist | | `screenshots/qt/startup.png` | |
| ST-02 | Data loaded: expected controls enabled/visible | | `screenshots/qt/data-loaded.png` | |
| ST-03 | Processing running: Start disabled, Stop active, progress visible | | `screenshots/qt/running.png` | |
| ST-04 | Processing complete: export/actions enabled, results visible | | `screenshots/qt/run-complete.png` | |
| ST-05 | Error state: error label and details are accessible | | `screenshots/qt/error.png` | |
| ST-06 | Settings changed: Apply control enables correctly | | `screenshots/qt/data-loaded.png` | |

### 2.5 Status-Label Semantics

| Ref | Criterion | Disposition (PASS/BLOCK/PENDING) | Evidence placeholder(s) | Notes |
|---|---|---|---|---|
| STATUS-01 | Ready/Idle label text + color semantics are correct | | `screenshots/qt/startup.png` | |
| STATUS-02 | Loading label includes loading indicator/spinner semantics | | `screenshots/qt/data-loaded.png` | |
| STATUS-03 | Processing label shows progress semantics (e.g., X/Y) | | `screenshots/qt/running.png` | |
| STATUS-04 | Success label text + color semantics are correct | | `screenshots/qt/run-complete.png` | |
| STATUS-05 | Warning label text + color semantics are correct | | `screenshots/qt/data-loaded.png` | |
| STATUS-06 | Error label text + color semantics and detail affordance are correct | | `screenshots/qt/error.png` | |
| STATUS-07 | Status tooltip behavior provides contextual help | | `screenshots/qt/startup.png` | |

---

## 3) Blockers and follow-up

| ID | Related refs | Blocker summary | Severity | Owner | Follow-up ticket/link | Status |
|---|---|---|---|---|---|---|
| B-01 | | | | | | |
| B-02 | | | | | | |

---

## 4) Final disposition

**Overall Result:** ☐ PASS for merge ☐ BLOCK ☐ PENDING  
**QA Notes:** ________________________________________________________________
