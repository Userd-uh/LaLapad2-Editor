# Trackpad UI — option 1 implementation QA

Date: 2026-09-20

## Outcome and acceptance

- Keymap shows 52 physical controls and two trackpad entrances in the inner hardware positions; virtual inputs remain in the data but are edited in Trackpad.
- Clicking either trackpad opens that side and preserves the selected layer.
- Trackpad names the editing side prominently and separates 操作の割り当て / 動き・感度 / 詳細設定.
- Operations show human-readable results such as 左クリック; modes, disabled operations, inherited bindings, pinch modifiers and shared tap/hold bindings remain distinguishable.
- All original settings, 76 binding positions, save/RPC contracts, and per-side/per-layer isolation are retained.

## Visual evidence

Source visual truth: `C:/Users/heheh/.codex/generated_images/01a0bcf8-465b-7281-b1a8-2130b1ead7df/exec-0c19730f-7f6f-4818-a9a3-9ce78a01da74.png` (2103 × 748 pixels; two concept frames, no defined CSS viewport).

Implementation: `http://localhost:5173/` (also available at the development preview on port 5174).

- `design-evidence/keymap-desktop.png`: 1440 × 960, Default layer, no palette open.
- `design-evidence/trackpad-desktop-final.png`: 1440 × 960, left side, Default layer, tap 1 selected.
- `design-evidence/comparison-desktop-final.png`: source and both implementation captures in the same comparison image.
- `design-evidence/comparison-detail-final.png`: operation rows and editor crops together at equal width.
- `design-evidence/trackpad-narrow.png`, `trackpad-narrow-editor.png`, `feel-narrow.png`: 680 × 900 responsive checks.

Desktop and narrow captures have one screenshot pixel per CSS pixel. The full comparison reduces each 1440 × 960 capture to 1052 × 701 (0.731 scale), keeping the source at its original dimensions. The focused comparison aligns region widths (990 pixels). Concept frame padding and the retained real device toolbar differ; these are not pixel-identical application states. Typography readability was also inspected in the original, unscaled captures. Viewport overrides were reset after verification.

## Comparison history and findings

1. First comparison (`comparison-desktop.png`): **P2**, editor panel proportion was too narrow (345 pixels at desktop) relative to the selected mock. This wrapped explanatory text unnecessarily. Changed the desktop grid to `minmax(350px,1.6fr) minmax(320px,1fr)`.
2. Revised comparison (`comparison-desktop-final.png`, `comparison-detail-final.png`): the editor now occupies approximately 38% of the content area, consistent with the mock's hierarchy; primary assignment action is visible. No remaining actionable P0/P1/P2 visual findings.
3. During interaction checks, the macro shortcut opened Basic because it used `macro` instead of the existing `macro_pal` category ID. Fixed and verified that mc0–mc15 appear. This was a functional finding, not a visual-comparison iteration.
4. The five-way arrow labels were truncated at their physical positions. Native arrow-key text now uses arrows while accessible names and binding tooltips retain the full meaning. The final Keymap capture verifies this.

## Required fidelity surfaces

- **Fonts and typography:** retain the application's Segoe UI/system sans stack and Japanese fallback. The concept is a raster image with no font metadata; exact font identity is not asserted. Prominent 29 px editing-side heading, 14 px operation text and 12 px supporting text remain readable at native size. Existing compact global controls are preserved. Long physical-key macro/layer names use ellipsis with full accessible names/tooltips (P3 refinement opportunity).
- **Spacing and layout:** physical split keyboard, internal pads, help block, prominent side selector, purpose tabs, two-column action list/editor and fixed scope footer follow option 1. Narrow layout becomes one column; choosing an operation scrolls to its editor. At 680 px the document has no horizontal overflow and persistent controls remain visible. Keymap intentionally scrolls horizontally below its 680 px physical-layout minimum.
- **Colors and tokens:** existing dark navy backgrounds, mint primary actions, cyan selection, light text and muted secondary text match the design direction. Existing blue RPC and orange firmware-change indicators are retained for their functional meaning.
- **Image quality:** generated transparent raster hardware asset is based on the supplied photograph, retains both halves and pads, and has no wood background. Interactive key labels are native controls. Hardware is dimmed behind controls. The source concept omitted some physical keys; actual firmware positions and the supplied hardware geometry take precedence over that image-generation error.
- **Copy and content:** operation-to-result labels are Japanese and side/layer context appears in the editor. Additional real settings include per-axis modes, enable switches, inherited/no-output choices and shared hold bindings. These add rows beyond the abbreviated concept, deliberately preserving supported behavior. Local Save All and hardware application remain distinct. No instructional prompt text is exposed in the product.

## Functional verification

Baseline: 31 Python tests and the existing gesture/device JavaScript suites passed before edits.

Final automated checks:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q — 31 passed
node test_trackpad_workspace.js — passed
node test_gesture_actions.js — passed
node test_device_binding_codec.js — passed
git diff --check — passed
```

New checks cover all 24 virtual positions, shared hold/tap bindings, hidden inactive directions without data loss, complete settings partition, physical positions, stale picker callbacks, template completion and opposite-side copy isolation.

Browser checks on the actual running application:

- 52 native physical-key controls and two side-specific pad entrances.
- Right-pad keyboard activation opens the right side while retaining layer 1.
- Left tap assignment changes without changing the right side.
- Right tap threshold changed from 250 to 300; left remained 250; right retained 300 after switching back.
- Changing two-finger horizontal mode from keys to scroll hides directional actions, preserves saved Right/Left bindings, and restores them when switched back.
- Macro picker opens the macro category; switching sides closes the stale picker.
- Physical Q key edited to A through the existing palette.
- Narrow-screen selection reaches the action editor; sensitivity controls remain readable.
- Captured browser console warnings/errors: none.
- All browser-only test changes discarded by reload; no Save All, MCU load/write or firmware write performed.

Static review compared the final diff and data flow with existing positions, config schema and save routes. A separate agent review was attempted but unavailable due to its usage limit; no independent-review claim is made. No firmware source changes were made by this UI implementation. Real-device behavior is not verified by these checks.

## Implementation checklist

- [x] Move trackpad assignment UI out of Keymap.
- [x] Add hardware-position navigation for both pads.
- [x] Make editing side and layer explicit.
- [x] Separate gesture actions, feel and advanced numeric settings.
- [x] Preserve bindings/settings and existing physical-key editing.
- [x] Verify desktop/narrow renderings and core interactions.
- [x] Refresh normal localhost service and discard unsaved test changes.
- [ ] Optional P3: shorten long user-defined layer/macro labels on physical keycaps.

Project knowledge capture to Obsidian was not performed because the vault lies outside this session's writable roots; implementation and verification evidence are recorded here.

final result: passed
