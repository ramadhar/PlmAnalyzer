"""AI Assistant module for AI Help page.

Provides two core capabilities (initial stub implementation):
 1. analyze_problem: Given title, description, and optional logs, produce a structured analysis outline.
 2. explain_logs: Given raw logs and optional focus/problem context, extract notable patterns & summarize.

Design goals:
 - Pure Python with no heavyweight model dependency (placeholder heuristic logic) so page works offline.
 - Deterministic output for same inputs (good for tests) until real model integration added.
 - Clear extension points (strategy methods) where real LLM / embedding / rules engines can plug in.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re
import hashlib
import time

# ---------------------------------------------------------------------------
# Original user-provided prompt templates (retained verbatim where possible)
# ---------------------------------------------------------------------------
# These are NOT executed against an LLM yet (heuristic mode only). They are
# stored so future integration can forward the exact intended instructions.

PROBLEM_ANALYSIS_PROMPT_TEMPLATE = """You are a senior Android log analysis expert. Your task is to analyze logs and determine the cause of a user-reported issue.

You will be given:

A problem title
A detailed description/content of the issue
Logs from the device (may include system logs, crash logs, ANRs, etc.)

Your tasks are:

Analyze the logs in context of the reported problem.
Identify if the logs are related to the described problem or not.
If logs are not directly related, still attempt to identify the root cause based on available log patterns.
Clearly state whether the issue is caused by:
A third-party App
Samsung device hardware
Samsung software/firmware/OS
Or if more information is needed
Be specific and mention important logs or errors (e.g., stack traces, ANR, crashes, permission issues).
Keep the explanation simple, technical, and helpful for a support engineer or QA team.

Example format for your output:
Summary: [Short summary of the problem]

Log Analysis:

[Explain key log findings and relevance]
[List important timestamps, errors, or messages]
Root Cause: [Explain what likely caused the problem]

Source of Issue: [Third-party App / Samsung Device / Samsung Software / Unclear]

Recommendation:

[Steps or suggestions for further troubleshooting]
Now analyze the following:

Problem Title: {PROBLEM_TITLE}

Problem Description: {PROBLEM_CONTENT}

Logs:
{LOG_CONTENT}
"""

LOG_EXPLANATION_PROMPT_TEMPLATE = """You are an expert Android system and log analysis assistant.
I will provide you with raw log lines.

Your task is to:

Explain the meaning of each log line in clear and simple English.
Identify the related module or component (e.g., Framework, Network, GPU, Security, Modem, UI, Storage, etc.).
Explain the important keywords or technical terms used in the log line.
Identify the intent or sentiment of the log (e.g., Error, Warning, Success, Informational, Debug, Performance Issue).
If multiple log lines are related, summarize them together.
⚠️ Strict rule: Always explain in English only.
Do not return the logs in other languages.

