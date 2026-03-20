# Broken JSON Fixer

A CLI tool that takes broken JSON as input and uses an LLM (Gemini 2.5 Flash) to figure out the intended structure, returning valid, clean, and pretty-printed JSON. The tool strictly fixes missing quotes, trailing commas, single quotes, and basic structural issues without mutating content values.

## Setup

1. Make sure Python 3.9+ is installed.
2. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your internal Google Deepmind Gemini API key:
   ```bash
   # Windows PowerShell
   $env:GEMINI_API_KEY="your_api_key_here"
   # Linux/Mac
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

You can run the script by passing a file, or by piping standard input to it.

```bash
# Pass broken JSON via a file
python json_fixer.py my_broken.json

# Pass broken JSON via standard input
echo "{foo: 'bar', trailing: true, }" | python json_fixer.py
```

### Dry Run mode

If you just want to see what the LLM intends to fix, without actually outputting the repaired JSON object, pass the `--dry-run` flag.

```bash
python json_fixer.py my_broken.json --dry-run
```
