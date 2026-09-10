"""Provider-neutral context budgeting and handoff compaction.

The :mod:`sisyphusfy.context` module owns three things:

1. A deterministic, documented prompt-size estimate that Sisyphusfy
   records on every run. The estimate is intentionally cheap and
   provider-neutral; adapters that know their tokeniser may override
   the recorded usage with exact numbers.
2. A configurable :class:`ContextBudget` with two policies
   (``"reject"`` and ``"truncate"``). When set, the loop applies the
   policy before invoking the agent and records the outcome in the
   :class:`ContextTelemetry` carried by the :class:`~sisyphusfy.loop.LoopResult`.
3. A bounded :class:`HandoffDocument` plus :class:`HandoffCompactor`.
   Compaction rewrites only the configured handoff file through an
   explicit operation; it never silently deletes arbitrary project
   history.

The estimate is byte-counted against a public ``chars/4`` heuristic and
labelled with its measurement method so downstream consumers can tell
estimates from adapter-supplied exact usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

ESTIMATION_METHOD = "chars/4"


def estimate_text(text: str, method: str = ESTIMATION_METHOD) -> ContextEstimate:
    """Return a deterministic, provider-neutral estimate for ``text``.

    The default heuristic is ``chars/4``; it is conservative for English
    prose and labelled so the recorded estimate can never be confused
    with billing totals.
    """
    chars = len(text)
    if method == "chars/4":
        tokens = chars // 4
    elif method == "words*1.3":
        tokens = int(len(text.split()) * 1.3)
    else:
        tokens = chars // 4
    return ContextEstimate(
        chars=chars,
        tokens_estimated=max(tokens, 0),
        measurement_method=method,
    )


class BudgetPolicy(str, Enum):
    REJECT = "reject"
    TRUNCATE = "truncate"


@dataclass(frozen=True)
class ContextBudget:
    """A configurable input budget for the agent prompt.

    ``max_input_tokens`` is the soft cap on the rendered prompt plus
    selected recovery material. ``policy`` selects what happens when
    the cap is exceeded:

    - ``"reject"`` stops the run before the agent is invoked and
      records ``budget_event = "rejected"`` on the telemetry.
    - ``"truncate"`` applies a documented bounded reduction and
      records ``budget_event = "truncated"``.

    ``max_handoff_chars`` is an optional hard cap on the handoff body
    included in the prompt; a handoff that exceeds it is summarised
    with a marker so the agent still receives a usable summary.
    """

    max_input_tokens: int
    policy: BudgetPolicy = BudgetPolicy.REJECT
    max_handoff_chars: int | None = None


@dataclass(frozen=True)
class ContextEstimate:
    chars: int
    tokens_estimated: int
    measurement_method: str

    def to_dict(self) -> dict:
        return {
            "chars": self.chars,
            "tokens_estimated": self.tokens_estimated,
            "measurement_method": self.measurement_method,
        }


@dataclass(frozen=True)
class ExactUsage:
    """Adapter-supplied exact usage.

    Adapters that know the provider's tokeniser may attach one of
    these to the run record. The core never fabricates a value.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "is_estimate": False,
        }


@dataclass
class ContextTelemetry:
    """Cumulative telemetry tracked for a single run.

    Every iteration records its :class:`ContextEstimate`; the run as a
    whole carries totals plus the latest :class:`ExactUsage` (if the
    adapter supplied one) and any budget event.
    """

    iterations: list[ContextEstimate] = field(default_factory=list)
    exact_usage: ExactUsage | None = None
    budget: ContextBudget | None = None
    budget_event: str | None = None

    @property
    def estimated_total_input_tokens(self) -> int:
        return sum(e.tokens_estimated for e in self.iterations)

    def record(
        self,
        estimate: ContextEstimate,
        *,
        exact: ExactUsage | None = None,
    ) -> None:
        self.iterations.append(estimate)
        if exact is not None:
            self.exact_usage = exact

    def to_dict(self) -> dict:
        d: dict = {
            "estimated_total_input_tokens": self.estimated_total_input_tokens,
            "iterations": [e.to_dict() for e in self.iterations],
        }
        if self.exact_usage is not None:
            d["exact_usage"] = self.exact_usage.to_dict()
        if self.budget is not None:
            d["budget"] = {
                "max_input_tokens": self.budget.max_input_tokens,
                "policy": self.budget.policy.value,
            }
        if self.budget_event is not None:
            d["budget_event"] = self.budget_event
        return d


class HandoffSection(str, Enum):
    COMPLETED = "completed"
    CURRENT_STATE = "current_state"
    BLOCKERS = "blockers"
    NEXT_ACTION = "next_action"
    RELEVANT_FILES = "relevant_files"
    VERIFICATION = "verification"


@dataclass
class _RawSection:
    title: str
    body: str


