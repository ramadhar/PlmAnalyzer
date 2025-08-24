from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import os
import shutil
import re
import json
import csv
import difflib
from werkzeug.utils import secure_filename
from datetime import datetime
import logging
import math
from collections import Counter
import uuid
import time
import subprocess
import sys
import threading
from importlib import metadata as importlib_metadata

# Attempt to import advanced duplicate finder (semantic support)
try:
    from advanced_duplicate_finder import AdvancedDuplicateFinder
except Exception:
    AdvancedDuplicateFinder = None  # Fallback gracefully
try:
    from translator.simple_translator import SimpleTranslator
    try:
        from ai.ai_assistant import get_ai_assistant
    except Exception:
        get_ai_assistant = None
except Exception:
    SimpleTranslator = None

app = Flask(__name__)
AI_MODE = os.environ.get('PLM_AI', '0') == '1'
app.secret_key = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size (hard ceiling - request rejected earlier)
app.config['UPLOAD_FOLDER'] = 'uploads'

# -----------------------------------------------------------------------------
# Diagnostics & Runtime Controls
# -----------------------------------------------------------------------------
ENABLE_REQ_LOG = os.environ.get('PLM_REQ_LOG', '1') == '1'

@app.before_request
def _req_start_timer():
    if ENABLE_REQ_LOG:
        from flask import g
        g._req_start = time.time()

@app.after_request
def _req_log(resp):
    if ENABLE_REQ_LOG:
        from flask import g, request
        st = getattr(g, '_req_start', None)
        if st is not None:
            dur = (time.time() - st) * 1000
            logger.info(f"REQ {request.method} {request.path} -> {resp.status_code} {dur:.1f}ms")
    return resp

@app.errorhandler(500)
def _err_500(e):
    logger.exception('Unhandled server error')
    return jsonify({'error': 'internal_server_error', 'detail': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'time': time.time(), 'cache_items': len(LOG_CACHE)})

@app.route('/admin/clear_cache', methods=['POST'])
def admin_clear_cache():
    """Manually clear persistent cache and in-memory analyses; returns stats."""
    stats = clear_persistent_cache()
    LOG_CACHE.clear()
    stats.update({'status': 'cleared', 'in_memory_cleared': True})
    return jsonify(stats)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
if AI_MODE:
    logger.info('AI mode enabled (PLM_AI=1). Will prefer semantic duplicate finder if dependencies available.')

# =============================================================
# Dependency Management (install/update/remove) infrastructure
# =============================================================
_DEP_OP_LOCK = threading.Lock()

BASE_REQUIREMENTS_FILE = os.path.join(os.path.dirname(__file__), 'requirements.txt')
AI_REQUIREMENTS_FILE = os.path.join(os.path.dirname(__file__), 'requirements-ai.txt')
OFFLINE_BUNDLE_DIR = os.path.join(os.path.dirname(__file__), 'offline_bundle')

def _parse_requirements(path: str):
    reqs = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):  # Skip comments / blank
                    continue
                # Basic safety: reject editable / direct URLs for this manager
                if any(line.startswith(p) for p in ('-e ', 'git+', 'http://', 'https://')):
                    continue
                reqs.append(line)
    except Exception as e:
        logger.warning(f"Failed parsing requirements {path}: {e}")
    return reqs

def _collect_all_requirements():
    base = _parse_requirements(BASE_REQUIREMENTS_FILE)
    ai = _parse_requirements(AI_REQUIREMENTS_FILE)
    # Preserve order but avoid duplicates (keep first spec)
    seen = set()
    combined = []
    for item in base + ai:
        name = re.split(r'[<>=!~]', item, 1)[0].strip().lower()
        if name not in seen:
            seen.add(name)
            combined.append(item)
    return combined

def _get_installed_version(pkg_name: str):
    try:
        return importlib_metadata.version(pkg_name)
    except Exception:
        return None

def _dependency_status():
    reqs = _collect_all_requirements()
    out = []
    for spec in reqs:
        name = re.split(r'[<>=!~]', spec, 1)[0].strip()
        installed_version = _get_installed_version(name)
        needs_update = False
        if installed_version and '==' in spec:
            pinned = spec.split('==',1)[1].strip()
            needs_update = installed_version != pinned
        out.append({
            'name': name,
            'spec': spec,
            'installed': installed_version is not None,
            'installed_version': installed_version,
            'needs_update': needs_update
        })
    return out

def _run_pip(args, offline_fallback=False):
    """Run pip command returning (rc, output). Adds offline fallback if requested."""
    python_exe = sys.executable or 'python'
    base_cmd = [python_exe, '-m', 'pip'] + args
    try:
        proc = subprocess.run(base_cmd, capture_output=True, text=True, timeout=1800)
        output = proc.stdout + '\n' + proc.stderr
        rc = proc.returncode
        if rc == 0:
            return rc, output
        if offline_fallback:
            # Attempt offline using wheel cache directory
            offline_args = [python_exe, '-m', 'pip'] + args + ['--no-index', '--find-links', OFFLINE_BUNDLE_DIR]
            proc2 = subprocess.run(offline_args, capture_output=True, text=True, timeout=1800)
            output += '\n---- OFFLINE FALLBACK ----\n' + proc2.stdout + '\n' + proc2.stderr
            return proc2.returncode, output
        return rc, output
    except Exception as e:
        return 1, f"Failed executing pip: {e}"

