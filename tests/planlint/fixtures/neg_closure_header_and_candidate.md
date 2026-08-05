# A header outside the closure, and a hedged consumption

The two halves of the ninth lint that the three historical fixtures do not
carry: a `#include` of a header another task creates, and a consumption whose
sentence HEDGES.

A hedged sentence is the recall bucket. `does not link`, `cannot`, `behind an
option` and `the previous revision` all describe a consumption that may not be
one, so the lint reports the row as a CANDIDATE for a human to adjudicate
instead of asserting a violation.

DDD-1 is the control. It declares AAA-1 and consumes the same three names, and
no rule may report it.

## 9. The tasks

**AAA-1 · The alpha surface** — T0
Files: `g2Lib/alpha.h`, `g2Lib/alpha.cpp`, targets `alpha_lib`
Design: 1
Depends: none
Check: It exports `alpha::alpha_lib`, and `g2Lib/alpha.h` declares `Alpha::Config`.

**BBB-1 · The unreachable include** — T0
Files: `g2Lib/beta.cpp`
Design: 2
Depends: none
Check: The translation unit carries `#include "alpha.h"` and reads `Alpha::Config`.

**CCC-1 · The hedged consumption** — T0
Files: `g2Lib/delta.cpp`
Design: 3
Depends: none
Check: This task does not link `alpha::alpha_lib`. It links `hardwareLib`, which no task in this plan creates.

**DDD-1 · The control** — T0
Files: `g2Lib/epsilon.cpp`
Design: 4
Depends: AAA-1
Check: The translation unit carries `#include "alpha.h"`, links `alpha::alpha_lib` and reads `Alpha::Config`.
