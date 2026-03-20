import argparse
import json
import sys
import os
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from google import genai
from google.genai import types

class FixResult(BaseModel):
    fixed_json: Optional[Any] = Field(description="The successfully parsed JSON object, strictly matching the intent of the input. Null if unable to fix.")
    fixes: List[str] = Field(description="A list of short string descriptions of each structural fix applied (e.g. 'Added missing double quotes around keys'). Empty if no fixes were needed.")
    status: str = Field(description="Must be 'success' if the JSON was successfully repaired, or 'fail' if it was hopelessly broken/ambiguous.")

def main():
    parser = argparse.ArgumentParser(description="Broken JSON Fixer using Gemini")
    parser.add_argument("input_file", nargs="?", type=argparse.FileType("r"), default=sys.stdin, help="File containing broken JSON. Reads from stdin if omitted.")
    parser.add_argument("--dry-run", action="store_true", help="Show fix summary without outputting the JSON")
    args = parser.parse_args()

    # If reading from stdin and it's an interactive terminal, we prompt nicely.
    if args.input_file is sys.stdin and sys.stdin.isatty():
        print("Reading from stdin... Enter broken JSON and press Ctrl-Z (then Enter) on Windows (or Ctrl-D on Unix) when done.", file=sys.stderr)

    try:
        content = args.input_file.read()
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    if not content.strip():
        print("Error: Input is empty", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set. Please set it to use the tool.", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a strict JSON repair tool.
Your job is to fix BROKEN JSON with MINIMAL changes.

RULES:
- Only fix STRUCTURAL issues:
  - add missing quotes around keys
  - convert single quotes to double quotes
  - remove trailing commas
  - close missing brackets/braces
  - fix invalid escape characters
- DO NOT change any values
- DO NOT add, remove, or rename keys
- DO NOT guess missing data
- If the input is truncated, attempt to complete it based on apparent structure if obvious.
- If the input is too broken or ambiguous -> return status = "fail"

INPUT:
<<<
{content}
>>>
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FixResult,
                temperature=0.0
            ),
        )
        
        # Parse the structured response
        result = json.loads(response.text)
        status = result.get("status", "fail")
        fixes = result.get("fixes", [])
        fixed_json = result.get("fixed_json")

        if status != "success" or fixed_json is None:
            print("Failed to fix JSON. The input may be too broken or ambiguous.", file=sys.stderr)
            if fixes:
                print("Reasons/Notes:", file=sys.stderr)
                for f in fixes:
                    print(f" - {f}", file=sys.stderr)
            sys.exit(1)

        # Print fixes to stderr so it doesn't corrupt stdout which could be piped
        if fixes:
            for f in fixes:
                print(f"Fixed: {f}", file=sys.stderr)
        else:
            print("Status: No structural changes were needed.", file=sys.stderr)

        if not args.dry_run:
            print(json.dumps(fixed_json, indent=2))
        else:
            print("(--dry-run enabled, omitted JSON output)", file=sys.stderr)

    except Exception as e:
        print(f"Error during API call or processing: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