@app.route('/dependencies')
def dependencies_page():
    return render_template('dependencies.html', ai_mode=AI_MODE)

@app.route('/api/dependencies/status')
def api_dependencies_status():
    return jsonify({'packages': _dependency_status()})

@app.route('/api/dependencies/action', methods=['POST'])
def api_dependencies_action():
    data = request.get_json(force=True) or {}
    action = data.get('action')
    package = data.get('package')
    if not action:
        return jsonify({'error': 'action required'}), 400
    if not _DEP_OP_LOCK.acquire(blocking=False):
        return jsonify({'error': 'operation_in_progress'}), 409
    try:
        output = ''
        rc = 0
        if action == 'install_missing':
            missing = [p['spec'] for p in _dependency_status() if not p['installed']]
            if not missing:
                return jsonify({'message': 'No missing packages'}), 200
            rc, output = _run_pip(['install'] + missing, offline_fallback=True)
        elif action == 'update_all':
            # Use requirements files directly
            args = ['install', '--upgrade']
            if os.path.exists(BASE_REQUIREMENTS_FILE):
                args += ['-r', BASE_REQUIREMENTS_FILE]
            if os.path.exists(AI_REQUIREMENTS_FILE):
                args += ['-r', AI_REQUIREMENTS_FILE]
            rc, output = _run_pip(args, offline_fallback=True)
        elif action == 'update_pip':
            rc, output = _run_pip(['install', '--upgrade', 'pip'], offline_fallback=False)
        elif action == 'remove':
            if not package:
                return jsonify({'error': 'package required for remove'}), 400
            # Safety: ensure package is in requirement set
            req_names = {re.split(r'[<>=!~]', r,1)[0].strip().lower() for r in _collect_all_requirements()}
            if package.lower() not in req_names:
                return jsonify({'error': 'package not managed'}), 400
            rc, output = _run_pip(['uninstall', '-y', package], offline_fallback=False)
        else:
            return jsonify({'error': 'unknown action'}), 400
        status = _dependency_status()
        return jsonify({'rc': rc, 'output': output, 'packages': status})
    finally:
        _DEP_OP_LOCK.release()

# =============================
# In-memory log analysis cache
# =============================
LOG_CACHE = {}
MAX_CACHE_ITEMS = 5
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache_store')
os.makedirs(CACHE_DIR, exist_ok=True)
# cache_store usage:
#  - Persist per-upload raw log copy and derived analysis JSON/metadata so user can refresh page without re-upload.
#  - Temporary embeddings / duplicate detection artifacts.
#  - Not needed long-term; safe to delete between sessions.
# We enforce a soft quota (e.g., 500MB) and prune oldest files beyond that.
CACHE_SOFT_MAX_BYTES = 500 * 1024 * 1024  # 500MB

ISSUE_TYPE_MAP = {
    'Audio Issues': ['Noise in Audio', 'Multiple Audio Output', 'Audio Not Working'],
    'Camera Issues': ['Camera Not Launched', 'Camera Rotated', 'Camera Crashes'],
    'App Crashes': ['App Force Stop', 'App Crashes', 'ANR in App', 'Device Reboot'],
    'UI Issues': ['Layout Problems', 'UI Crashes'],
    'Network Issues': ['Connection Problems', 'HTTP Errors'],
    'Memory Issues': ['Out of Memory'],
    'Multimedia Issues': ['Video Playback', 'Media Streaming', 'Codec Issues'],
    'Bluetooth Issues': ['Connection Problems', 'Audio Issues', 'Pairing Issues'],
    'App Installation': ['Install Failures', 'Update Issues', 'Permission Denied'],
    'Battery Issues': ['Drain Problems', 'Charging Issues', 'Power Management'],
    'Storage Issues': ['Space Problems', 'File Corruption', 'SD Card Issues'],
    'Security Issues': ['Permission Denied', 'Authentication Failed', 'Root Detection']
}

def _prune_cache():
    if len(LOG_CACHE) <= MAX_CACHE_ITEMS:
        return
    oldest = sorted(LOG_CACHE.items(), key=lambda kv: kv[1]['created'])[:len(LOG_CACHE)-MAX_CACHE_ITEMS]
    for k, _ in oldest:
        LOG_CACHE.pop(k, None)

def _cache_size_bytes():
    total = 0
    for root, _, files in os.walk(CACHE_DIR):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    return total

