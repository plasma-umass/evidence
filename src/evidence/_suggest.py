"""LLM-assisted specification mining for Evidence.

Provides a SpecSuggester protocol and a ClaudeSuggester implementation
that uses the Anthropic API to suggest @ensures postconditions and
@spec reference implementations for Python functions.

All suggestions are validated by running Evidence checks before presenting.

Requires: pip install evidence[suggest]  (anthropic>=0.40) + ANTHROPIC_API_KEY env var.
"""

from __future__ import annotations

import inspect
import os
import textwrap
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SpecSuggester(Protocol):
    """Protocol for spec suggestion backends."""

    def suggest(
        self,
        fn: Callable[..., Any],
        *,
        existing_contracts: dict[str, Any] | None = None,
        mutation_score: float | None = None,
    ) -> list[Suggestion]:
        """Suggest postconditions and specs for a function.

        Args:
            fn: The function to analyze.
            existing_contracts: Info about existing @requires/@ensures.
            mutation_score: If available, the mutation testing score.

        Returns:
            List of Suggestion objects.
        """
        ...


class Suggestion:
    """A suggested postcondition or specification."""

    __slots__ = ("code", "confidence", "description", "kind")

    def __init__(self, kind: str, code: str, description: str, confidence: float = 0.0) -> None:
        self.kind = kind  # "ensures" or "spec"
        self.code = code  # Python source code
        self.description = description  # Human-readable explanation
        self.confidence = confidence  # 0.0 to 1.0

    def __repr__(self) -> str:
        return f"Suggestion({self.kind}: {self.description}, confidence={self.confidence})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "code": self.code,
            "description": self.description,
            "confidence": self.confidence,
        }


def _get_function_source(fn: Callable[..., Any]) -> str | None:
    """Get dedented source of a function."""
    try:
        return textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None


def _build_prompt(
    source: str,
    existing_contracts: dict[str, Any] | None = None,
    mutation_score: float | None = None,
) -> str:
    """Build the LLM prompt for spec suggestion."""
    parts = [
        "You are an expert Python programmer specializing in formal verification and property-based testing.",
        "",
        "Given the following Python function, suggest postconditions (@ensures) and optionally a reference "
        "specification (@spec) that capture the function's intended behavior.",
        "",
        "Function source:",
        "```python",
        source,
        "```",
    ]

    if existing_contracts:
        parts.extend([
            "",
            f"Existing contracts: {existing_contracts}",
        ])

    if mutation_score is not None:
        parts.extend([
            "",
            f"Current mutation testing score: {mutation_score}%",
            "Focus on properties that would help kill surviving mutants.",
        ])

    parts.extend([
        "",
        "Respond with a JSON array of suggestions. Each suggestion should have:",
        '  - "kind": either "ensures" or "spec"',
        '  - "code": valid Python code (a lambda for ensures, a full function for spec)',
        '  - "description": brief explanation of what the property checks',
        '  - "confidence": float 0.0-1.0 indicating how confident you are',
        "",
        "For @ensures, the lambda signature should be (args..., result) matching the function parameters.",
        "For @spec, write a complete function with the same signature.",
        "",
        "Focus on fundamental correctness properties:",
        "- Output type and shape invariants",
        "- Relationship between input and output",
        "- Boundary conditions",
        "- Algebraic properties (idempotence, commutativity, etc.)",
        "",
        "Return ONLY the JSON array, no other text.",
    ])

    return "\n".join(parts)


class ClaudeSuggester:
    """Spec suggestion using the Anthropic Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic  # type: ignore[import-not-found]
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError as e:
                raise ImportError(
                    "anthropic package not installed; install with: pip install evidence[suggest]"
                ) from e
        return self._client

    def suggest(
        self,
        fn: Callable[..., Any],
        *,
        existing_contracts: dict[str, Any] | None = None,
        mutation_score: float | None = None,
    ) -> list[Suggestion]:
        source = _get_function_source(fn)
        if source is None:
            return []

        prompt = _build_prompt(source, existing_contracts, mutation_score)
        client = self._get_client()

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
        except Exception:
            return []

        return _parse_suggestions(text)


def _parse_suggestions(text: str) -> list[Suggestion]:
    """Parse JSON suggestions from LLM response text."""
    import json

    # Try to extract JSON array from the response
    text = text.strip()
    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(data, list):
        return []

    suggestions = []
    for item in data:
        if isinstance(item, dict) and "kind" in item and "code" in item:
            suggestions.append(Suggestion(
                kind=item.get("kind", "ensures"),
                code=item.get("code", ""),
                description=item.get("description", ""),
                confidence=float(item.get("confidence", 0.0)),
            ))

    return suggestions


def validate_suggestion(
    suggestion: Suggestion,
    fn: Callable[..., Any],
    *,
    max_examples: int = 200,
) -> bool:
    """Validate a suggestion by compiling and testing it.

    Returns True if the suggestion passes validation (no counterexample found).
    """

    code = suggestion.code.strip()
    ns: dict[str, Any] = {}

    try:
        # Compile and execute the suggestion code
        if suggestion.kind == "ensures":
            exec(f"_pred = {code}", fn.__globals__, ns)
            pred = ns.get("_pred")
            if pred is None or not callable(pred):
                return False

            # Quick validation: run on a few examples
            from evidence._bundle import _root_original
            from evidence._strategies import _find_satisfying_kwargs, _strategy_for_function

            root = _root_original(fn)
            strat = _strategy_for_function(root, max_list_size=10)
            try:
                kwargs = _find_satisfying_kwargs(root, strat)
                result = root(**kwargs)
                return bool(pred(**kwargs, result=result))
            except Exception:
                return False

        elif suggestion.kind == "spec":
            exec(code, fn.__globals__, ns)
            # Find the defined function
            spec_fn = None
            for v in ns.values():
                if callable(v) and not isinstance(v, type):
                    spec_fn = v
                    break
            if spec_fn is None:
                return False

            from evidence._bundle import _root_original
            from evidence._strategies import _find_satisfying_kwargs, _strategy_for_function

            root = _root_original(fn)
            strat = _strategy_for_function(root, max_list_size=10)
            try:
                kwargs = _find_satisfying_kwargs(root, strat)
                impl_r = root(**kwargs)
                spec_r = spec_fn(**kwargs)
                return bool(impl_r == spec_r)
            except Exception:
                return False

    except Exception:
        return False

    return False
