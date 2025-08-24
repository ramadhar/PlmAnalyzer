import os
import tempfile
import csv
from advanced_duplicate_finder import AdvancedDuplicateFinder


def _make_csv(rows):
    fd, path = tempfile.mkstemp(suffix='.csv', text=True)
    os.close(fd)
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def test_lightweight_similarity_and_duplicates():
    path = _make_csv([
        {"PLM_ID": "A1", "problem_title": "Camera crash", "problem_description": "App crashes switching to front camera"},
        {"PLM_ID": "B2", "problem_title": "Battery drain", "problem_description": "High battery usage overnight"},
    ])
    try:
        finder = AdvancedDuplicateFinder(path, use_transformer=False)
        sims = finder.find_duplicates("Camera app crashes", "Crashes when switching camera", threshold=40, max_results=3)
        assert sims, "Expected at least one duplicate"
        assert sims[0]['plm_id'] == 'A1'
        info = finder.get_similarity_method_info()
        assert info['method'] == 'Lightweight Text Similarity'
    finally:
        os.remove(path)


def test_cache_stats_structure():
    path = _make_csv([
        {"PLM_ID": "C3", "problem_title": "WiFi disconnects", "problem_description": "WiFi disconnecting randomly"},
    ])
    try:
        finder = AdvancedDuplicateFinder(path, use_transformer=False)
        stats = finder.get_cache_stats()
        # For lightweight mode cache values default false
        assert 'embedding_cache_hit' in stats
        assert stats['embedding_cache_hit'] in (True, False)
    finally:
        os.remove(path)
