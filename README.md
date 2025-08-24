# PLM Log Analyzer - Android Issue Detection Tool

A modern web application that intelligently analyzes Android log files to detect issues and identify root causes.

## Features

- **Smart Issue Detection**: Automatically identifies common Android issues like:
  - App Crashes
  - ANR (Application Not Responding)
  - UI Issues
  - Network Problems
  - Audio Problems
  - Camera Issues
  - Memory Issues
  - Permission Problems

- **Pattern Analysis**: Uses advanced regex patterns to extract relevant log entries
- **Root Cause Analysis**: Provides detailed analysis of what caused the issue
- **Duplicate Detection**: Find similar issues from your database using advanced text similarity
- **Beautiful UI**: Modern, responsive design with drag-and-drop file upload
- **API Support**: RESTful API for programmatic access

## Installation

1. **Clone or download the project**
2. **Install Python dependencies (base only)**:
   ```bash
   pip install -r requirements.txt
   ```
3. *(Optional for AI / semantic duplicate & translation)* Install extended dependencies:
   ```bash
   pip install -r requirements-ai.txt
   ```

### Offline Environment Preparation

If you need to work completely offline (no internet on office laptop):

1. On an online machine run:
   ```bash
   python scripts/prepare_offline_env.py --download-dir offline_bundle
   ```
2. Copy the entire project folder **including** `offline_bundle/` to the offline machine.
3. On the offline machine install from the local bundle:
   ```bash
   pip install --no-index --find-links offline_bundle -r requirements.txt
   pip install --no-index --find-links offline_bundle -r requirements-ai.txt
   ```
4. The sentence-transformer model (default `all-MiniLM-L6-v2`) will already be downloaded under `offline_bundle/models/`.
5. Run the app normally (`python app.py`).

## Usage

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and go to `http://localhost:5000`

3. **Upload your Android log file** (.txt or .log format)

4. **Provide problem details**:
   - Problem statement (brief description)
   - Detailed problem description

5. **Click "Analyze Logs & Detect Issues"**

6. **View results** including:
   - Identified issue types with confidence scores
   - Relevant log entries with context
   - Root cause analysis

## API Usage

The application also provides a REST API:

```bash
POST /api/analyze
Content-Type: application/json

{
    "log_content": "your log content here",
    "problem_description": "description of the problem"
}
```

## Duplicate Finder

The application includes a powerful duplicate detection feature that helps identify if similar issues have been reported before:

### How It Works
1. **Upload CSV Database**: Provide a CSV file with your issues database (must include PLM_ID column)
2. **Describe Issue**: Enter problem title and detailed description
3. **Set Threshold**: Adjust similarity threshold (80% recommended)
4. **Find Matches**: Get up to 5 most similar issues above the threshold

### CSV Format
Your CSV should include these columns:
- `PLM_ID`: Unique identifier for each issue
- `problem_title`: Brief issue description
- `problem_description`: Detailed problem description
- `logs_analysis`: Relevant log entries or analysis

### Similarity Methods
* **Lightweight** (always available): Rule / token based similarity.
* **Advanced (Semantic)**: Requires installing `requirements-ai.txt` and enables sentence embedding matching.
* **Translation Support**: After installing AI requirements, you can integrate translation (e.g. using `deep-translator`) to normalize non-English issue text before similarity.

### Embedding Cache
When semantic mode is used, embeddings for the CSV are cached under `cache/` named as `<csv>.<model>.embeddings.pkl` plus a meta JSON. Subsequent searches with an unchanged CSV reuse the cache. Result page shows HIT/MISS status.

## Tests
Lightweight tests for the duplicate finder are in `tests/test_duplicate_finder.py`. If you have `pytest` installed:

```bash
pytest -q
```

They exercise lightweight duplicate detection and cache stat structure. (Transformer path not covered to keep tests fast.)

## File Structure

```
PlmAnalyzer/
├── app.py                    # Main Flask application
├── templates/               # HTML templates
│   ├── index.html          # Main upload form
│   ├── results.html        # Results display
│   ├── duplicate_finder.html    # Duplicate finder form
│   └── duplicate_results.html   # Duplicate search results
├── requirements.txt         # Python dependencies
├── sample_issues_database.csv  # Sample CSV format
├── advanced_duplicate_finder.py # Advanced duplicate detection
├── README.md               # This file
└── uploads/                # Upload directory (auto-created)
```

## Supported Log Formats

- `.txt` files
- `.log` files
- Maximum file size: 16MB
- UTF-8 encoding (auto-detected)

## How It Works

1. **Pattern Matching**: The system uses predefined regex patterns for each issue type
2. **Scoring**: Issues are scored based on pattern matches in both logs and problem description
3. **Context Extraction**: Relevant log entries are extracted with surrounding context
4. **Root Cause Analysis**: Identifies specific indicators that point to the root cause

## Customization

You can modify the `LogAnalyzer` class in `app.py` to:
- Add new issue types
- Modify pattern matching rules
- Adjust scoring algorithms
- Enhance root cause analysis

## Requirements

- Python 3.7+
- Flask web framework
- Modern web browser with JavaScript enabled

## License

This project is open source and available under the MIT License.
