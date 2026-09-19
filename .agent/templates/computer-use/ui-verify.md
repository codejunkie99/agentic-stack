# Template: single-screen visual verification

Use to verify one screen does what it claims — before trusting it, after a
fix, or as the verify step of a UI-changing task.

## Checks (in order)

1. **Tree**: does the accessibility tree contain the data the screen claims
   to show? (Empty trees with rendered pixels = lying pixels.)
2. **Pixels**: screenshot and judge layout — truncation, overlap, contrast,
   empty states, disabled states that shouldn't be.
3. **Function**: exercise the primary action when safe and reversible;
   verify the outcome via state, not the button's own label.
4. **State**: re-observe after acting; the UI must reflect reality
   (counts, labels, enabled/disabled).

## Verdicts

- `pass` — all four checks hold.
- `fail` — say which check broke, with the observation as evidence.
- `inconclusive` — what could not be exercised and why.

Evidence first: every "works" claim carries a tree line or a screenshot
reference behind it.
