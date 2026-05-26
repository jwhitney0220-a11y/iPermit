"""Response envelope and RFC-9457 problem-details (S01-03, ADR-0003).

Every permit-bearing response is wrapped so the mandatory liability fields
(advisories, confidence, citations) cannot be dropped by a client. The standing
platform advisory (T00-05 §4.4) is ALWAYS present at the envelope level — a
permit response with zero advisories is a contract violation (ADR-0003).

Errors are separate from advisories: failures use the RFC-9457
``application/problem+json`` shape; an uncertain-but-valid result never becomes
an HTTP error (ADR-0003 *Error and advisory response structure*).
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"

#: Standing platform disclaimer, verbatim from T00-05 §4.4. Always present at the
#: envelope level on permit-bearing responses.
PLATFORM_ADVISORY: dict[str, str] = {
    "text": (
        "Advisory only; not a legal determination. Professional review and"
        " agency confirmation are required before submission."
    ),
    "origin": "platform",
    "category": "advisory_disclaimer",
}

T = TypeVar("T")


class Advisory(BaseModel):
    """One advisory notice (T00-05 §4.3 categories)."""

    text: str
    origin: str
    category: str


class Meta(BaseModel):
    """Envelope metadata: the reproducibility triple + cross-references."""

    ruleset_version: dict[str, Any]
    evaluation_date: str
    evaluation_mode: str = "live"
    evaluation_id: str | None = None
    schema_version: str = "1.0.0"


class Envelope(BaseModel, Generic[T]):
    """The ADR-0003 response envelope: ``{data, meta, advisories, warnings}``."""

    data: T
    meta: Meta
    advisories: list[Advisory] = Field(default_factory=list)
    warnings: list[Advisory] = Field(default_factory=list)


class Problem(BaseModel):
    """RFC-9457 problem-details body."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[dict[str, Any]] | None = None


class ProblemException(Exception):
    """Raise to return an RFC-9457 problem-details error response."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        *,
        type_: str = "about:blank",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.problem = Problem(
            type=type_, title=title, status=status, detail=detail, errors=errors
        )
        super().__init__(title)


def _response(problem: Problem, instance: str) -> JSONResponse:
    """Render a Problem as an ``application/problem+json`` response."""
    problem.instance = problem.instance or instance
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_CONTENT_TYPE,
    )


async def problem_exception_handler(
    request: Request, exc: ProblemException
) -> JSONResponse:
    """Handle explicitly raised :class:`ProblemException`."""
    return _response(exc.problem, str(request.url))


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Map FastAPI/Starlette HTTPException to problem-details."""
    problem = Problem(title=str(exc.detail), status=exc.status_code)
    return _response(problem, str(request.url))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map request-validation failures to a 422 problem with ``errors[]``."""
    problem = Problem(
        title="Request validation failed",
        status=422,
        detail="One or more request fields are invalid.",
        errors=[dict(e) for e in exc.errors()],
    )
    return _response(problem, str(request.url))


def register_exception_handlers(app: Any) -> None:
    """Install the problem-details handlers on a FastAPI app."""
    app.add_exception_handler(ProblemException, problem_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
