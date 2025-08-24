import re
import os
from datetime import datetime

class LogAnalyzer:
    def __init__(self):
        self.issue_categories = {
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
        # Basic pattern map (placeholder) for identify_issue_type / extract_relevant_logs
        self.issue_patterns = {
            'App Crash': [r'FATAL EXCEPTION', r'Process:'],
            'ANR (Application Not Responding)': [r'ANR in', r'Input dispatching timed out'],
            'UI Issue': [r'ViewRootImpl', r'Choreographer'],
            'Network Issue': [r'HttpClient', r'ConnectException', r'SocketTimeoutException'],
            'Audio Problem': [r'AudioTrack', r'AudioManager'],
            'Memory Issue': [r'OutOfMemoryError', r'GC '],
        }
        # Simple keyword lists for fast substring scanning per (main_issue_type, sub_issue_type)
        # All keywords compared in lowercase.
        self.simple_keywords = {
            ('App Crashes', 'App Crashes'): ['fatal exception', 'process:'],
            ('App Crashes', 'App Force Stop'): ['force stopping', 'am_crash', 'force-stop'],
            ('App Crashes', 'ANR in App'): ['anr in', 'input dispatching timed out'],
            ('App Crashes', 'Device Reboot'): ['fatal exception in system process'],  # still handled specially
            ('Audio Issues', 'Noise in Audio'): ['audio', 'noise', 'underrun'],
            ('Audio Issues', 'Multiple Audio Output'): ['audiooutput', 'audiotrack'],
            ('Audio Issues', 'Audio Not Working'): ['no audio', 'audioflinger', 'audio service'],
            ('Network Issues', 'Connection Problems'): ['connectexception', 'failed to connect', 'unreachable'],
            ('Network Issues', 'HTTP Errors'): ['http 4', 'http 5', 'timeout', 'unknownhostexception'],
            ('Memory Issues', 'Out of Memory'): ['outofmemoryerror', 'oom', 'low memory'],
            ('UI Issues', 'Layout Problems'): ['constraintlayout', 'inflater', 'layout params'],
            ('UI Issues', 'UI Crashes'): ['viewrootimpl', 'nullpointerexception', 'illegalstateexception'],
        }

    # --- Individual category analyzers (kept minimal placeholders) ---
    def analyze_audio_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Audio Issues', sub_issue_type, 'Custom Audio Analysis')

    def analyze_camera_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Camera Issues', sub_issue_type, 'Custom Camera Analysis')

    def analyze_app_crashes(self, log_content, sub_issue_type, package_name=None):
        """Analyze App Crash related sub types.

        Enhancement: if the provided "log_content" string actually points to an existing
        file path on disk (user uploaded and you kept the path) we will stream that file
        line-by-line instead of operating on the in‑memory string. This avoids loading
        very large logs fully into memory just to find crash markers.

        Streaming is only applied for the generic "App Crashes" subtype (other subtypes
        keep existing logic or specialized extraction). If a path is used, we build
        blocks beginning with any fatal marker and capture stack lines until a blank
        line or a new timestamp entry that is not part of the stack.
        """
        relevant_logs = []
        if sub_issue_type == 'Device Reboot':
            last_fatal = self._extract_last_system_process_fatal(log_content)
            root_cause_analysis = 'No FATAL EXCEPTION IN SYSTEM PROCESS found.'
            if last_fatal:
                stack_text, line_number = last_fatal
                raw_lines = stack_text.split('\n')
                # Use only the first line (fatal header) as the matched line; suppress context to meet "matched lines only" requirement
                relevant_logs = [{
                    'line_number': line_number,
                    'matched_line': stack_text.split('\n')[0],
                    'type': 'FATAL_EXCEPTION_SYSTEM_PROCESS'
                }]
                root_cause_analysis = 'Last system process fatal exception captured.'
            return {
                'issue_type': f'App Crashes - {sub_issue_type}',
                'relevant_logs': relevant_logs,
                'root_cause': root_cause_analysis,
                'analysis_method': 'Last System Fatal Extraction',
                'single_stack': True
            }
        # If subtype is the generic crash group and log_content is an existing file path -> stream
        if sub_issue_type == 'App Crashes' and os.path.exists(log_content) and os.path.isfile(log_content):
            streamed = [s for s in self._stream_crash_headers(log_content) if 'fatal exception' in s['matched_line'].lower()]
            if streamed:
                return {
                    'issue_type': f'App Crashes - {sub_issue_type}',
                    'relevant_logs': streamed,
                    'root_cause': 'Fatal exception headers detected via streaming scan (file path).',
                    'analysis_method': 'Streaming Fatal Exception Header Scan'
                }
        # Fallback to original in‑memory scan (keywords)
        simple = self._simple_keyword_scan(log_content, 'App Crashes', sub_issue_type)
        if simple:
            return {
                'issue_type': f'App Crashes - {sub_issue_type}',
                'relevant_logs': simple,
                'root_cause': 'Preliminary keyword-based extraction (simple scan).',
                'analysis_method': 'Simple Keyword Scan'
            }
        return self._empty_result('App Crashes', sub_issue_type, 'Custom App Crash Analysis')

    def analyze_ui_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('UI Issues', sub_issue_type, 'Custom UI Analysis')

    def analyze_network_issues(self, log_content, sub_issue_type, package_name=None):
        simple = self._simple_keyword_scan(log_content, 'Network Issues', sub_issue_type)
        if simple:
            return {
                'issue_type': f'Network Issues - {sub_issue_type}',
                'relevant_logs': simple,
                'root_cause': 'Preliminary keyword-based extraction (simple scan).',
                'analysis_method': 'Simple Keyword Scan'
            }
        return self._empty_result('Network Issues', sub_issue_type, 'Custom Network Analysis')

    def analyze_multimedia_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Multimedia Issues', sub_issue_type, 'Custom Multimedia Analysis')

    def analyze_bluetooth_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Bluetooth Issues', sub_issue_type, 'Custom Bluetooth Analysis')

    def analyze_app_installation_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('App Installation Issues', sub_issue_type, 'Custom App Installation Analysis')

    def analyze_battery_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Battery Issues', sub_issue_type, 'Custom Battery Analysis')

    def analyze_storage_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Storage Issues', sub_issue_type, 'Custom Storage Analysis')

    def analyze_security_issues(self, log_content, sub_issue_type, package_name=None):
        return self._empty_result('Security Issues', sub_issue_type, 'Custom Security Analysis')

    def analyze_memory_issues(self, log_content, sub_issue_type, package_name=None):
        simple = self._simple_keyword_scan(log_content, 'Memory Issues', sub_issue_type)
        if simple:
            return {
                'issue_type': f'Memory Issues - {sub_issue_type}',
                'relevant_logs': simple,
                'root_cause': 'Preliminary keyword-based extraction (simple scan).',
                'analysis_method': 'Simple Keyword Scan'
            }
        return self._empty_result('Memory Issues', sub_issue_type, 'Custom Memory Analysis')

    # --- Dispatcher ---
    def analyze_issue_by_type(self, log_content, main_issue_type, sub_issue_type, package_name=None):
        if package_name:
            log_content = self.filter_logs_by_package(log_content, package_name)
        mapping = {
            'Audio Issues': self.analyze_audio_issues,
            'Camera Issues': self.analyze_camera_issues,
            'App Crashes': self.analyze_app_crashes,
            'UI Issues': self.analyze_ui_issues,
            'Network Issues': self.analyze_network_issues,
            'Multimedia Issues': self.analyze_multimedia_issues,
            'Bluetooth Issues': self.analyze_bluetooth_issues,
            'App Installation': self.analyze_app_installation_issues,
            'Battery Issues': self.analyze_battery_issues,
            'Storage Issues': self.analyze_storage_issues,
            'Security Issues': self.analyze_security_issues,
            'Memory Issues': self.analyze_memory_issues,
        }
        handler = mapping.get(main_issue_type)
        if handler:
            return handler(log_content, sub_issue_type, package_name)
        return {
            'issue_type': f'{main_issue_type} - {sub_issue_type}',
            'relevant_logs': [],
            'root_cause': f'Unknown issue type: {main_issue_type}',
            'analysis_method': 'Unknown Analysis Method'
        }

    # --- Utility methods ---
    def filter_logs_by_package(self, log_content, package_name):
        if not package_name:
            return log_content
        filtered = [ln for ln in log_content.split('\n') if package_name.lower() in ln.lower()]
        return '\n'.join(filtered) if filtered else log_content

    def extract_relevant_logs(self, log_content, issue_type):
        relevant_logs = []
        patterns = self.issue_patterns.get(issue_type, [])
        lines = log_content.split('\n')
        for i, line in enumerate(lines):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    context = lines[start:end]
                    relevant_logs.append({
                        'line_number': i + 1,
                        'context': context,
                        'matched_line': line.strip()
                    })
                    break
        return relevant_logs

    # --- Simple keyword scan helper ---
    def _simple_keyword_scan(self, log_content: str, main_issue_type: str, sub_issue_type: str):
        key = (main_issue_type, sub_issue_type)
        keywords = self.simple_keywords.get(key)
        if not keywords:
            return []
        keywords_lower = [k.lower() for k in keywords]
        restrict_activitymanager = False
        if key == ('App Crashes', 'App Crashes'):
            # Override: only keep 'fatal exception' lines per updated requirement (exclude process:, am_crash, fatal signal etc.)
            keywords_lower = ['fatal exception']
            restrict_activitymanager = True
        results = []
        # Simulate readline loop (no need to allocate all lines twice)
        lines = log_content.splitlines()
        for idx, line in enumerate(lines, start=1):
            low = line.lower()
            if restrict_activitymanager:
                # Skip noisy slow operation / battery stat lines
                if 'activitymanager' in low and ('slow operation' in low or 'starting to update pids map' in low or 'done updating pids map' in low):
                    continue
            matched_kw = None
            for kw in keywords_lower:
                if kw in low:
                    matched_kw = kw
                    break
            if matched_kw:
                results.append({
                    'line_number': idx,
                    'matched_line': line.rstrip(),
                    'keyword': matched_kw
                })
        return results

    def identify_issue_type(self, log_content, problem_description):
        findings = {}
        for key, pats in self.issue_patterns.items():
            count = 0
            for p in pats:
                count += len(re.findall(p, log_content, re.IGNORECASE))
            if count:
                findings[key] = count
        return dict(sorted(findings.items(), key=lambda kv: kv[1], reverse=True))

    def analyze_root_cause(self, relevant_logs, issue_type):
        if not relevant_logs:
            return 'No relevant logs found for analysis.'
        indicators = {
            'App Crash': ['NullPointerException', 'IndexOutOfBoundsException'],
            'ANR (Application Not Responding)': ['Input dispatching', 'Service'],
            'Memory Issue': ['OutOfMemoryError', 'GC ']
        }
        found = []
        for entry in relevant_logs:
            for ind in indicators.get(issue_type, []):
                if re.search(ind, entry['matched_line'], re.IGNORECASE):
                    found.append(f"Line {entry['line_number']}: {ind}")
        if found:
            return 'Root cause indicators found:\n' + '\n'.join(found[:5])
        return 'Root cause analysis requires more detailed log examination.'

    def _extract_last_system_process_fatal(self, log_content):
        pattern = re.compile(r'(FATAL EXCEPTION IN SYSTEM PROCESS[\s\S]*?)(?:\n\s*\n[^ \t]|\Z)', re.IGNORECASE)
        matches = list(pattern.finditer(log_content))
        if not matches:
            return None
        last = matches[-1]
        stack_text = last.group(1).rstrip()
        line_number = log_content.count('\n', 0, last.start()) + 1
        return stack_text, line_number

    def _stream_crash_headers(self, file_path):
        """Yield dictionaries representing crash header lines from a log file path.

        A crash 'header' is identified by containing any of the fatal markers. We only
        return the header line (no full stack) to satisfy the existing UI contract that
        expects a list of minimal matched_line entries. Extend later if needed.
        """
        fatal_markers = [
            'FATAL EXCEPTION',  # Java crash
            'FATAL EXCEPTION IN SYSTEM PROCESS',
            'Fatal signal',     # Native crash
            'am_crash',         # ActivityManager event
        ]
        try:
            with open(file_path, 'r', errors='ignore') as f:
                for idx, line in enumerate(f, start=1):
                    low = line.lower()
                    for mk in fatal_markers:
                        if mk.lower() in low:
                            yield {
                                'line_number': idx,
                                'matched_line': line.rstrip(),
                                'marker': mk
                            }
                            break
        except Exception:
            return

    def _format_stack_lines(self, lines):
        def classify(line: str):
            s = line.lstrip()
            if s.startswith('FATAL EXCEPTION IN SYSTEM PROCESS'): return 'header'
            if s.startswith('Caused by:'): return 'cause'
            if s.startswith('at '): return 'frame'
            if not s: return 'blank'
            return 'other'
        formatted=[]; prev=None
        for i,line in enumerate(lines):
            t=classify(line)
            if t=='blank': formatted.append(line); prev=t; continue
            if prev and t!=prev and t!='blank' and prev!='blank': formatted.append('')
            if t=='cause' and (not formatted or formatted[-1] != ''): formatted.append('')
            formatted.append(line)
            if t=='cause':
                for j in range(i+1, min(i+6, len(lines))):
                    nxt=classify(lines[j])
                    if nxt=='blank': continue
                    if nxt=='frame': formatted.append('')
                    break
            prev=t
        return formatted

    # --- Customizable preview hook ---
    @staticmethod
    def generate_preview(log_content: str, max_preview_lines: int = 800, max_crash_stack: int = 80) -> str:
        """Return a focused preview with ONLY useful basic information.

        Updated requirement: Remove showing arbitrary first-N lines. Instead show:
          1. Build / system properties (fingerprint, sdk, sales_code, release, flavor, display id, model)
          2. ALL crash stacks (lines containing 'FATAL EXCEPTION' including system process)
          3. ActivityManager crash events (lines containing 'am_crash') with one-line context before/after

        If nothing is found, return an explanatory message. Output preserves original line
        numbers as: "{line_number:6d} | original line". A soft cap (max_preview_lines)
        prevents UI overload.
        """
        lines = log_content.splitlines()
        out = []

        def add_section(title: str):
            if out and out[-1] != '':
                out.append('')
            out.append(f"==== {title} ====")

        import re as _re

        # 1. Build / system properties (scan first 5k lines to stay efficient)
        # Expanded list per request; ALWAYS display (even if missing) at top
        build_keys_order = [
            'ro.bootimage.build.fingerprint',
            'ro.system.build.fingerprint',
            'ro.build.version.sdk',
            'ro.system.build.version.sdk',
            'ro.build.version.release',
            'ro.build.flavor',
            'ro.system.build.type',
            'ro.build.display.id',
            'ro.product.model',
            'ro.product.system.model',
            'ro.product.vendor.device',
            'ro.product.locale',
            'ro.csc.sales_code',
            'ro.csc.country_code',
            'ro.com.google.gmsversion',
            'ro.com.google.clientidbase.pg2'
        ]
        wanted = set(build_keys_order)
        found = {}
        prop_re = _re.compile(r"^\s*\[(ro\.[^]]+)\]:\s*\[([^]]*)\]")
        # Scan the FULL log so properties that appear later are not missed (large logs may emit props mid-file).
        # For ultra-large files this is still linear and acceptable since we're already holding lines in memory.
        scan_limit = len(lines)
        for idx in range(scan_limit):
            m = prop_re.match(lines[idx])
            if not m:
                continue
            k = m.group(1)
            if k in wanted and k not in found:
                found[k] = (idx + 1, m.group(2))
            if len(found) == len(wanted):
                break
        # Alias fallback: if some canonical keys missing but close variants present, fill them.
        alias_map = {
            'ro.bootimage.build.fingerprint': ['ro.system.build.fingerprint', 'ro.build.fingerprint'],
            'ro.system.build.fingerprint': ['ro.build.fingerprint', 'ro.bootimage.build.fingerprint'],
        }
        for primary, alts in alias_map.items():
            if primary not in found:
                for alt in alts:
                    if alt in found:
                        # Reuse line number / value from alt indicating fallback
                        ln, val = found[alt]
                        found[primary] = (ln, val + ' (alias from ' + alt + ')')
                        break
        add_section('Build / System Properties')
        for k in build_keys_order:
            if k in found:
                _ln, val = found[k]
                out.append(f"[{k}]: [{val}]")
            else:
                out.append(f"[{k}]: [NOT FOUND]")

        # 2. All crash stacks (each 'FATAL EXCEPTION') with refined capture to avoid unrelated lines
        fatal_regex = _re.compile(r'FATAL EXCEPTION', _re.IGNORECASE)
        frame_regex = _re.compile(r"^\s*at ")
        caused_regex = _re.compile(r"^Caused by:")
        timestamp_regex = _re.compile(r"^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}")
        for idx, line in enumerate(lines):
            if fatal_regex.search(line):
                # Remove explicit line number from header per request
                add_section("Crash Stack")
                out.append(line)
                captured = 0
                saw_frame = False
                for j in range(idx + 1, len(lines)):
                    ln = lines[j]
                    if fatal_regex.search(ln) and j != idx:
                        break  # next crash starts
                    if not ln.strip():
                        out.append("")
                        break
                    if frame_regex.search(ln) or caused_regex.search(ln):
                        saw_frame = True
                        out.append(ln)
                    else:
                        if not saw_frame and not timestamp_regex.match(ln):
                            out.append(ln)
                        else:
                            break  # stop on unrelated timestamped line
                    captured += 1
                    if captured >= max_crash_stack:
                        out.append("... (stack truncated) ...")
                        break

        # 3. am_crash events with minimal context
        am_crash_regex = _re.compile(r'am_crash', _re.IGNORECASE)
        am_hits = [i for i,l in enumerate(lines) if am_crash_regex.search(l)]
        if am_hits:
            add_section('ActivityManager Crash Events (am_crash)')
            for pos in am_hits:
                start = max(0, pos - 1)
                end = min(len(lines), pos + 2)
                for j in range(start, end):
                    marker = '>' if j == pos else ' '
                    out.append(f"{marker} {lines[j]}")
                out.append('')
            if out and out[-1] == '':
                out.pop()

        # Soft cap total preview lines
        if len(out) > max_preview_lines:
            out = out[:max_preview_lines] + ['... (preview truncated at max_preview_lines) ...']

        if not out:
            return 'No build properties, crash stacks, or am_crash events found in log.'

        return '\n'.join(out)

    # --- Summary extraction (crashes, reboots, build props) ---
    @staticmethod
    def extract_summary_sections(log_content: str, max_stack_lines: int = 60):
        """Build a concise summary containing:
        - Selected build property lines (ro.bootimage.build.fingerprint, ro.build.version.sdk, ro.csc.sales_code, etc.)
        - All FATAL EXCEPTION stacks (first line + subsequent indented / 'at ' / cause lines until blank or limit)
        - System / device reboot indicators (watchdog, reboot, restarting system, FATAL EXCEPTION IN SYSTEM PROCESS)
        Returns a multi-line string with section headers and original line numbers preserved.
        """
        lines = log_content.splitlines()
        summary_lines = []

        def add_header(text):
            summary_lines.append("".ljust(0))  # ensure blank separation (no-op for first if empty)
            summary_lines.append(f"==== {text} ====")

        # 1. Build properties
        build_keys = [
            'ro.bootimage.build.fingerprint',
            'ro.system.build.fingerprint',
            'ro.build.version.sdk',
            'ro.system.build.version.sdk',
            'ro.csc.sales_code',
            'ro.csc.country_code',
            'ro.build.version.release',
            'ro.build.flavor',
            'ro.system.build.type',
            'ro.build.display.id',
            'ro.product.model',
            'ro.product.system.model',
            'ro.product.vendor.device',
            'ro.product.locale',
            'ro.com.google.gmsversion',
            'ro.com.google.clientidbase.pg2'
        ]
        prop_pattern = re.compile(r"^\s*\[(ro\.[^]]+)\]:\s*\[([^]]*)\]")
        found_props = {}
        for line in lines:
            m = prop_pattern.match(line)
            if m:
                key = m.group(1)
                if key in build_keys and key not in found_props:
                    found_props[key] = m.group(2)
                if len(found_props) == len(build_keys):
                    break
        add_header("Build / System Properties")
        for k in build_keys:
            if k in found_props:
                summary_lines.append(f"[{k}]: [{found_props[k]}]")
            else:
                summary_lines.append(f"[{k}]: [NOT FOUND]")

        # 2. Crash stacks (generic FATAL EXCEPTION)
        fatal_regex = re.compile(r"FATAL EXCEPTION", re.IGNORECASE)
        for i, l in enumerate(lines):
            if fatal_regex.search(l):
                add_header("Crash Stack")
                summary_lines.append(l)
                captured = 0
                for j in range(i+1, len(lines)):
                    nxt = lines[j]
                    if fatal_regex.search(nxt) and j != i:
                        break
                    if not nxt.strip():
                        summary_lines.append("")
                        break
                    summary_lines.append(nxt)
                    captured += 1
                    if captured >= max_stack_lines:
                        summary_lines.append("... (stack truncated) ...")
                        break

        # 3. Reboot / watchdog indicators
        reboot_patterns = [
            r"FATAL EXCEPTION IN SYSTEM PROCESS",
            r"watchdog", r"Watchdog", r"wdt", r"restarting system", r"Restarting system",
            r"lowlevel reboot", r"beginning of crash", r"Emergency reboot"
        ]
        reboot_regex = re.compile('|'.join(reboot_patterns), re.IGNORECASE)
        matches = []
        for line in lines:
            if reboot_regex.search(line):
                matches.append(line)
        if matches:
            add_header("Reboot / Watchdog Indicators")
            for txt in matches[:500]:  # safety cap
                summary_lines.append(txt)

        # Filter out leading blank if present
        cleaned = []
        for i,l in enumerate(summary_lines):
            if i==0 and not l.strip():
                continue
            cleaned.append(l)
        return '\n'.join(cleaned) if cleaned else 'No crash, reboot, or selected build info found.'

    def _empty_result(self, main, sub, method):
        return {
            'issue_type': f"{main} - {sub}",
            'relevant_logs': [],
            'root_cause': f"{main.split()[0]} analysis requires custom implementation",
            'analysis_method': method
        }
