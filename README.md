# 🍵 Matchya — Hire faster

**Matchya** is an application for screening candidates in a super fast and simple format.
Need to process 10 or 100 or even 1,000 résumés? Save your time—press a couple of buttons and get an unbiased, easy-to-read result.

## Easy-to-get output

![Abstract](https://github.com/kittyygoo/Matchya/blob/main/examples/Screenshot%202025-12-16%20at%2022.34.57.png)

See? All candidates were graded and sorted—for you to easily process the top ones.

---

![Detailed](https://github.com/kittyygoo/Matchya/blob/main/examples/Screenshot%202025-12-16%20at%2022.35.42.png)

Just zoomed version for you to see what is going on.

## Why Matchya
- ⏱️ **Time efficiency** — Instead of manual screening or blunt keyword filtering, delegate candidate selection to Matchya. Focus only on high-quality candidates that truly fit.

- 🤟 **Ease of use** — A few clicks, a short wait, and the results are ready.

- 🤸 **Flexibility** — Customize evaluation criteria to your needs. Don’t want to define them yourself? Matchya can do it for you.

- 🩻 **Clean, actionable results** — Clear, structured output with explanations and formatting, designed for fast HR decision-making.

- 🤑 **Cost savings** — Processing 10, 100, or 1,000 résumés with Matchya costs up to 10× less than manual work.

## UI

![pic](https://github.com/kittyygoo/Matchya/blob/main/examples/Screenshot%202025-12-16%20at%2023.52.31.png)

---

![pic](https://github.com/kittyygoo/Matchya/blob/main/examples/Screenshot%202025-12-16%20at%2023.52.53.png)

## Quick start
1. Install dependencies:
   ```bash
   pip install streamlit pdfminer.six python-docx rapidfuzz pandas openpyxl pydantic tenacity openai requests beautifulsoup4 lxml
   ```
2. Run the app:
   ```bash
   streamlit run app.py
   ```
   (Or `python start_app.py` to pick an open port automatically.)
3. Open the Streamlit URL printed in the terminal.
4. Enjoy Matchya ✌️

## Code structure
- `app.py`: Streamlit UI orchestrator.
- `matchya/`: modules for LLM clients, intake, scoring, similarity, checkpoints, and text helpers.
- `app_requests.py`: tiny shim for backward compatibility with the old entrypoint.

## LLM configuration
- **OpenAI (cloud)**: select the provider, add your API key, and pick a model from the auto-fetched list.
- **OpenRouter (cloud)**: enter your OpenRouter key; models are fetched live with polite default headers.
- **LM Studio (local)**: works with `http://localhost:1234` or `http://localhost:1234/v1`; leave the key blank to auto-use `lm-studio`. Models are pulled via `/v1/models` with fallback to `/models`.
- **Custom base_url**: point to any OpenAI-compatible endpoint, provide the base URL and token, and choose from the discovered models or defaults.

## Feeding resumes
Choose **one** intake mode (the inputs stay hidden until selected):
- **Upload files**: PDF, DOCX, TXT, MD, or RTF directly in the browser.
- **Cloud links**: paste one URL per line (direct file links or HTML resume pages). Matchya downloads and normalizes the files for you.

## Role context & criteria
- Provide a **role/vacancy description** (required).
- Enter key skills/criteria in the editable table (`Criterion`, `Weight`, `Keywords`). Add rows, reorder, or tweak values inline.
- Use **⚡️ Generate skills** to let the LLM propose a weighted criteria list based on the description; edit as needed.

## How scoring works
- **Isolation first**: each resume is scored in its own LLM call with the description and the criteria table included every time.
- **Signals extracted**: full name, specialization, emails, phones, scores per criterion, and reasoning per criterion.
- **Composite score**: `0.75 × weighted percentiles + 0.25 × coverage` (coverage = share of criteria with >0 scores).
- **Duplicate defense**: hashes for files and normalized text, plus email/phone and similarity pruning based on your threshold.
- **Comments**: Matchya writes easy-to-get summaries with strengths, examples, gaps, and risk flags.

## Output
- **Excel**: ranked candidates with conditional formatting, borders, priority buckets, and optional similarity pairs (top 200).
- **Checkpoint**: JSONL keyed by SHA-1 to safely resume long runs without re-scoring processed resumes.
- **Config sheet**: model, provider, thresholds, and criteria weights for transparency.

## Pro tips
- Keep LM Studio running before you fetch models; both `/v1/models` and `/models` are tried automatically.
- Use the cloud-links mode for large batches of public resumes; the uploader is ideal for handpicked files.
- Treat the criteria table as weights: higher `weight` means a bigger influence on ranking, while `keywords` help the LLM stay on-topic.

Enjoy faster, clearer hiring workflows with **🍵 Matchya**.

## Authors
- Elizaveta Kalinina [@kittyygoo](https://github.com/kittyygoo)
- Nikita Prudnikov [@prudnik-web](https://github.com/prudnik-web)
