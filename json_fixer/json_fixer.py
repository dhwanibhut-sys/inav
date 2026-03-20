import argparse
import json
import sys
import os
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from google import genai
from google.genai import types


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")


class FixResult(BaseModel):
    fixed_json: Optional[Any]
    fixes: List[str]
    status: str


def try_parse_json(content):
    """Quick deterministic check before calling LLM"""
    try:
        return json.loads(content), []
    except Exception:
        return None, ["Input is not valid JSON, attempting repair via LLM"]


def main():
    parser = argparse.ArgumentParser(description="Broken JSON Fixer using Gemini")
    parser.add_argument(
        "input_file",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="File containing broken JSON. Reads from stdin if omitted.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api-key")
    args = parser.parse_args()

    load_env()

    if args.input_file is sys.stdin and sys.stdin.isatty():
        print(
            "Reading from stdin... Enter JSON and press Ctrl-Z (Windows) or Ctrl-D (Unix)",
            file=sys.stderr,
        )

    try:
        content = args.input_file.read()
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    if not content.strip():
        print("Error: Input is empty", file=sys.stderr)
        sys.exit(1)

    # STEP 1: Try normal parsing first
    parsed, pre_fixes = try_parse_json(content)
    if parsed is not None:
        print("Status: Input already valid JSON", file=sys.stderr)
        if not args.dry_run:
            print(json.dumps(parsed, indent=2))
        sys.exit(0)

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Missing GEMINI_API_KEY", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a strict JSON repair tool.

Fix ONLY structural issues:
- missing quotes around keys
- single → double quotes
- trailing commas
- unclosed brackets/braces
- invalid escape sequences

STRICT RULES:
- DO NOT change values
- DO NOT add/remove keys
- DO NOT guess missing data
- If ambiguous → status = "fail"

Return JSON in this format:
{{
  "fixed_json": <valid JSON or null>,
  "fixes": ["short descriptions"],
  "status": "success" or "fail"
}}

INPUT:
{content}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FixResult,
                temperature=0.0,
            ),
        )

        try:
            result = json.loads(response.text)
        except Exception:
            print("LLM returned invalid JSON output", file=sys.stderr)
            sys.exit(1)

        status = result.get("status", "fail")
        fixes = result.get("fixes", [])
        fixed_json = result.get("fixed_json")

        # Extra safety: ensure output is valid JSON
        if fixed_json is not None:
            try:
                json.dumps(fixed_json)
            except Exception:
                print("LLM produced invalid JSON structure", file=sys.stderr)
                sys.exit(1)

        if status != "success" or fixed_json is None:
            print("Failed to fix JSON", file=sys.stderr)
            for f in fixes:
                print(f" - {f}", file=sys.stderr)
            sys.exit(1)

        # Print fixes
        for f in pre_fixes + fixes:
            print(f"Fixed: {f}", file=sys.stderr)

        if not args.dry_run:
            print(json.dumps(fixed_json, indent=2))

    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()