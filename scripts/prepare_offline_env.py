"""Prepare offline environment by downloading wheels & model files.

Run this script on an online machine:
    python scripts/prepare_offline_env.py --download-dir offline_bundle

Then copy the whole project folder INCLUDING the created offline_bundle/ directory
to the offline laptop. There you can run:
    pip install --no-index --find-links offline_bundle -r requirements.txt
    pip install --no-index --find-links offline_bundle -r requirements-ai.txt

It will also download the sentence-transformer model (all-MiniLM-L6-v2) into
offline_bundle/models/ so it can be loaded without network.
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path

BASE_REQUIREMENTS = 'requirements.txt'
AI_REQUIREMENTS = 'requirements-ai.txt'
DEFAULT_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

def run(cmd: list[str]):
    print('[RUN]', ' '.join(cmd))
    subprocess.check_call(cmd)

def download_wheels(download_dir: Path, req_file: str):
    if not Path(req_file).is_file():
        print(f'Skip {req_file} (missing)')
        return
    run([sys.executable, '-m', 'pip', 'download', '-r', req_file, '-d', str(download_dir), '--no-deps'])
    # Then download dependencies recursively for completeness
    run([sys.executable, '-m', 'pip', 'download', '-r', req_file, '-d', str(download_dir)])

def download_model(download_dir: Path, model_id: str):
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        run([sys.executable, '-m', 'pip', 'install', 'huggingface-hub'])
        from huggingface_hub import snapshot_download
    model_dir = download_dir / 'models'
    model_dir.mkdir(parents=True, exist_ok=True)
    print(f'Downloading model {model_id} ...')
    snapshot_download(repo_id=model_id, local_dir=model_dir / model_id.split('/')[-1], local_dir_use_symlinks=False)
    print('Model downloaded.')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--download-dir', default='offline_bundle', help='Target directory to place wheels and models')
    ap.add_argument('--model', default=DEFAULT_MODEL, help='Sentence-transformer model ID to pre-download')
    args = ap.parse_args()
    dl = Path(args.download_dir)
    dl.mkdir(parents=True, exist_ok=True)
    print('Downloading wheels (base)...')
    download_wheels(dl, BASE_REQUIREMENTS)
    print('Downloading wheels (AI)...')
    download_wheels(dl, AI_REQUIREMENTS)
    print('Downloading model...')
    download_model(dl, args.model)
    print('All artifacts prepared in', dl)

if __name__ == '__main__':
    main()
