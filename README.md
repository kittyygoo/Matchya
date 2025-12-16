# 🍵 Matchya — Hire faster

Matchya is a portfolio-grade Streamlit app for ranking resumes with OpenAI-compatible LLMs. It keeps every run reproducible, resilient, and audit-friendly while staying simple enough to demo. The entire experience is English-only and tuned to look and feel like a polished startup tool.

## Why Matchya
- **Provider agility** — OpenAI, OpenRouter, LM Studio, or any OpenAI-compatible endpoint with live model discovery for each provider.
- **Resume intake your way** — pick one path explicitly: upload files or paste cloud links. Inputs remain hidden until you choose.
- **Context-first scoring** — vacancy description and a friendly criteria table are mandatory; one click can auto-draft the rows from the description.
- **Per-resume isolation** — one request per resume to avoid model cross-talk, plus strong deduplication by hash, contacts, and similarity.
- **Ready-to-share output** — styled Excel export with ranks, risk flags, reasoning, and similarity pairs for audits.

## Quick start
1. Install dependencies:
   ```bash
   pip install streamlit pdfminer.six python-docx rapidfuzz pandas openpyxl pydantic tenacity openai requests beautifulsoup4 lxml
   ```
2. Run the app:
   ```bash
   streamlit run app_requests.py
   ```
   (Or `python start_app.py` to pick an open port automatically.)
3. Open the Streamlit URL printed in the terminal.

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
- **Comments**: Matchya writes human-friendly summaries with strengths, examples, gaps, and risk flags.

## Output
- **Excel**: ranked candidates with conditional formatting, borders, priority buckets, and optional similarity pairs (top 200).
- **Checkpoint**: JSONL keyed by SHA-1 to safely resume long runs without re-scoring processed resumes.
- **Config sheet**: model, provider, thresholds, and criteria weights for transparency.

## Pro tips
- Keep LM Studio running before you fetch models; both `/v1/models` and `/models` are tried automatically.
- Use the cloud-links mode for large batches of public resumes; the uploader is ideal for handpicked files.
- Treat the criteria table as weights: higher `weight` means a bigger influence on ranking, while `keywords` help the LLM stay on-topic.

Enjoy faster, clearer hiring workflows with **🍵 Matchya**.