Input Logs (sampled):
{LOG_SAMPLE}
"""

# Simple keyword buckets for heuristic analysis
_SYMPTOM_KEYWORDS = {
    'crash': ['crash', 'fatal', 'exception', 'signal', 'abort', 'anr'],
    'performance': ['slow', 'lag', 'freeze', 'hang', 'stutter'],
    'network': ['timeout', 'network', 'socket', 'http', 'request', 'response', 'disconnect'],
    'memory': ['oom', 'out of memory', 'leak', 'gc ', 'alloc'],
    'battery': ['battery', 'drain', 'power', 'wakelock'],
    'camera': ['camera', 'preview', 'record', 'frame', 'exposure'],
    'audio': ['audio', 'mic', 'speaker', 'pcm', 'volume', 'playback'],
}

_LOG_PATTERNS = {
    'exceptions': re.compile(r'(\b[A-Z][A-Za-z0-9_]+Exception\b|ANR in|Fatal signal)', re.IGNORECASE),
    'errors': re.compile(r'\b(E/|Error|ERROR)\b'),
    'warnings': re.compile(r'\b(W/|Warn|WARNING)\b'),
    'time_spikes': re.compile(r'([0-9]{2,}ms)')
}

@dataclass
class AnalysisSection:
    title: str
    details: List[str] = field(default_factory=list)

@dataclass
class AIAnalysisResult:
    problem_hash: str
    summary: str
    categories: List[str]
    sections: List[AnalysisSection]
    metrics: Dict[str, Any]
    generated_at: float

@dataclass
class LogExplanationResult:
    log_hash: str
    findings: List[str]
    notable_lines: List[Dict[str, Any]]
    summary: str
    metrics: Dict[str, Any]
    generated_at: float

class AIAssistant:
    """Core AI helper (stub heuristics). Replace internals with real model later."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze_problem(self, title: str, description: str, logs: str = '') -> AIAnalysisResult:
        """Produce structured analysis based on textual heuristics.

        Steps:
          1. Token scan across title + description (and logs if provided) to collect category hits.
          2. Extract exception / error signature lines from logs (top N) for context.
          3. Build outline sections (Symptoms, Suspected Domains, Next Steps, Evidence).
        """
        src = ' '.join(filter(None, [title, description]))
        combo = ' '.join(filter(None, [src, logs[:5000]]))  # cap logs for speed
        norm = combo.lower()
        categories = []
        cat_hits: Dict[str, int] = {}
        for cat, kws in _SYMPTOM_KEYWORDS.items():
            hits = sum(norm.count(k) for k in kws)
            if hits:
                categories.append(cat)
                cat_hits[cat] = hits
        categories.sort(key=lambda c: cat_hits[c], reverse=True)

        exception_lines = self._collect_exception_lines(logs)
        performance_lines = self._collect_performance_lines(logs)

        sections = [
            AnalysisSection('Symptoms Observed', self._build_symptom_points(src, categories)),
            AnalysisSection('Suspected Domains', [f'{c} (score {cat_hits[c]})' for c in categories] or ['Unclear - gather more context']),
            AnalysisSection('Key Exceptions', exception_lines[:5] or ['None detected in provided snippet']),
            AnalysisSection('Performance Indicators', performance_lines[:5] or ['No timing spikes detected']),
            AnalysisSection('Recommended Next Steps', self._recommended_next_steps(categories)),
            AnalysisSection('Evidence Snippet', [l[:160] for l in exception_lines[:3]] or ['N/A'])
        ]

        summary = self._build_summary(title, categories, exception_lines)
        metrics = {
            'category_hits': cat_hits,
            'exception_count': len(exception_lines),
            'performance_spikes': len(performance_lines),
            'text_length': len(src),
            'log_sampled_chars': len(logs[:5000])
        }
        problem_hash = hashlib.sha1(src.encode('utf-8', 'ignore')).hexdigest()[:12]
        return AIAnalysisResult(problem_hash, summary, categories, sections, metrics, time.time())

    def explain_logs(self, logs: str, focus: Optional[str] = None) -> LogExplanationResult:
        """Extract notable patterns from raw logs (heuristic draft)."""
        sample = logs[:20000]
        lines = sample.splitlines()
        notable: List[Dict[str, Any]] = []
        findings: List[str] = []
        err_ct = warn_ct = exc_ct = time_spike_ct = 0
        focus_lower = (focus or '').lower()
        for idx, line in enumerate(lines, start=1):
            l = line.strip()
            if not l:
                continue
            matched = False
            if _LOG_PATTERNS['exceptions'].search(l):
                exc_ct += 1
                notable.append({'n': idx, 'type': 'exception', 'text': l[:300]})
                matched = True
            if _LOG_PATTERNS['errors'].search(l):
                err_ct += 1
                if not matched:
                    notable.append({'n': idx, 'type': 'error', 'text': l[:300]})
                matched = True
            if _LOG_PATTERNS['warnings'].search(l):
                warn_ct += 1
                if not matched:
                    notable.append({'n': idx, 'type': 'warn', 'text': l[:300]})
                matched = True
            if _LOG_PATTERNS['time_spikes'].search(l):
                time_spike_ct += 1
                if not matched:
                    notable.append({'n': idx, 'type': 'timing', 'text': l[:300]})
                matched = True
            if focus_lower and focus_lower in l.lower():
                notable.append({'n': idx, 'type': 'focus', 'text': l[:300]})
        if err_ct:
            findings.append(f"Errors: {err_ct} lines contain error markers")
        if warn_ct:
            findings.append(f"Warnings: {warn_ct} lines with warnings")
        if exc_ct:
            findings.append(f"Exceptions/ANRs: {exc_ct} critical lines")
        if time_spike_ct:
            findings.append(f"Timing spikes: {time_spike_ct} lines with latency markers")
        if focus_lower:
            focus_hits = sum(1 for n in notable if n['type'] == 'focus')
            findings.append(f"Focus keyword '{focus_lower}' lines: {focus_hits}")
        if not findings:
            findings.append('No notable patterns found in sample (first 20k chars).')
        summary = self._build_log_summary(findings, len(lines), len(sample))
        metrics = {
            'lines_scanned': len(lines),
            'chars_scanned': len(sample),
            'notable_lines': len(notable),
            'error_lines': err_ct,
            'warning_lines': warn_ct,
            'exception_lines': exc_ct,
            'timing_spikes': time_spike_ct
        }
        log_hash = hashlib.sha1(sample.encode('utf-8','ignore')).hexdigest()[:12]
        return LogExplanationResult(log_hash, findings, notable[:80], summary, metrics, time.time())

    # ------------------------------------------------------------------
    # Prompt construction helpers (for future LLM integration)
    # ------------------------------------------------------------------
    def build_problem_prompt(self, title: str, description: str, logs: str) -> str:
        """Return the full problem analysis prompt (logs may be truncated)."""
        max_chars = 30000  # safeguard
        truncated_logs = logs[:max_chars]
        if len(logs) > max_chars:
            truncated_logs += "\n[... truncated ...]"
        return PROBLEM_ANALYSIS_PROMPT_TEMPLATE.format(
            PROBLEM_TITLE=title.strip() or 'Untitled',
            PROBLEM_CONTENT=description.strip() or '(no description provided)',
            LOG_CONTENT=truncated_logs or '(no logs provided)'
        )

    def build_log_explanation_prompt(self, logs: str) -> str:
        max_chars = 20000
        sample = logs[:max_chars]
        if len(logs) > max_chars:
            sample += "\n[... truncated ...]"
        return LOG_EXPLANATION_PROMPT_TEMPLATE.format(LOG_SAMPLE=sample or '(no logs provided)')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _collect_exception_lines(self, logs: str) -> List[str]:
        out=[]
        for ln in logs.splitlines():
            if 'Exception' in ln or 'ANR in' in ln or 'Fatal signal' in ln:
                out.append(ln.strip())
        return out

    def _collect_performance_lines(self, logs: str) -> List[str]:
        perf=[]
        for ln in logs.splitlines():
            if re.search(r'\b([0-9]{3,}ms)\b', ln):
                perf.append(ln.strip())
        return perf

    def _build_symptom_points(self, src: str, categories: List[str]) -> List[str]:
        points=[]
        if not categories:
            return ['Insufficient keyword matches for classification.']
        if 'crash' in categories:
            points.append('Application instability indicated (crash signatures present).')
        if 'performance' in categories:
            points.append('User-perceived lag or frame drop keywords detected.')
        if 'network' in categories:
            points.append('Potential connectivity / protocol timing problems.')
        if 'memory' in categories:
            points.append('Memory pressure or leak indications present.')
        if 'battery' in categories:
            points.append('Potential power consumption inefficiency.')
        if 'camera' in categories:
            points.append('Camera pipeline / capture subsystem involvement.')
        if 'audio' in categories:
            points.append('Audio stack / playback pathway referenced.')
        return points or ['General issue context without strong category signals.']

    def _recommended_next_steps(self, categories: List[str]) -> List[str]:
        steps = []
        if 'crash' in categories:
            steps.append('Collect full stack trace & reproduce under debugger.')
        if 'performance' in categories:
            steps.append('Profile critical path (traceview / systrace).')
        if 'network' in categories:
            steps.append('Capture network traffic & verify latency / retries.')
        if 'memory' in categories:
            steps.append('Run heap profiler to isolate leak suspects.')
        if 'battery' in categories:
            steps.append('Measure wakelocks & job scheduling patterns.')
        if 'camera' in categories:
            steps.append('Enable camera verbose logs; test under controlled lighting.')
        if 'audio' in categories:
            steps.append('Check audio routing & codec negotiation logs.')
        if not steps:
            steps.append('Request additional reproduction steps & environment details.')
        steps.append('Validate on latest build to rule out fixed regressions.')
        return steps

    def _build_summary(self, title: str, categories: List[str], exception_lines: List[str]) -> str:
        base = f"Issue: {title.strip() or 'Untitled'}"\
            + (f" | Domains: {', '.join(categories[:3])}" if categories else " | Domains: Unclassified")\
            + (f" | Exceptions: {len(exception_lines)}" if exception_lines else " | Exceptions: 0")
        return base

    def _build_log_summary(self, findings: List[str], line_count: int, chars: int) -> str:
        return f"Scanned {line_count} lines / {chars} chars. Key points: " + '; '.join(findings[:4])

# Singleton convenience (optional)
_ai_singleton: Optional[AIAssistant] = None

def get_ai_assistant() -> AIAssistant:
    global _ai_singleton
    if _ai_singleton is None:
        _ai_singleton = AIAssistant()
    return _ai_singleton
