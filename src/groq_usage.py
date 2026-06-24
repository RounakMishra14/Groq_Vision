"""
groq_usage.py

Small local usage tracker for Groq calls inside the Streamlit app.

Important:
- Groq does not return your full org-level remaining daily quota on every successful call.
- This tracker shows usage made inside the current Streamlit session.
- If Groq returns a 429 rate-limit error, the tracker parses Limit/Used/Requested
  from the error text and helps the UI show a clean user-friendly message.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GroqLimitConfig:
    model_name: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # Free/on-demand limits observed for this model/service tier.
    # Keep editable because Groq can change model/plan limits.
    rpm_limit: int = 30          # requests per minute
    rpd_limit: int = 1000        # requests per day
    tpm_limit: int = 30000       # tokens per minute
    tpd_limit: int = 500000      # tokens per day


@dataclass
class GroqCallUsage:
    timestamp: float
    image_number: int
    file_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_seconds: float
    model: str
    status: str = "success"
    error_message: str = ""


@dataclass
class GroqObservedLimitError:
    limit_type: str = ""
    limit: Optional[int] = None
    used: Optional[int] = None
    requested: Optional[int] = None
    retry_after_text: str = ""
    raw_message: str = ""

    @property
    def remaining_before_request(self) -> Optional[int]:
        if self.limit is None or self.used is None:
            return None
        return max(0, self.limit - self.used)


@dataclass
class GroqUsageTracker:
    limits: GroqLimitConfig = field(default_factory=GroqLimitConfig)
    calls: List[GroqCallUsage] = field(default_factory=list)
    last_limit_error: Optional[GroqObservedLimitError] = None

    def add_success(
        self,
        *,
        image_number: int,
        file_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        duration_seconds: float,
        model: str,
    ) -> None:
        self.calls.append(
            GroqCallUsage(
                timestamp=time.time(),
                image_number=image_number,
                file_name=file_name,
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
                total_tokens=int(total_tokens or 0),
                duration_seconds=float(duration_seconds or 0),
                model=model,
                status="success",
            )
        )

    def add_error(
        self,
        *,
        image_number: int,
        file_name: str,
        error_message: str,
        model: str,
    ) -> None:
        self.calls.append(
            GroqCallUsage(
                timestamp=time.time(),
                image_number=image_number,
                file_name=file_name,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                duration_seconds=0,
                model=model,
                status="error",
                error_message=error_message,
            )
        )
        parsed = parse_groq_rate_limit_error(error_message)
        if parsed.limit_type:
            self.last_limit_error = parsed

    @property
    def total_requests(self) -> int:
        return len([c for c in self.calls if c.status == "success"])

    @property
    def failed_requests(self) -> int:
        return len([c for c in self.calls if c.status == "error"])

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls if c.status == "success")

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls if c.status == "success")

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls if c.status == "success")

    def calls_last_seconds(self, seconds: int) -> List[GroqCallUsage]:
        cutoff = time.time() - seconds
        return [c for c in self.calls if c.timestamp >= cutoff and c.status == "success"]

    @property
    def requests_last_minute(self) -> int:
        return len(self.calls_last_seconds(60))

    @property
    def tokens_last_minute(self) -> int:
        return sum(c.total_tokens for c in self.calls_last_seconds(60))

    @property
    def remaining_session_rpd(self) -> int:
        return max(0, self.limits.rpd_limit - self.total_requests)

    @property
    def remaining_session_tpd(self) -> int:
        return max(0, self.limits.tpd_limit - self.total_tokens)

    @property
    def remaining_session_rpm(self) -> int:
        return max(0, self.limits.rpm_limit - self.requests_last_minute)

    @property
    def remaining_session_tpm(self) -> int:
        return max(0, self.limits.tpm_limit - self.tokens_last_minute)

    def as_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for c in self.calls:
            rows.append(
                {
                    "image_number": c.image_number,
                    "file_name": c.file_name,
                    "status": c.status,
                    "prompt_tokens": c.prompt_tokens,
                    "completion_tokens": c.completion_tokens,
                    "total_tokens": c.total_tokens,
                    "duration_seconds": round(c.duration_seconds, 2),
                    "model": c.model,
                    "error_message": c.error_message,
                }
            )
        return rows


def parse_groq_rate_limit_error(message: str) -> GroqObservedLimitError:
    """
    Parses Groq 429 text like:
    "Rate limit reached ... on tokens per day (TPD): Limit 500000, Used 498034, Requested 2832. Please try again in 2m29.6448s."
    """
    msg = str(message or "")
    observed = GroqObservedLimitError(raw_message=msg)

    type_match = re.search(r"\((TPD|TPM|RPM|RPD)\)", msg, flags=re.IGNORECASE)
    if type_match:
        observed.limit_type = type_match.group(1).upper()

    limit_match = re.search(
        r"Limit\s+([0-9,]+),\s*Used\s+([0-9,]+),\s*Requested\s+([0-9,]+)",
        msg,
        flags=re.IGNORECASE,
    )
    if limit_match:
        observed.limit = int(limit_match.group(1).replace(",", ""))
        observed.used = int(limit_match.group(2).replace(",", ""))
        observed.requested = int(limit_match.group(3).replace(",", ""))

    retry_match = re.search(
        r"Please try again in\s+([^\.]+(?:\.\d+)?s)",
        msg,
        flags=re.IGNORECASE,
    )
    if retry_match:
        observed.retry_after_text = retry_match.group(1)

    return observed


def build_friendly_groq_error_message(error_message: str) -> str:
    """
    Convert raw Groq/Python exceptions into a clean UI message.
    This deliberately avoids tracebacks and internal file paths.
    """
    msg = str(error_message or "")
    observed = parse_groq_rate_limit_error(msg)

    if observed.limit_type:
        parts = [f"Groq rate limit reached: {observed.limit_type}."]

        if observed.limit is not None:
            parts.append(f"Limit: {observed.limit:,}.")
        if observed.used is not None:
            parts.append(f"Used: {observed.used:,}.")
        if observed.requested is not None:
            parts.append(f"Requested by next image: {observed.requested:,}.")
        if observed.remaining_before_request is not None:
            parts.append(f"Remaining before this request: {observed.remaining_before_request:,}.")
        if observed.retry_after_text:
            parts.append(f"Try again after {observed.retry_after_text}.")

        parts.append("Partial results are kept and can still be downloaded.")
        return " ".join(parts)

    lower_msg = msg.lower()

    if "api_key" in lower_msg or "groq_api_key" in lower_msg:
        return "Groq API key is missing or invalid. Check your .env file and GROQ_API_KEY value."

    if "connection" in lower_msg or "timeout" in lower_msg:
        return "Groq request failed because of a network/timeout issue. Partial results are kept if available."

    return "Groq request failed. Partial results are kept if available. Check your API key, network, or Groq quota."