@dataclass
class HandoffDocument:
    """A bounded structured handoff document.

    The :class:`HandoffDocument` parses the sectioned Markdown written
    by the agent, exposes the per-section body, and supports a
    deterministic clamp used by the compactor.
    """

    sections: dict[HandoffSection, str] = field(default_factory=dict)
    _order: list[HandoffSection] = field(default_factory=list)

    @classmethod
    def from_markdown(cls, text: str) -> HandoffDocument:
        sections: dict[HandoffSection, str] = {}
        order: list[HandoffSection] = []
        current_title: str | None = None
        current_body: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                if current_title is not None:
                    body = "\n".join(current_body).strip()
                    section = _title_to_section(current_title)
                    if section is not None:
                        sections[section] = body
                        order.append(section)
                current_title = stripped[3:].strip()
                current_body = []
            else:
                current_body.append(line)
        if current_title is not None:
            body = "\n".join(current_body).strip()
            section = _title_to_section(current_title)
            if section is not None:
                sections[section] = body
                order.append(section)
        return cls(sections=sections, _order=order)

    def get(self, section: HandoffSection) -> str | None:
        return self.sections.get(section)

    def clamp(self, *, max_chars_per_section: int) -> HandoffDocument:
        new_sections: dict[HandoffSection, str] = {}
        for section, body in self.sections.items():
            if len(body) > max_chars_per_section:
                kept = body[:max_chars_per_section]
                new_sections[section] = (
                    f"{kept}\n\n[handoff section truncated at "
                    f"{max_chars_per_section} chars]"
                )
            else:
                new_sections[section] = body
        return HandoffDocument(sections=new_sections, _order=list(self._order))

    def to_markdown(self) -> str:
        lines: list[str] = []
        for section in self._order:
            body = self.sections.get(section, "")
            lines.append(f"## {section_to_title(section)}")
            lines.append("")
            lines.append(body)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def _title_to_section(title: str) -> HandoffSection | None:
    normalised = title.strip().lower().replace(" ", "_")
    for section in HandoffSection:
        if section.value == normalised:
            return section
    return None


def section_to_title(section: HandoffSection) -> str:
    """Return the canonical ``## Title`` heading for a section."""
    return {
        HandoffSection.COMPLETED: "Completed",
        HandoffSection.CURRENT_STATE: "Current state",
        HandoffSection.BLOCKERS: "Blockers",
        HandoffSection.NEXT_ACTION: "Next action",
        HandoffSection.RELEVANT_FILES: "Relevant files",
        HandoffSection.VERIFICATION: "Verification",
    }[section]


@dataclass
class HandoffCompactionResult:
    compacted: bool
    before_chars: int
    after_chars: int
    sections_clamped: int

    def to_dict(self) -> dict:
        return {
            "compacted": self.compacted,
            "before_chars": self.before_chars,
            "after_chars": self.after_chars,
            "sections_clamped": self.sections_clamped,
        }


@dataclass
class HandoffCompactor:
    """Bound the configured handoff file through an explicit operation."""

    max_chars_per_section: int = 4000
    max_total_chars: int = 16_000

    def compact(self, handoff_path: str | Path) -> HandoffCompactionResult:
        path = Path(handoff_path)
        if not path.exists():
            return HandoffCompactionResult(
                compacted=False,
                before_chars=0,
                after_chars=0,
                sections_clamped=0,
            )
        original = path.read_text()
        doc = HandoffDocument.from_markdown(original)
        clamped_sections = 0
        for section, body in list(doc.sections.items()):
            if len(body) > self.max_chars_per_section:
                clamped_sections += 1
        clamped = doc.clamp(max_chars_per_section=self.max_chars_per_section)
        rewritten = clamped.to_markdown()
        if len(rewritten) > self.max_total_chars:
            rewritten = rewritten[: self.max_total_chars] + (
                f"\n\n[handoff truncated at {self.max_total_chars} chars]"
            )
        path.write_text(rewritten)
        return HandoffCompactionResult(
            compacted=clamped_sections > 0 or len(rewritten) < len(original),
            before_chars=len(original),
            after_chars=len(rewritten),
            sections_clamped=clamped_sections,
        )


def apply_budget_to_prompt(
    prompt: str,
    budget: ContextBudget,
) -> tuple[str, str | None]:
    """Apply a configured budget to ``prompt`` and return the body + event.

    Returns the possibly-truncated prompt and the budget event
    (``"rejected"``, ``"truncated"``, or ``None``). When the policy is
    ``"reject"`` and the prompt is over budget, the returned prompt is
    the original (so the caller can decide what to do) and the event
    is ``"rejected"``; the caller is responsible for stopping the
    invocation.
    """
    estimate = estimate_text(prompt)
    if estimate.tokens_estimated <= budget.max_input_tokens:
        return prompt, None
    policy = budget.policy
    if isinstance(policy, str):
        try:
            policy = BudgetPolicy(policy)
        except ValueError:
            policy = BudgetPolicy.REJECT
    if policy is BudgetPolicy.REJECT:
        return prompt, "rejected"
    max_chars = budget.max_input_tokens * 4
    return prompt[:max_chars] + (
        f"\n\n[prompt truncated at {max_chars} chars by context budget]"
    ), "truncated"
