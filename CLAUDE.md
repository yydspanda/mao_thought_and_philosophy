# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Mao-Cognition** is an LLM-powered knowledge engineering system that deeply analyzes classical Chinese political texts (primarily Mao Zedong's works) and transforms them into structured, interactive knowledge bases for Obsidian. The system extracts concepts, builds knowledge graphs, and generates markdown documentation with bidirectional links.

## Common Commands

### Running the Application

```bash
# Run with default file (毛泽东选集一至七卷.epub) and developer perspective
python -m src.mao_thought_and_philosophy.main

# Specify a different EPUB file
python -m src.mao_thought_and_philosophy.main --file "毛主席教我们当省委书记.epub"

# Choose analysis perspective (developer vs management)
python -m src.mao_thought_and_philosophy.main --role developer
python -m src.mao_thought_and_philosophy.main --role management
```

### Development Tools

```bash
# Format code with Ruff (auto-runs on save in VSCode)
ruff format .

# Run linting
ruff check .

# Fix auto-fixable lint issues
ruff check --fix .

# Type checking with mypy
mypy src/

# Install dependencies
poetry install
```

## Architecture

### ETL + RAG Pipeline

The system follows an Extract-Transform-Load pattern with Retrieval-Augmented Generation:

1. **Extract** (`core/loader.py`): Parse EPUB files using `ebooklib` and `BeautifulSoup4`
   - `MaoEpubLoader`: Specialized loader that extracts hierarchical structure (volumes, periods), dates, and content
   - Intelligently removes headers, dates, and noise from content
   - Filters out short chapters (<300 chars) and excluded titles

2. **Transform** (`processing/workflow.py`): LLM analysis with context-aware prompts
   - Uses Jinja2 templates for prompt engineering (`processing/prompt_templates.py`)
   - Calls LLM via OpenAI-compatible API (`core/llm_client.py`)
   - Supports role-based analysis (developer/management perspectives)
   - Implements checkpoint recovery: skips existing files, only backfills index

3. **Load** (`core/graph_builder.py`): Build knowledge graph and generate Obsidian vault
   - `ConceptMemory`: Maintains global concept definitions, relations, and chapter appearances
   - Generates markdown files with YAML frontmatter, WikiLinks, and navigation
   - Creates concept cards in `concepts/` directory with backlinks

### Key Components

**Configuration** (`config.py`):
- Uses `importlib.resources` for package asset access
- Loads environment variables from `.env` (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL)
- Defines directory structure: `ASSETS_DIR`, `OUTPUT_DIR`, `LOG_DIR`

**LLM Client** (`core/llm_client.py`):
- Wraps OpenAI SDK with `response_format={"type": "json_object"}`
- Uses `json_repair` library to fix malformed JSON from LLM responses
- Strips markdown code blocks from responses

**Knowledge Graph** (`core/graph_builder.py`):
- `ConceptMemory.update()`: Merges new concepts from each chapter
- `ConceptMemory.get_context_string()`: Returns top 20 concepts by frequency for LLM context
- `ConceptMemory.purge_chapter_memory()`: Cleans up orphaned concepts when re-processing chapters

**Workflow** (`processing/workflow.py`):
- Generates role-specific output directories (e.g., `毛泽东选集一至七卷【牛马】`)
- Creates numbered chapter files (`001_title.md`, `002_title.md`) for proper sorting
- Builds index table with volume, period, date, tags, and summary
- Implements API rate limiting with countdown timer

## Environment Setup

Create a `.env` file in the project root:

```ini
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

Supported LLM providers: OpenAI, DeepSeek, Google Gemini (via OpenAI-compatible endpoints)

## Output Structure

```
output/
└── {book_title}【{role}】/
    ├── 00_全书概览_Index.md          # Auto-generated index table
    ├── knowledge_graph.json          # Serialized concept memory
    ├── chapters/
    │   ├── 001_chapter_title.md
    │   ├── 002_chapter_title.md
    │   └── ...
    └── concepts/
        ├── 解剖麻雀.md                # Concept cards with backlinks
        └── ...
```

## Important Implementation Details

### Checkpoint Recovery
- The system checks if chapter markdown files already exist before calling the LLM
- If a file exists, it extracts metadata (summary, tags) via regex to populate the index
- This prevents redundant API calls and allows resuming interrupted runs
- Use `ConceptMemory.purge_chapter_memory()` before re-processing to avoid duplicate references

### Filename Sanitization
- `sanitize_filename()` removes illegal characters: `\/*?:"<>|""''\'"`
- Truncates to 60 characters to prevent path length issues on Windows
- Applied to both chapter titles and concept names

### Role-Based Analysis
- Two perspectives: `developer` (牛马) and `management` (管理)
- Different system prompts generate different insights from the same text
- Output directories are separated by role to prevent conflicts

### JSON Repair Strategy
- LLM responses may contain unescaped quotes, trailing commas, or truncated JSON
- `json_repair.repair_json()` automatically fixes common issues
- If repair fails, the system prints the first 500 chars of the problematic response for debugging

### Obsidian Integration
- Uses `[[WikiLink]]` syntax for bidirectional linking
- YAML frontmatter includes: title, order, volume, period, publish_date, tags, date
- Original text is preserved in collapsible `<details>` blocks
- Navigation links use consistent `{index:03d}_{title}` format

## Python Version & Dependencies

- Requires Python 3.11+
- Uses Poetry for dependency management
- Key dependencies: `openai`, `ebooklib`, `beautifulsoup4`, `jinja2`, `json-repair`, `networkx`

## Code Style

- Formatted with Ruff (88 char line length)
- Type hints are optional (mypy configured with `ignore_missing_imports=true`)
- VSCode auto-formats and organizes imports on save
