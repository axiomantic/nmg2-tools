# Empty-population fixture — the removed-mechanism lint

This document carries NO task block at all. The lint therefore examines zero
`Check:` blocks, and `guard_no_input` turns that into a hard error rather than
into a clean run. Nothing to check is never a pass.

## 9. The tasks

There are none. A `Check:` line written here belongs to no task block, and a
task an `assert()` names is a task this document does not define.
