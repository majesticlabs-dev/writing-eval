"""Prompt construction for generation and revision runs."""

from .style_audit import Finding

REVISION_INSTRUCTION = (
    "Revise the following text to eliminate the listed style violations. "
    "Change only the offending spans; preserve meaning, length, and voice. "
    "Return only the revised text."
)


def build_generation_prompt(system_prompt: str, task_prompt: str) -> str:
    return f"{system_prompt}\n\n{task_prompt}"


def format_findings(findings: list[Finding]) -> str:
    lines = []
    for index, finding in enumerate(findings, start=1):
        lines.append(
            f'{index}. [{finding.rule_id}] {finding.message} '
            f'(matched: "{finding.matched_text}")'
        )
    return "\n".join(lines)


def build_revision_prompt(
    system_prompt: str, findings: list[Finding], text: str
) -> str:
    return (
        f"{system_prompt}\n\n{REVISION_INSTRUCTION}\n\n"
        f"{format_findings(findings)}\n\n{text}"
    )
