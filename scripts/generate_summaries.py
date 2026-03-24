#!/usr/bin/env python3
"""
Generate 1-2 line summaries for all Playwright test specs using Azure OpenAI.
Writes results to test_summaries.json (same directory as this script).
Run this when new tests are added, or to refresh summaries. Requires API key in env.

Usage:
  Set env: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
  python generate_summaries.py --repo ../OmegaAI-Mono
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Load .env from script directory so API key etc. are available without setting env each time
_scripts_dir = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(_scripts_dir / ".env")
except ImportError:
    pass  # python-dotenv not installed; use env vars only

# Ensure scripts dir is on path so select_tests can be imported when run from repo root
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from select_tests import _summaries_json_path, discover_playwright_spec_paths, playwright_dir, resolve_repo_path


def call_azure_openai(user_content: str) -> str:
    """Call Azure OpenAI chat completions; return assistant message content."""
    try:
        from openai import AzureOpenAI
    except ImportError:
        print("Error: openai package required. Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

    if not api_key or not endpoint or not deployment:
        print(
            "Error: Set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint.rstrip("/"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    )
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "system",
                "content": "You summarize E2E test files in 1-2 short lines. Reply with only the summary, no preamble.",
            },
            {"role": "user", "content": user_content},
        ],
        max_completion_tokens=512,
    )
    return (response.choices[0].message.content or "").strip()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate test summaries via Azure OpenAI and save to test_summaries.json")
    parser.add_argument("--repo", default="../OmegaAI-Mono", help="Path to OmegaAI-Mono repo root")
    args = parser.parse_args()

    repo_path = resolve_repo_path(args.repo)
    pw_root = playwright_dir(repo_path)
    if not pw_root.is_dir():
        print(f"Error: not a directory: {pw_root}", file=sys.stderr)
        sys.exit(1)

    spec_paths = discover_playwright_spec_paths(repo_path)
    if not spec_paths:
        print(f"Error: no *.spec.js files under {pw_root}", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(spec_paths)} spec file(s) (glob **/*.spec.js).", file=sys.stderr)

    summaries = {}
    for path in spec_paths:
        full_path = pw_root / path
        if not full_path.exists():
            print(f"Warning: skipping missing file: {full_path}", file=sys.stderr)
            summaries[path] = "(file not found)"
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"Warning: could not read {full_path}: {e}", file=sys.stderr)
            summaries[path] = "(read error)"
            continue

        prompt = f"Summarize this E2E test in 1-2 lines (what flow or feature it covers).\n\nFile: {path}\n\n```\n{content[:8000]}\n```"
        print(f"Generating summary for {path}...", file=sys.stderr)
        try:
            summary = call_azure_openai(prompt)
            summaries[path] = summary or "(no summary)"
        except Exception as e:
            print(f"Warning: API failed for {path}: {e}", file=sys.stderr)
            summaries[path] = "(API error)"

    out_path = _summaries_json_path()
    out_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"Wrote {len(summaries)} summaries to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
