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

    def report(self):
        """A human-readable report: task, section, evidence, and the rule."""
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
        body = []
        for f in sorted(
            self.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule, f.task, f.line)
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
