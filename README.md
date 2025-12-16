# HR Assistant — resume ranking toolkit

A pragmatic Streamlit app that prioritises CVs with a single LLM pass, smart de-duplication, and a polished Excel export. The code is structured to be portfolio-ready and easy to extend. Added OpenRouter support, live model pickers, and mandatory role context with AI-generated skill weights.

## Highlights (EN)
- **Flexible LLMs**: OpenAI, OpenRouter, local **LM Studio**, or any custom OpenAI-compatible base URL — model lists are auto-fetched per provider (LM Studio works with `http://localhost:1234` _or_ `http://localhost:1234/v1`).
- **Mandatory context**: role description + key skills with weights are required; click “⚡️ Generate” to auto-build skills/keywords from the description.
- **Multiple intake paths**: upload local files, point to a server directory (even without uploads), or feed an Excel file with links (plus optional names).
- **Batch-grade scoring**: one request per batch (up to 5 CVs) with role context and weighted criteria.
- **Human-readable output**: tidy XLSX with borders, conditional formatting, priority buckets, and a commentary column.
- **Resilience**: hashing-based checkpoints, duplicate pruning by hash/contacts/similarity, and graceful fallbacks for names.

## Quick start
1. Install dependencies:
   ```bash
   pip install streamlit pdfminer.six python-docx rapidfuzz pandas openpyxl pydantic tenacity openai requests beautifulsoup4 lxml
   ```
2. Run the app:
   ```bash
   streamlit run app.py
   ```
3. Open the UI (defaults to `http://localhost:85948` when launched via `start_app.py`).

## LLM configuration
- **OpenAI cloud**: select "OpenAI (облако)" and provide your API key.
- **OpenRouter**: choose "OpenRouter (облако)" and provide your OpenRouter API key; models are pulled automatically.
- **LM Studio (local)**: choose "LM Studio (локально)". Leave the key blank to auto-use `lm-studio`; base URL can be `http://localhost:1234` or `http://localhost:1234/v1` — the app tries both when fetching models.
- **Custom endpoint**: pick "Custom base_url" and set any OpenAI-compatible base URL plus token.
  - Model dropdowns fetch available IDs via API (`/models` for LM Studio) and fall back to safe defaults.

## Feeding resumes
- **Upload**: drop PDF/DOCX/TXT/MD/RTF files directly into the uploader.
- **Server directory**: specify a folder path on the server and optionally include subfolders—handy for bulk drops.
- **Excel with links**: supply an `.xlsx` file containing URLs; optional columns for candidate names will be picked up automatically.

## Export & checkpoints
- The app writes a richly formatted XLSX (ranking, stats, similarity pairs, config).
- Checkpoints are stored as JSONL keyed by SHA-1, so you can safely resume long runs.
- Skill weights are passed to the LLM as JSON together with the vacancy description, so every batch is judged against explicit expectations.

---

# HR Assistant — ранжирование резюме

Портфолио-готовое приложение на Streamlit: один LLM-запрос на батч резюме, аккуратный XLSX и продуманная дедупликация. Теперь есть OpenRouter, авто-выбор моделей и обязательный контекст вакансии с AI-генерацией навыков.

## Ключевые плюсы (RU)
- **Гибкие модели**: OpenAI, OpenRouter, локальный **LM Studio** или любой OpenAI-совместимый endpoint; список моделей тянется через API (LM Studio понимает и `http://localhost:1234`, и `http://localhost:1234/v1`).
- **Любые источники резюме**: загрузка файлов, чтение с сервера из директории (даже без загрузок), либо XLSX со ссылками и ФИО.
- **Оценка за раз**: до 5 резюме в одном запросе, критерии с весами и контекст вакансии; кнопку “⚡️ Сгенерировать” можно нажать, чтобы собрать навыки из описания.
- **Красивый экспорт**: форматирование, data bars, приоритетные бакеты, поясняющие комментарии.
- **Надёжность**: чекпоинты по SHA-1, фильтрация дубликатов по хешам/контактам/похожести, фолбэки для ФИО.

## Быстрый старт
1. Установите зависимости (см. блок выше).
2. Запустите `streamlit run app.py` (или `python start_app.py` для автоконфига порта/браузера).
3. Откройте UI и выберите провайдера LLM.

## Настройка LLM
- **OpenAI** — введите API key.
- **OpenRouter** — введите OpenRouter API key; список моделей подтянется автоматически.
- **LM Studio** — можете оставить ключ пустым, base URL может быть `http://localhost:1234` или `http://localhost:1234/v1`; список моделей берётся из `/models`, пробуем оба варианта.
- **Custom** — впишите свой OpenAI-совместимый base URL и токен.
  - Выпадающие списки моделей используют данные API, при ошибке остаются дефолтные варианты.

## Откуда брать резюме
- Загрузите файлы (PDF/DOCX/TXT/MD/RTF) через UI.
- Укажите путь к директории на сервере и, при желании, захватите подпапки — можно работать и без загрузок.
- Добавьте XLSX со ссылками; колонку с ФИО можно подсказать, но авто-эвристика тоже работает.

## Экспорт и возобновление
- XLSX сохраняется на сервере и доступен для скачивания прямо в браузере.
- Чекпоинты в JSONL позволяют безопасно перезапускать процесс без повторных запросов к LLM.
- Весовые навыки в JSON уходят в запрос к LLM вместе с описанием роли, так что каждая пачка оценивается против явных ожиданий.

Удачи в подборе идеальных кандидатов — этот инструмент создан, чтобы экономить время и выглядеть профессионально.