def clear_persistent_cache():
    """Recursively delete all files & folders in CACHE_DIR; return stats."""
    before = _cache_size_bytes()
    removed_files = 0
    removed_dirs = 0
    for entry in os.scandir(CACHE_DIR):
        try:
            if entry.is_file():
                os.remove(entry.path)
                removed_files += 1
            else:
                shutil.rmtree(entry.path, ignore_errors=True)
                removed_dirs += 1
        except Exception:
            pass
    after = _cache_size_bytes()
    freed = before - after
    if freed or removed_files or removed_dirs:
        logger.info(f"Cache cleared: files={removed_files} dirs={removed_dirs} freed={freed/1024/1024:.2f}MB")
    return {'files_removed': removed_files, 'dirs_removed': removed_dirs, 'bytes_before': before, 'bytes_after': after, 'bytes_freed': freed}

def prune_cache_size():
    """Ensure total size of CACHE_DIR does not exceed CACHE_SOFT_MAX_BYTES.
    Deletes oldest files first based on modification time."""
    try:
        entries = []
        total = 0
        for name in os.listdir(CACHE_DIR):
            path = os.path.join(CACHE_DIR, name)
            if os.path.isfile(path):
                try:
                    st = os.stat(path)
                    entries.append((st.st_mtime, st.st_size, path))
                    total += st.st_size
                except Exception:
                    pass
        if total <= CACHE_SOFT_MAX_BYTES:
            return
        # Sort oldest first
        entries.sort(key=lambda x: x[0])
        removed_bytes = 0
        removed_files = 0
        for _, size, path in entries:
            if total - removed_bytes <= CACHE_SOFT_MAX_BYTES:
                break
            try:
                os.remove(path)
                removed_bytes += size
                removed_files += 1
            except Exception:
                pass
        if removed_files:
            logger.info(f"Pruned {removed_files} cache files freeing {removed_bytes/1024/1024:.1f}MB (limit {CACHE_SOFT_MAX_BYTES/1024/1024:.0f}MB)")
    except Exception as e:
        logger.warning(f"Failed pruning cache size: {e}")

# Clear on app startup
clear_persistent_cache()
prune_cache_size()
from analyzers import LogAnalyzer

# =============================
# Helper utilities & persistence
# =============================

ALLOWED_EXTENSIONS = {'.txt', '.log'}

def allowed_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

