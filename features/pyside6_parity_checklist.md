# QT-026: PySide6 Parity Checklist

> Execution companion: `features/pyside6_parity_evidence.md` (QT-020 evidence capture scaffold).

**Date:** _______________  
**Tester:** _______________  
**App Version:** _______________  
**Reference (Qt5/6):** _______________  

> **Instructions:** For each item, verify the behavior matches the reference implementation. Mark **✓ PASS** or **✗ BLOCK** and provide evidence (e.g., screenshot, console output, ticket reference).

---

## 1. Toolbar Order & Behavior

| Element | Expected Order (left → right) | Actual Order | PASS/ BLOCK | Evidence |
|---------|------------------------------|--------------|-------------|----------|
| File menu | First | | | |
| View menu | After File | | | |
| Tools menu | After View | | | |
| Help menu | Last | | | |
| Toolbar icons (e.g., Open, Save, Settings) | Consistent with Qt5 layout | | | |
| Toolbar separators | Correct placement | | | |
| Toolbar floatability/dockability | Works as expected | | | |

---

## 2. Tab Order (Focus Navigation)

| Widget Group | Expected Tab Sequence | Actual Sequence | PASS/ BLOCK | Evidence |
|--------------|----------------------|-----------------|-------------|----------|
| Main window widgets | Follow logical flow: Input → Options → Output | | | |
| Tab widgets (QTabWidget) | Tab order preserved per tab page | | | |
| Focus indication (focus ring) | Visible on keyboard navigation | | | |
| Shortcut keys (Alt+X) | Match reference shortcuts | | | |

---

## 3. Splitter Ratios & Behavior

| Splitter | Expected Ratio (left/right or top/bottom) | Actual Ratio | PASS/ BLOCK | Evidence |
|----------|------------------------------------------|--------------|-------------|----------|
| Main horizontal splitter | 30/70 (input/output panels) | | | |
| Options vertical splitter | 20/80 (settings/content) | | | |
| Resizing behavior | Ratios preserved proportionally | | | |
| Minimum size constraints | Enforced correctly | | | |

---

## 4. State Matrix (Widget States)

| Scenario | Expected State | Actual State | PASS/ BLOCK | Evidence |
|----------|---------------|--------------|-------------|----------|
| No data loaded | Input pane disabled, Output pane disabled | | | |
| Data loaded | Input pane enabled, Output pane enabled | | | |
| Processing running | Stop button active, Start button disabled | | | |
| Processing complete | Export buttons enabled, Results tab visible | | | |
| Error state | Error label visible, details expandable | | | |
| Settings changed | Apply button enabled | | | |

---

## 5. Status-Label Semantics

| Status Label | Expected Content/Behavior | Actual Content/Behavior | PASS/ BLOCK | Evidence |
|--------------|--------------------------|-------------------------|-------------|----------|
| Ready/Idle | “Ready” or “Idle” (green) | | | |
| Loading | “Loading…” with spinner | | | |
| Processing | “Processing… X/Y” (progress) | | | |
| Success | “Done” or “Completed” (green) | | | |
| Warning | “Warning: …” (yellow) | | | |
| Error | “Error: …” (red), clickable for details | | | |
| Tooltip on status | Contextual help on hover | | | |

---

## Notes & Comments

________________________________________________________________________  
________________________________________________________________________  
________________________________________________________________________  

---

**Decision:** ☐ PASS for merge ☐ BLOCK (list blockers above) ☐ PENDING
