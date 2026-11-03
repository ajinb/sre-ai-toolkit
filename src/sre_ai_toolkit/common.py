"""Shared plumbing for every toolkit script: CLI controls, the Claude call, usage reporting.

Every script gets the same flags (``add_common_args``) and makes its model call
through ``ask``, so model choice, effort, timeouts, dry runs, refusal handling
and the end-of-run token/cost line behave identically across the toolkit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
EFFORTS = ("low", "medium", "high", "xhigh", "max")

# Models that accept the server-side ``fallbacks: "default"`` route.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"}

# USD per 1M tokens (input, output, cache-read multiplier) for the end-of-run
# estimate. `cloudandsre.cost` is the maintained table and is used when it is
# installed; this fallback covers the current lineup only.
_PRICES = {
    "claude-fable-5-1": (10.00, 50.00, 0.025),
    "claude-opus-5-5": (4.00, 20.00, 0.05),
    "claude-opus-5": (5.00, 25.00, 0.10),
    "claude-opus-4-8": (5.00, 25.00, 0.10),
    "claude-sonnet-5-5": (2.00, 10.00, 0.05),
    "claude-sonnet-5": (2.00, 10.00, 0.10),
    "claude-sonnet-4-6": (3.00, 15.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.10),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}


class ToolkitError(RuntimeError):
    """A model call finished without a usable answer (refusal, truncation)."""


def add_common_args(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group("model controls")
    g.add_argument(
        "--model",
        default=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        help=f"Claude model (default: $ANTHROPIC_MODEL or {DEFAULT_MODEL})",
    )
    g.add_argument(
        "--effort",
        choices=EFFORTS,
        default=os.environ.get("SRE_AI_EFFORT", DEFAULT_EFFORT),
        help=f"Thinking depth (default: $SRE_AI_EFFORT or {DEFAULT_EFFORT})",
    )
    g.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.environ.get("SRE_AI_MAX_TOKENS", "16000")),
        help="Output cap per call, thinking included (default: 16000)",
    )
    g.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("SRE_AI_TIMEOUT", "120")),
        help="Request timeout in seconds (default: 120)",
    )
    g.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request that would be sent, then exit without calling the API",
    )
    g.add_argument(
        "--no-usage", action="store_true", help="Do not print the token/cost summary to stderr"
    )


def _price(model: str) -> tuple[float, float, float] | None:
    for prefix in sorted(_PRICES, key=len, reverse=True):
        if model.startswith(prefix):
            return _PRICES[prefix]
    return None


def estimate_usd(model: str, usage: Any) -> float | None:
    try:
        from cloudandsre.cost import cost_for_message  # optional, maintained table

        return float(cost_for_message(_Msg(model, usage))["usd"])
    except ImportError:
        pass
    price = _price(model)
    if price is None:
        return None
    inp, out, cache_mult = price
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    return (
        usage.input_tokens * inp
        + cache_read * inp * cache_mult
        + cache_write * inp * 1.25
        + usage.output_tokens * out
    ) / 1_000_000


class _Msg:
    def __init__(self, model: str, usage: Any) -> None:
        self.model, self.usage = model, usage


def usage_line(message: Any) -> str:
    u = message.usage
    cache_read = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    usd = estimate_usd(message.model, u)
    cost = f" · est. ${usd:.4f}" if usd is not None else ""
    cached = f" (+{cache_read:,} cached)" if cache_read else ""
    return f"[usage] {message.model}: {u.input_tokens:,} in{cached}, {u.output_tokens:,} out{cost}"


def ask(
    args: argparse.Namespace,
    *,
    system: str,
    user: str,
    json_schema: dict | None = None,
    client: anthropic.Anthropic | None = None,
) -> str:
    """One Claude call honouring the common flags. Returns the reply text ('' on --dry-run)."""
    output_config: dict[str, Any] = {"effort": args.effort}
    if json_schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": json_schema}
    request: dict[str, Any] = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": output_config,
    }

    if args.dry_run:
        print(json.dumps(request, indent=2))
        return ""

    if args.model in _FALLBACK_MODELS:
        request |= {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

    client = client or anthropic.Anthropic(timeout=args.timeout)
    message = client.beta.messages.create(**request)

    if not getattr(args, "no_usage", False):
        print(usage_line(message), file=sys.stderr)

    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None)
        raise ToolkitError(f"the model declined this request (category={category})")
    text = "".join(block.text for block in message.content if block.type == "text")
    if message.stop_reason == "max_tokens":
        raise ToolkitError(
            f"reply hit --max-tokens={args.max_tokens} before finishing; raise it or lower --effort"
        )
    return text


def run(main_fn) -> None:
    """Entry-point wrapper: friendly one-line errors and distinct exit codes."""
    try:
        main_fn()
    except ToolkitError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(4)
    except anthropic.AuthenticationError:
        print("error: Anthropic authentication failed; set ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(4)
    except anthropic.APIError as e:
        print(f"error: Claude API: {e}", file=sys.stderr)
        sys.exit(4)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
