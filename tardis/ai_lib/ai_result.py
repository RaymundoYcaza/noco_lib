"""AIResult — universal return contract for AI operations.

Every public function in ``ai_lib`` MUST return an ``AIResult``
instance, mirroring the ``NocoResult`` pattern from ``noco_lib``.
This ensures consistent error handling and introspection across
the project.
"""

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AIResult:
    """Result of an AI operation (correct, classify, extract, summarize).

    Parameters
    ----------
    success : bool
        Whether the operation completed without errors.
    operation : str
        The operation that was attempted: ``"correct"`` | ``"classify"`` |
        ``"extract"`` | ``"summarize"``.
    data : Any
        The structured AI response: ``str``, ``list``, or ``dict``.
    errors : list[str]
        Human-readable error messages, empty on success.
    meta : dict
        Metadata from the AI provider: ``model``, ``provider``,
        ``prompt_tokens``, ``completion_tokens``, ``latency_ms``.
    """

    success: bool
    operation: str
    data: Any = None
    errors: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    # ── Serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a plain dict representation of this result."""
        return asdict(self)

    # ── Factory class methods ────────────────────────────────────────

    @classmethod
    def ok(
        cls,
        operation: str,
        data: Any = None,
        meta: dict | None = None,
    ) -> "AIResult":
        """Create a successful result.

        Parameters
        ----------
        operation : str
            The operation that succeeded.
        data : Any, optional
            The AI's structured response.
        meta : dict, optional
            Provider metadata (model, provider, tokens, latency).

        Returns
        -------
        AIResult
            ``success=True``, ``errors=[]``.
        """
        return cls(
            success=True,
            operation=operation,
            data=data,
            errors=[],
            meta=meta or {},
        )

    @classmethod
    def fail(
        cls,
        operation: str,
        errors: str | list[str],
        meta: dict | None = None,
    ) -> "AIResult":
        """Create a failed result.

        Parameters
        ----------
        operation : str
            The operation that failed.
        errors : str | list[str]
            One or more human-readable error messages.  A single string
            is automatically wrapped in a list.
        meta : dict, optional
            Provider metadata (model, provider, tokens, latency).

        Returns
        -------
        AIResult
            ``success=False``, ``data=None``.
        """
        if isinstance(errors, str):
            errors = [errors]
        return cls(
            success=False,
            operation=operation,
            data=None,
            errors=errors,
            meta=meta or {},
        )
