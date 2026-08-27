"""Findings and lint results.

Exit codes are stated once, here, because the project measured what a silent
zero costs: `ctest -R` exits 0 when its pattern matches no test, so a check can
report PASS against no code. A lint therefore reports a hard error when it finds
no input to examine. Nothing to check is never a pass.
"""

import dataclasses

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"

SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

# The flag a collapsed report names as the way back to every line. It lives
# here, beside the code that PRINTS it, and `cli` registers the same constant
# as the argument's name, so the sentence the reader acts on cannot name a flag
# the parser does not accept.
RECOVERY_FLAG = "--full-warnings"


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    message: str
    task: str = ""
    section: str = ""
    line: int = 0
    evidence: str = ""
    severity: str = ERROR


@dataclasses.dataclass
class LintResult:
    name: str
    findings: list
    examined: int
    examined_label: str = "inputs"
    notice: str = ""
    """A line printed under the report, on a clean run as well as a dirty one.

    It carries what the run's own findings cannot say: which of the checks a
    lint OWES its reader it actually decided. A report silent about a check
    reads exactly like one in which that check passed, and `cli` already
    applies that reasoning one level up to a lint the default run leaves out.

    A notice changes the report's WORDING and never `failed`. Scoring it would
    change what `if planlint; then` means for every existing caller, which is a
    separate decision from making a gap visible.
    """

    @property
    def failed(self):
        """Any finding fails the run. Severity orders the report; it never
        excuses a finding from the exit code."""
        return bool(self.findings)

    def collapsible(self):
        """The findings a collapsed report prints as a count, in report order.

        ERROR is never collapsed. The measured reason is one direction only:
        three WARNING rules produced 573 of one run's 667 warnings, and the
        ERRORs that named a check which could not fail sat unread under them
        for months. Collapsing the other direction would hide the finding the
        report exists to deliver.
        """
        return [f for f in self.findings if f.severity != ERROR]

    def collapsed_counts(self):
        """`[(severity, rule, count)]` for the collapsible findings.

        This is what a collapsed report PRINTS, derived from the findings and
        from nothing else. It is a separate method so a test can compare the
        rendered summary against a count taken from the rendered full report,
        with neither side computed from the other.
        """
        counts = {}
        for f in self.collapsible():
            key = (f.severity, f.rule)
            counts[key] = counts.get(key, 0) + 1
        return [
            (severity, rule, counts[(severity, rule)])
            for severity, rule in sorted(
                counts, key=lambda k: (SEVERITY_ORDER[k[0]], k[1])
            )
        ]

    def report(self, full=True, recovery=RECOVERY_FLAG):
        """A human-readable report: task, section, evidence, and the rule.

        `full` prints every finding, and is the default so that every existing
        caller of this method keeps the report it already gets. `full=False`
        prints every ERROR unchanged and collapses each lower severity to one
        line per rule carrying its count.

        A collapsed block NAMES `recovery`, the flag that prints the lines it
        did not. A reader who cannot see how to expand is looking at
        suppression whatever the code calls it.

        Collapsing changes the report's WORDING and never `failed`. Scoring it
        would change what `if planlint; then` means for every existing caller,
        which is a separate decision from making the report readable — the
        same reasoning `cli` applies to a lint the default run leaves out.
        """
        tail = f"  {self.notice}\n" if self.notice else ""
        if not self.findings:
            return (
                f"{self.name}: clean ({self.examined} {self.examined_label} "
                f"examined)\n{tail}"
            )
        head = (
            f"{self.name}: {len(self.findings)} finding(s) "
            f"({self.examined} {self.examined_label} examined)\n"
        )
        collapsed = [] if full else self.collapsible()
        # The two halves partition `findings` by the SAME predicate
        # `collapsible` uses, so a finding cannot fall out of both. Filtering
        # by identity against the collapsed list would not: `Finding` is a
        # frozen dataclass, so two findings that differ in no field are equal,
        # and one of a duplicated pair would be dropped from the report
        # entirely.
        printed = self.findings if full else [
            f for f in self.findings if f.severity == ERROR
        ]
        body = []
        for f in sorted(
            printed, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule, f.task, f.line)
        ):
            head_parts = [f"  [{f.severity}] {f.rule}"]
            if f.task:
                head_parts.append(f.task)
            if f.line:
                head_parts.append(f"line {f.line}")
            body.append("  ".join(head_parts))
            if f.section:
                body.append(f"      section: {f.section}")
            body.append(f"      {f.message}")
            if f.evidence:
                body.append(f"      evidence: {f.evidence}")
        if collapsed:
            body.append(
                f"  collapsed to one line per rule; {recovery} prints every one:"
            )
            for severity, rule, count in self.collapsed_counts():
                body.append(f"    [{severity}] {rule}  {count}")
        return head + "\n".join(body) + "\n" + tail


def guard_no_input(name, findings, examined, label, noun, notice=""):
    """Turn 'nothing to check' into a hard error, never a pass."""
    if examined == 0:
        findings = list(findings) + [
            Finding(
                rule="no-input",
                message=f"the {noun} examined 0 {label}",
                severity=ERROR,
            )
        ]
    return LintResult(
        name=name,
        findings=findings,
        examined=examined,
        examined_label=label,
        notice=notice,
    )