# Lightweight duplicate finder fallback (simple similarity) if advanced not used
class DuplicateFinder:
    def __init__(self, csv_path):
        self.issues = []
        try:
            with open(csv_path, newline='', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = (row.get('title') or row.get('problem_title') or '').strip()
                    content = (row.get('content') or row.get('description') or '').strip()
                    if title or content:
                        self.issues.append({'title': title, 'content': content})
        except Exception:
            pass

    def get_issue_statistics(self):
        return {
            'total_issues': len(self.issues)
        }

    def find_duplicates(self, title, content, threshold=80.0, max_results=5):
        base = (title + ' ' + content).strip()
        out=[]
        if not base:
            return out
        for issue in self.issues:
            candidate = (issue['title'] + ' ' + issue['content']).strip()
            if not candidate:
                continue
            ratio = difflib.SequenceMatcher(None, base.lower(), candidate.lower()).ratio()*100
            if ratio >= threshold:
                out.append({'issue': issue, 'similarity': round(ratio,2)})
        out.sort(key=lambda x: x['similarity'], reverse=True)
        return out[:max_results]

# Persistence helpers
def _cache_entry_dir(log_id: str) -> str:
    return os.path.join(CACHE_DIR, log_id)

def _persist_entry(log_id: str):
    entry = LOG_CACHE.get(log_id)
    if not entry:
        return
    d = _cache_entry_dir(log_id)
    os.makedirs(d, exist_ok=True)
    # Write raw log (only once)
    raw_path = os.path.join(d, 'log.txt')
    if not os.path.exists(raw_path):
        with open(raw_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(entry['log'])
    # Meta (analyses) minimal persistence (just list of analyzed pairs)
    meta_path = os.path.join(d, 'meta.json')
    meta = {
        'created': entry['created'],
        'package_name': entry['package_name'],
        'pairs': list(map(lambda k: {'main': k[0], 'sub': k[1]}, entry['analyses'].keys()))
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f)

def _load_cache_from_disk():
    try:
        for log_id in os.listdir(CACHE_DIR):
            d = _cache_entry_dir(log_id)
            if not os.path.isdir(d):
                continue
            raw_path = os.path.join(d, 'log.txt')
            meta_path = os.path.join(d, 'meta.json')
            if not os.path.exists(raw_path) or not os.path.exists(meta_path):
                continue
            with open(raw_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            LOG_CACHE[log_id] = {
                'log': log_content,
                'package_name': meta.get('package_name'),
                'created': meta.get('created', time.time()),
                'analyses': {},
                'eager_mode': False
            }
    except Exception as e:
        logger.warning(f"Failed loading cache persistence: {e}")

_load_cache_from_disk()

def _analyze_pair(analyzer: LogAnalyzer, log_content: str, package: str, main: str, sub: str):
    return analyzer.analyze_issue_by_type(log_content, main, sub, package)

def _store_log_with_analyses(log_content: str, package_name: str, analyzer_factory, selected_pair):
    """Store a log and compute ONLY the selected (main, sub) analysis.
    Eager mode removed: we no longer precompute all issue types to simplify UX and performance."""
    log_id = str(uuid.uuid4())
    analyzer = analyzer_factory()
    analyses = {}
    main, sub = selected_pair
    analyses[(main, sub)] = _analyze_pair(analyzer, log_content, package_name, main, sub)
    LOG_CACHE[log_id] = {
        'log': log_content,
        'package_name': package_name,
        'created': time.time(),
        'analyses': analyses
    }
    _prune_cache()
    _persist_entry(log_id)
    return log_id

def _build_analysis_preview(analysis_result: dict) -> str:
    """Create a preview string containing ONLY the matched log lines (no properties, no context lines).
    Context lines are excluded per requirement to avoid loading extra / unrelated logs."""
    if not analysis_result:
        return 'No analysis result.'
    relevant = analysis_result.get('relevant_logs') or []
    if not relevant:
        return 'No relevant log lines extracted for this issue.'
    out_lines = []
    for rl in relevant:
        matched = rl.get('matched_line') or ''
        if matched:
            out_lines.append(matched)
    return '\n'.join(out_lines).strip()

def _ensure_analysis(log_id: str, main: str, sub: str):
    entry = LOG_CACHE.get(log_id)
    if not entry:
        raise KeyError('log id not found')
    key=(main, sub)
    if key not in entry['analyses']:
        analyzer = LogAnalyzer()
        res = _analyze_pair(analyzer, entry['log'], entry['package_name'], main, sub)
        entry['analyses'][key]=res
        _persist_entry(log_id)
    return entry['analyses'][key]

def _build_metrics(entry):
    total_pairs = sum(len(v) for v in ISSUE_TYPE_MAP.values())
    analyzed_pairs = len(entry['analyses'])
    per_category_counts = {}
    for (main, _sub) in entry['analyses'].keys():
        per_category_counts[main] = per_category_counts.get(main, 0) + 1
    return {
        'analyzed_pairs': analyzed_pairs,
        'total_pairs': total_pairs,
        'coverage_percent': round(100*analyzed_pairs/total_pairs,2) if total_pairs else 0,
        'per_category_counts': per_category_counts
    }


@app.route('/')
def index():
    return render_template('index.html', ai_mode=AI_MODE)

@app.route('/duplicate-finder')
def duplicate_finder():
    return render_template('duplicate_finder.html', ai_mode=AI_MODE)

@app.route('/ai_help')
def ai_help_page():
    """UI page for AI assisted analysis & log explanation (frontend only for now)."""
    return render_template('ai_help.html', ai_mode=AI_MODE)

@app.route('/api/ai/analyze_problem', methods=['POST'])
def api_ai_analyze_problem():
    """Analyze a problem (title+description+logs) using heuristic AI assistant.
    JSON body: {title, description, logs}
    Returns structured analysis sections. Safe for offline usage.
    """
    if get_ai_assistant is None:
        return jsonify({'error': 'ai_module_unavailable'}), 503
    try:
        data = request.get_json(force=True) or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        logs = data.get('logs') or ''
        if not (title or description):
            return jsonify({'error': 'missing_title_or_description'}), 400
        assistant = get_ai_assistant()
        result = assistant.analyze_problem(title, description, logs)
        return jsonify({
            'problem_hash': result.problem_hash,
            'summary': result.summary,
            'categories': result.categories,
            'sections': [{'title': s.title, 'details': s.details} for s in result.sections],
            'metrics': result.metrics,
            'generated_at': result.generated_at
        })
    except Exception as e:
        logger.exception('ai_analyze_problem error')
        return jsonify({'error': 'internal', 'detail': str(e)}), 500

@app.route('/api/ai/explain_logs', methods=['POST'])
def api_ai_explain_logs():
    """Explain raw logs with optional focus keyword.
    JSON body: {logs, focus}
    Returns heuristic findings & notable lines.
    """
    if get_ai_assistant is None:
        return jsonify({'error': 'ai_module_unavailable'}), 503
    try:
        data = request.get_json(force=True) or {}
        logs = data.get('logs') or ''
        focus = data.get('focus') or None
        if not logs.strip():
            return jsonify({'error': 'missing_logs'}), 400
        assistant = get_ai_assistant()
        result = assistant.explain_logs(logs, focus)
        return jsonify({
            'log_hash': result.log_hash,
            'findings': result.findings,
            'notable_lines': result.notable_lines,
            'summary': result.summary,
            'metrics': result.metrics,
            'generated_at': result.generated_at
        })
    except Exception as e:
        logger.exception('ai_explain_logs error')
        return jsonify({'error': 'internal', 'detail': str(e)}), 500

_translator_instance = None

def _get_translator(target_lang: str = 'en'):
    global _translator_instance
    if _translator_instance is None and SimpleTranslator is not None:
        _translator_instance = SimpleTranslator(target_lang=target_lang)
    return _translator_instance

@app.route('/translate', methods=['GET', 'POST'])
def translate_page():
    source_text = ''
    translated = ''
    meta = None
    target_lang = request.form.get('target_lang', 'en') if request.method == 'POST' else 'en'
    source_lang = request.form.get('source_lang') if request.method == 'POST' else ''
    if request.method == 'POST':
        source_text = request.form.get('source_text', '')
        if source_text.strip():
            translator = _get_translator(target_lang)
            if translator is None:
                translated = '[Translator module not available. Implement your model in translator/simple_translator.py]'
            else:
                result = translator.translate(source_text, source_lang or None)
                translated = result.translated_text
                meta = result.meta
    return render_template('translate.html', source_text=source_text, translated=translated, meta=meta, target_lang=target_lang, source_lang=source_lang, ai_mode=AI_MODE)

@app.route('/find-duplicates', methods=['POST'])
def find_duplicates():
    """Find duplicate issues based on problem title and content"""
    try:
        problem_title = request.form.get('problem_title', '').strip()
        problem_content = request.form.get('problem_content', '').strip()
        csv_file = request.files.get('csv_file')
        threshold = float(request.form.get('similarity_threshold', 80.0))
        # If AI_MODE is active, default semantic on unless user explicitly disabled
        use_semantic_form = request.form.get('use_semantic') == '1'
        if AI_MODE:
            use_semantic = True if AdvancedDuplicateFinder is not None else False
        else:
            use_semantic = use_semantic_form
        
        if not problem_title and not problem_content:
            flash('Please provide either problem title or content', 'error')
            return redirect(url_for('duplicate_finder'))
        
        if not csv_file or csv_file.filename == '':
            flash('Please upload a CSV file with issues database', 'error')
            return redirect(url_for('duplicate_finder'))
        
        if not allowed_file(csv_file.filename):
            flash('Please upload a valid CSV file', 'error')
            return redirect(url_for('duplicate_finder'))
        
        # Save CSV file temporarily
        csv_filename = secure_filename(csv_file.filename)
        csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
        csv_file.save(csv_path)
        
        # Initialize duplicate finder
        method_info = None
        if use_semantic and AdvancedDuplicateFinder is not None:
            # Use advanced finder with transformer (if bundled)
            duplicate_finder = AdvancedDuplicateFinder(csv_path, use_transformer=True)
            method_info = duplicate_finder.get_similarity_method_info()
        else:
            duplicate_finder = DuplicateFinder(csv_path)
            method_info = {
                'method': 'Lightweight Text Similarity',
                'model': 'N/A'
            }
        
        # Get database statistics
        stats = duplicate_finder.get_issue_statistics()
        
        if stats['total_issues'] == 0:
            flash('No valid issues found in CSV file. Please check the file format.', 'error')
            return redirect(url_for('duplicate_finder'))
        
        # Find duplicates
        if hasattr(duplicate_finder, 'find_duplicates'):
            duplicates = duplicate_finder.find_duplicates(
                problem_title,
                problem_content,
                threshold=threshold,
                max_results=5
            )
        else:
            duplicates = []
        
        # Clean up temporary CSV file
        try:
            os.remove(csv_path)
        except:
            pass
        
        # Prepare results
        results = {
            'problem_title': problem_title,
            'problem_content': problem_content,
            'similarity_threshold': threshold,
            'database_stats': stats,
            'duplicates_found': duplicates,
            'total_matches': len(duplicates),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'method_info': method_info or {}
        }
        results['ai_mode'] = AI_MODE
        return render_template('duplicate_results.html', result=results, ai_mode=AI_MODE)
    except Exception as e:
        logger.error(f"Error finding duplicates: {str(e)}")
        flash(f'Error finding duplicates: {str(e)}', 'error')
        return redirect(url_for('duplicate_finder'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'log_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('index'))

    file = request.files['log_file']
    main_issue_type = request.form.get('main_issue_type', '')
    sub_issue_type = request.form.get('sub_issue_type', '')
    package_name = request.form.get('package_name', '')

    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload .txt or .log files only.', 'error')
        return redirect(url_for('index'))

    if not main_issue_type or not sub_issue_type:
        flash('Please select both main issue type and sub-issue type', 'error')
        return redirect(url_for('index'))

    try:
        # Clear persistent cache before processing a new upload to avoid stale growth
        clear_persistent_cache()
        prune_cache_size()
        # Read entire log file once
        raw_bytes = file.read()
        size = len(raw_bytes)
        log_content = raw_bytes.decode('utf-8', errors='ignore')
        logger.info(f"UPLOAD size={size}B main={main_issue_type} sub={sub_issue_type}")
        log_id = _store_log_with_analyses(
            log_content,
            package_name,
            analyzer_factory=lambda: LogAnalyzer(),
            selected_pair=(main_issue_type, sub_issue_type)
        )
        current = LOG_CACHE[log_id]['analyses'].get((main_issue_type, sub_issue_type))
        current = dict(current)
        # Always set preview to analysis-only relevant logs (no global system properties)
        current['preview_log'] = _build_analysis_preview(current)
        # We no longer load or build full-log previews or summaries for the preview pane (always issue-only lines)
        current['raw_log_preview'] = ''
        current['raw_line_count'] = 0
        current['summary'] = ''
        current['log_id'] = log_id
        current['all_issue_types'] = ISSUE_TYPE_MAP
        # metrics removed from UI; keeping computation optional if needed elsewhere
        # current['metrics'] = _build_metrics(LOG_CACHE[log_id])
        current['main_issue_type'] = main_issue_type
        current['sub_issue_type'] = sub_issue_type
        current['selected_issue'] = f"{main_issue_type} - {sub_issue_type}"
        current['package_name'] = package_name
        from datetime import datetime as _dt
        current['timestamp'] = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        # TODO: Inline display enhancement: render on index without navigation (AJAX JSON response + DOM update)
        return render_template('results.html', result=current)
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API endpoint for programmatic analysis"""
    try:
        data = request.get_json()
        log_content = data.get('log_content', '')
        problem_description = data.get('problem_description', '')
        
        if not log_content or not problem_description:
            return jsonify({'error': 'Missing required fields'}), 400
        
        analyzer = LogAnalyzer()
        identified_issues = analyzer.identify_issue_type(log_content, problem_description)
        
        if not identified_issues:
            return jsonify({'message': 'No issues identified'}), 200
        
        primary_issue = list(identified_issues.keys())[0]
        relevant_logs = analyzer.extract_relevant_logs(log_content, primary_issue)
        root_cause = analyzer.analyze_root_cause(relevant_logs, primary_issue)
        
        return jsonify({
            'identified_issues': identified_issues,
            'primary_issue': primary_issue,
            'relevant_logs_count': len(relevant_logs),
            'root_cause': root_cause
        })
        
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Removed switch_issue & metrics endpoints as eager-mode multi-analysis selection is deprecated.

# =============================
# Smart Detection (AI) Prototype
# =============================
@app.route('/smart')
def smart_detection_page():
    return render_template('smart_detection.html', ai_mode=AI_MODE)

@app.route('/api/smart_detect', methods=['POST'])
def api_smart_detect():
    """Return top <=300 individual log lines matching problem description with score >= threshold.
    Input JSON: {problem_title, problem_content, log_text, threshold=0.8, max_lines=300, model=heuristic|sentiment_lexicon}
    heuristic: token overlap (with reboot boosters)
    sentiment_lexicon: same + negative sentiment boosting
    """
    try:
        data = request.get_json(force=True) or {}
        title = (data.get('problem_title') or '').strip()
        content = (data.get('problem_content') or '').strip()
        log_text = data.get('log_text') or ''
        threshold = float(data.get('threshold') or 0.8)
        max_lines = int(data.get('max_lines') or 300)
        model = (data.get('model') or 'heuristic').strip()
        if not title or not content or not log_text:
            return jsonify({'error': 'missing_fields'}), 400

        # Tokenize problem with stopword removal & domain detection
        def _tok(s: str):
            return [t for t in re.split(r'[^A-Za-z0-9_]+', s.lower()) if t]

        raw_prob_tokens = _tok(title + ' ' + content)
        stop = {
            'the','and','for','with','when','that','this','have','has','from','into','after','before','while','will','then','than','are','was','were','can','cannot','cant','could','should','would','about','upon','onto','during','user','issue','problem','device','system','log','logs','error','failure','fail','failing','crash','crashes','crashed','reboot','rebooting','restart','restarting'
        }
        prob_tokens = set(t for t in raw_prob_tokens if (len(t) > 2 and t not in stop) or t in {'cpu','ram','io'})
        if not prob_tokens:
            return jsonify({'error': 'no_tokens'}), 400

        text_lower = (title + ' ' + content).lower()
        reboot_mode = any(k in text_lower for k in ['reboot','restart','bootloop','boot loop','boot-loop','watchdog'])
        reboot_tokens = {'reboot','boot','booting','restarting','restart','watchdog','panic','kernel','shutdown','power','cold','warm','uptime','crash','crashing'}
        booster_tokens = reboot_tokens if reboot_mode else set()
        prob_tokens_all = prob_tokens | booster_tokens

        lines = log_text.splitlines()
        generic_config_patterns = [
            re.compile(r'^[A-Z][A-Za-z0-9_-]{1,32}:\s*$'),
            re.compile(r'^(KeyMgmt|PairwiseCiphers|GroupCiphers|Protocols|AuthAlgorithms)\b', re.IGNORECASE),
        ]
        reboot_noise_patterns = []
        if reboot_mode:
            reboot_noise_patterns = [
                re.compile(r'ContentProviderRecord', re.IGNORECASE),
                re.compile(r'^\s*Client:\s*$', re.IGNORECASE),
                re.compile(r'nothing to dump', re.IGNORECASE),
            ]

        def looks_like_config(line: str) -> bool:
            stripped = line.strip()
            if not stripped:
                return False
            if any(p.search(stripped) for p in generic_config_patterns):
                return True
            if ':' in stripped and len(stripped.split()) <= 6 and len(stripped) < 80:
                key = stripped.split(':',1)[0]
                if len(key) < 25 and key.isalpha():
                    return True
            return False

        excluded_config = 0
        zero_overlap = 0
        excluded_noise = 0

        # Sentiment lexicon (simple) for optional boosting
        if model == 'sentiment_lexicon':
            negative_terms = {
                'fail': -0.9,'failed': -1.0,'failure': -1.0,'crash': -1.0,'crashes': -1.0,'fatal': -1.0,'error': -0.8,'exception': -0.85,
                'anr': -0.9,'timeout': -0.7,'watchdog': -0.8,'panic': -1.0,'reset': -0.6,'reboot': -0.6,'overheat': -0.7,
                'denied': -0.5,'reject': -0.6,'corrupt': -0.9,'oom': -1.0,'leak': -0.7,'stuck': -0.6,'hang': -0.7
            }
            positive_terms = {'success': 0.4,'ok':0.2,'started':0.1,'initialized':0.15,'connected':0.2,'recovered':0.3,'resume':0.1}
            def sentiment_score(tokens):
                sc = 0.0
                for t in tokens:
                    if t in negative_terms:
                        sc += negative_terms[t]
                    elif t in positive_terms:
                        sc += positive_terms[t]
                return sc
        else:
            def sentiment_score(_tokens):
                return 0.0

        candidates = []
        for idx, line in enumerate(lines, start=1):
            ltoks = set(_tok(line))
            if not ltoks:
                continue
            base_overlap = len(prob_tokens & ltoks)
            boost_overlap = len(booster_tokens & ltoks) if booster_tokens else 0
            total_overlap = base_overlap + (2 * boost_overlap)
            if total_overlap == 0:
                zero_overlap += 1
                continue
            if reboot_mode and boost_overlap == 0 and looks_like_config(line):
                excluded_config += 1
                continue
            if reboot_mode and boost_overlap == 0 and any(p.search(line) for p in reboot_noise_patterns):
                excluded_noise += 1
                continue
            denom = len(prob_tokens_all) + 1e-6
            score = total_overlap / denom
            sentiment = None
            if model == 'sentiment_lexicon':
                sentiment = sentiment_score(ltoks)
                if sentiment < 0:
                    score *= (1 + min(0.5, abs(sentiment)))
                if score > 1:
                    score = 1.0
            match_tokens = sorted(prob_tokens_all & ltoks)
            candidates.append({
                'n': idx,
                'score': score,
                'text': line[:1000],
                'base_overlap': base_overlap,
                'booster_overlap': boost_overlap,
                'match_tokens': match_tokens,
                'sentiment': sentiment
            })

        candidates.sort(key=lambda d: (-d['score'], d['n']))
        filtered = []
        for c in candidates:
            if c['score'] >= threshold:
                filtered.append({
                    'n': c['n'],
                    'score': round(c['score'], 4),
                    'text': c['text'],
                    'base_overlap': c['base_overlap'],
                    'booster_overlap': c['booster_overlap'],
                    'match_tokens': c['match_tokens'],
                    'sentiment': c.get('sentiment')
                })
        truncated = False
        if len(filtered) > max_lines:
            filtered = filtered[:max_lines]
            truncated = True

        return jsonify({
            'problem': title,
            'threshold': threshold,
            'returned_count': len(filtered),
            'max_lines': max_lines,
            'total_lines_scanned': len(lines),
            'total_candidates': len(candidates),
            'above_threshold_count': sum(1 for c in candidates if c['score'] >= threshold),
            'truncated': truncated,
            'reboot_mode': reboot_mode,
            'problem_tokens': sorted(prob_tokens),
            'booster_tokens': sorted(booster_tokens),
            'excluded_config': excluded_config,
            'excluded_noise': excluded_noise,
            'zero_overlap': zero_overlap,
            'model': model,
            'lines': filtered
        })
    except Exception as e:
        logger.exception('smart_detect error')
        return jsonify({'error': 'internal', 'detail': str(e)}), 500

@app.route('/generate_overview', methods=['POST'])
def generate_overview():
    """On-demand generation of preview/summary/raw preview for lazy mode entries.
    Expects JSON: {log_id}
    """
    try:
        data = request.get_json() or {}
        log_id = data.get('log_id')
        if not log_id:
            return jsonify({'error': 'log_id required'}), 400
        entry = LOG_CACHE.get(log_id)
        if not entry:
            return jsonify({'error': 'Log not found'}), 404
        # If already eager or caches exist, just return existing (respecting new lazy suppression policy)
        log_text = entry['log']
        # Build caches
        if 'raw_log_preview_cache' not in entry:
            raw_lines = log_text.splitlines()
            entry['raw_log_preview_cache'] = '\n'.join(f"{i+1:6d} | {ln}" for i, ln in enumerate(raw_lines))
        if 'summary_cache' not in entry:
            try:
                entry['summary_cache'] = LogAnalyzer.extract_summary_sections(log_text)
            except Exception:
                entry['summary_cache'] = 'Failed to generate summary.'
        if 'preview_cache' not in entry:
            try:
                entry['preview_cache'] = LogAnalyzer.generate_preview(log_text)
            except Exception:
                entry['preview_cache'] = 'Failed to generate custom preview.'
        return jsonify({
            'log_id': log_id,
            'summary': entry.get('summary_cache',''),
            'preview_log': entry.get('preview_cache',''),
            'raw_log_preview': entry.get('raw_log_preview_cache','')
        })
    except Exception as e:
        logger.error(f"generate_overview error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/compare_issues', methods=['POST'])
def compare_issues():
    """Compare two issue analyses (intersection / unique relevant log counts)."""
    data = request.get_json() or {}
    log_id = data.get('log_id')
    a_main = data.get('a_main')
    a_sub = data.get('a_sub')
    b_main = data.get('b_main')
    b_sub = data.get('b_sub')
    if not all([log_id, a_main, a_sub, b_main, b_sub]):
        return jsonify({'error': 'Missing parameters'}), 400
    entry = LOG_CACHE.get(log_id)
    if not entry:
        return jsonify({'error': 'Log ID not found'}), 404
    a = _ensure_analysis(log_id, a_main, a_sub)
    b = _ensure_analysis(log_id, b_main, b_sub)
    # Build simple signature sets (line_number + first 40 chars of matched_line)
    def sig_set(res):
        out=set()
        for rl in res.get('relevant_logs', []):
            ln = rl.get('line_number')
            ml = (rl.get('matched_line') or '')[:40]
            out.add((ln, ml))
        return out
    set_a = sig_set(a)
    set_b = sig_set(b)
    intersection = set_a & set_b
    return jsonify({
        'a': {'main': a_main, 'sub': a_sub, 'count': len(set_a)},
        'b': {'main': b_main, 'sub': b_sub, 'count': len(set_b)},
        'intersection_count': len(intersection),
        'a_only': len(set_a - set_b),
        'b_only': len(set_b - set_a)
    })

@app.route('/raw_log/<log_id>')
def raw_log(log_id):
    """Return the full raw log as plain text for viewing/downloading."""
    entry = LOG_CACHE.get(log_id)
    if not entry:
        return 'Log not found or expired', 404
    from flask import Response
    return Response(entry['log'], mimetype='text/plain')

@app.route('/raw_log_chunk')
def raw_log_chunk():
    """Return a chunk of the raw log as JSON.
    Query params: log_id (required), start (1-based line), limit (default 1000)
    """
    log_id = request.args.get('log_id')
    try:
        start = int(request.args.get('start', '1'))
        limit = int(request.args.get('limit', '1000'))
    except ValueError:
        return jsonify({'error': 'Invalid start/limit'}), 400
    if limit <= 0 or limit > 20000:
        limit = 1000
    if start <= 0:
        start = 1
    entry = LOG_CACHE.get(log_id)
    if not entry:
        return jsonify({'error': 'Log not found'}), 404
    if 'log_lines' not in entry:
        entry['log_lines'] = entry['log'].splitlines()
    lines = entry['log_lines']
    total = len(lines)
    if start > total:
        return jsonify({'log_id': log_id, 'start': start, 'limit': limit, 'lines': [], 'has_more': False, 'total_lines': total})
    end = min(total, start + limit - 1)
    slice_lines = lines[start-1:end]
    out_lines = [{'n': i, 't': txt} for i, txt in zip(range(start, end+1), slice_lines)]
    has_more = end < total
    next_start = end + 1 if has_more else None
    return jsonify({
        'log_id': log_id,
        'start': start,
        'limit': limit,
        'lines': out_lines,
        'has_more': has_more,
        'next_start': next_start,
        'total_lines': total
    })

@app.route('/ai_status')
def ai_status():
    """Lightweight status endpoint describing AI mode and availability.
    Returns JSON: {ai_mode: bool, advanced_duplicate_available: bool, translator_available: bool}
    """
    return jsonify({
        'ai_mode': AI_MODE,
        'advanced_duplicate_available': AdvancedDuplicateFinder is not None,
        'translator_available': SimpleTranslator is not None
    })

if __name__ == '__main__':
    debug_flag = os.environ.get('PLM_DEBUG', '0') == '1'
    if AI_MODE and AdvancedDuplicateFinder is None:
        logger.warning('AI mode requested but advanced_duplicate_finder dependencies not available. Falling back to lightweight mode.')
    # Disable reloader to reduce connection refusals during code changes
    app.run(debug=debug_flag, use_reloader=False, host='0.0.0.0', port=5000)
