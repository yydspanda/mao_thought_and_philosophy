# AGENTS.md

Guide for AI coding agents working on the Mao-Cognition project.

## Project Overview

Mao-Cognition is an LLM-powered knowledge engineering system that analyzes classical Chinese political texts (primarily Mao Zedong's works) and transforms them into structured, interactive knowledge bases for Obsidian. The system extracts concepts, builds knowledge graphs, and generates markdown documentation with bidirectional links.

## Build/Lint/Test Commands

### Running the Application

```bash
# Run with default file and developer perspective
python -m src.mao_thought_and_philosophy.main

# Specify a different EPUB file
python -m src.mao_thought_and_philosophy.main --file "my_book.epub"

# Choose analysis perspective
python -m src.mao_thought_and_philosophy.main --role developer
python -m src.mao_thought_and_philosophy.main --role management
```

### Development Commands

```bash
# Install dependencies
poetry install

# Format code with Ruff (auto-runs on save in VSCode)
ruff format .

# Run linting
ruff check .

# Fix auto-fixable lint issues
ruff check --fix .

# Type checking with mypy
mypy src/
```

### Testing

This project does not have a formal test suite. The `tests/` directory contains utility scripts for maintenance tasks (e.g., `restore_old_format.py` for cleaning duplicate files).

## Code Style Guidelines

### Imports

Organize imports in three groups, separated by blank lines:

1. **Standard library** (alphabetically sorted)
2. **Third-party libraries** (alphabetically sorted)
3. **Local imports** (relative imports using `.` or `..`)

Example:
```python
import datetime
import json
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from openai import OpenAI

from ..config import LLM_API_KEY, LLM_BASE_URL
from .prompt_templates import get_system_prompt
```

- Use `from importlib.resources import files` for package resource access
- Use `from typing import Any, Dict, List, Optional` for type hints
- Add `# type: ignore` for libraries without type stubs (e.g., `import ebooklib  # type: ignore`)

### Formatting

- **Line length**: 88 characters (Ruff default)
- **Indentation**: 4 spaces
- **String quotes**: Double quotes preferred for consistency
- **Trailing commas**: Use in multi-line collections
- **Blank lines**: 
  - 2 blank lines before class/function definitions at module level
  - 1 blank line between methods
  - 1 blank line between logical sections within functions

Ruff configuration (`pyproject.toml`):
```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]
```

### Type Hints

Type hints are **optional but encouraged**. The project uses relaxed mypy settings:

```toml
[tool.mypy]
ignore_missing_imports = true
strict_optional = true
disallow_untyped_defs = false
check_untyped_defs = false
warn_return_any = false
```

Guidelines:
- Add type hints for function parameters and return types when the type is non-obvious
- Use `Optional[T]` for values that can be `None`
- Use `Dict[str, Any]` for JSON-like structures
- Use `List[T]` for typed lists
- Use `Any` when type is truly dynamic (e.g., LLM responses)

Example:
```python
def call_llm_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    ...

def sanitize_filename(name: str) -> str:
    ...
```

### Naming Conventions

- **Modules/Files**: `snake_case.py` (e.g., `llm_client.py`, `graph_builder.py`)
- **Classes**: `PascalCase` (e.g., `ConceptMemory`, `MaoEpubLoader`)
- **Functions/Methods**: `snake_case` (e.g., `get_context_string`, `purge_chapter_memory`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ASSETS_DIR`, `OUTPUT_DIR`, `DEFAULT_EXCLUDED_TITLES`)
- **Private methods**: Prefix with underscore (e.g., `_clean_json_string`, `_extract_date`)
- **Variables**: `snake_case` (e.g., `chapter_title`, `file_path`)

### Error Handling

- Use `try/except` blocks for operations that may fail (API calls, file I/O, JSON parsing)
- Print user-friendly error messages with emoji prefixes for visibility
- Re-raise exceptions after logging if the caller should handle them
- Use defensive checks with `.get()` for dictionary access

Example:
```python
try:
    result = call_llm_json(current_system_prompt, prompt)
except Exception as e:
    print(f"   ⚠️ 分析失败，跳过本章: {str(e)}")
    continue

# Defensive dictionary access
name = concept.get("name")
definition = concept.get("definition")
if not name or not definition:
    continue
```

### File and Path Handling

- Always use `pathlib.Path` for path operations (never string concatenation)
- Use `Path.mkdir(parents=True, exist_ok=True)` for directory creation
- Use `with open(file_path, "r", encoding="utf-8") as f:` for file operations
- Always specify `encoding="utf-8"` for Chinese text support

Example:
```python
from pathlib import Path

OUTPUT_DIR = BASE_WORK_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
```

### Comments and Documentation

- Use **Chinese comments** for inline explanations (matching the project's domain)
- Use **English** for docstrings and type hints
- Add docstrings for public functions and classes
- Use block comments (`# ---`) to separate logical sections in long functions

Example:
```python
def get_context_string(self, limit=20):
    """
    Extract high-value concepts and pack them into a string for LLM context.
    """
    if not self.concepts:
        return "暂无已知概念。"
    
    # 排序：按"出现章节数"从多到少排序
    sorted_concepts = sorted(
        self.appearances.items(), 
        key=lambda x: len(x[1]), 
        reverse=True
    )
```

### JSON Handling

- Always use `json_repair.repair_json()` when parsing LLM responses
- Use `json.dump(..., ensure_ascii=False, indent=2)` for Chinese text support
- Strip markdown code blocks before parsing: `^```(?:json)?\s*(.*?)\s*```$`

Example:
```python
from json_repair import repair_json

parsed_data = repair_json(cleaned_content, return_objects=True)
if not isinstance(parsed_data, dict):
    raise TypeError("LLM did not return a JSON object as expected.")
```

### Logging and Output

- Use `print()` with emoji prefixes for user-facing messages:
  - `🚀` for initialization
  - `✅` for success
  - `❌` for errors
  - `⚠️` for warnings
  - `⏳` for progress/waiting
  - `🧠` for knowledge graph operations
  - `💾` for saving data
- Use `logging` module for internal debugging (see `loader.py`)

## Project Structure

```
src/mao_thought_and_philosophy/
├── __init__.py
├── main.py              # Entry point with CLI argument parsing
├── config.py            # Environment variables and directory paths
├── core/
│   ├── __init__.py
│   ├── loader.py        # EPUB parsing with MaoEpubLoader class
│   ├── llm_client.py    # OpenAI API wrapper with JSON repair
│   └── graph_builder.py # ConceptMemory class for knowledge graph
└── processing/
    ├── __init__.py
    ├── prompt_templates.py  # Jinja2 prompt templates
    └── workflow.py          # Main analysis pipeline

tests/
└── restore_old_format.py    # Utility for cleaning duplicate files

output/
└── {book_title}【{role}】/
    ├── 00_全书概览_Index.md
    ├── knowledge_graph.json
    ├── chapters/
    └── concepts/
```

## Environment Setup

Create a `.env` file in the project root:

```ini
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
```

Supported providers: OpenAI, DeepSeek, Google Gemini (via OpenAI-compatible endpoints).
