"""Simple translation stub.

This module provides a placeholder translation interface used by the
Translate tab. Replace the body of `SimpleTranslator.translate` with
your offline / on-device model inference (e.g., MarianMT, M2M100,
NLLB, custom quantized model, etc.). Keep the method synchronous or
adapt the route to async if you integrate an async engine.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
import threading
import time

try:
    # deep_translator part of requirements-ai.txt; available offline if wheels installed
    from deep_translator import GoogleTranslator
    _DT_AVAILABLE = True
except Exception:
    GoogleTranslator = None  # type: ignore
    _DT_AVAILABLE = False

try:
    from langdetect import detect  # lightweight language detection
    _LD_AVAILABLE = True
except Exception:
    detect = None  # type: ignore
    _LD_AVAILABLE = False


@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    detected_source_lang: Optional[str] = None
    target_lang: str = "en"
    meta: Dict[str, str] | None = None


class SimpleTranslator:
    """Pluggable translator stub.

    Replace `translate` logic with real model invocation. For example:

        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        ... load model once in __init__ ...
        def translate(...):
            tokens = self.tokenizer(text, return_tensors='pt')
            out = self.model.generate(**tokens, max_new_tokens=256)
            return decoded

    Keep a lightweight cache if desired.
    """
    def __init__(self, target_lang: str = "en", cache_ttl: int = 3600, enable_translation: bool = True):
        self.target_lang = target_lang
        self.enable_translation = enable_translation and _DT_AVAILABLE
        self._translator = None
        self._cache_ttl = cache_ttl
        self._cache: dict[tuple[str, str], tuple[float, TranslationResult]] = {}
        self._lock = threading.Lock()
        if self.enable_translation:
            try:
                # Instantiate underlying translator lazily; GoogleTranslator can auto-detect source
                self._translator = GoogleTranslator(source='auto', target=self.target_lang)
            except Exception:
                self.enable_translation = False

    def _cache_get(self, key: tuple[str, str]) -> Optional[TranslationResult]:
        with self._lock:
            item = self._cache.get(key)
            if not item:
                return None
            ts, res = item
            if (time.time() - ts) > self._cache_ttl:
                self._cache.pop(key, None)
                return None
            return res

    def _cache_put(self, key: tuple[str, str], res: TranslationResult):
        with self._lock:
            self._cache[key] = (time.time(), res)
            # Simple size guard
            if len(self._cache) > 500:
                # Drop oldest half
                items = sorted(self._cache.items(), key=lambda kv: kv[1][0])
                for k, _ in items[: len(items)//2]:
                    self._cache.pop(k, None)

    def translate(self, text: str, source_lang: Optional[str] = None) -> TranslationResult:
        if not text.strip():
            return TranslationResult(original_text=text, translated_text="(empty input)")

        detected = source_lang
        if not detected and _LD_AVAILABLE:
            try:
                detected = detect(text)
            except Exception:
                detected = None
        detected = detected or 'auto'

        key = (detected, text.strip())
        cached = self._cache_get(key)
        if cached:
            return TranslationResult(
                original_text=text,
                translated_text=cached.translated_text,
                detected_source_lang=cached.detected_source_lang,
                target_lang=self.target_lang,
                meta={**(cached.meta or {}), 'cache': 'hit'}
            )

        if not self.enable_translation or not self._translator:
            translated = text if detected.startswith(self.target_lang) else f"[no-engine:{self.target_lang}] {text}"
            res = TranslationResult(
                original_text=text,
                translated_text=translated,
                detected_source_lang=detected,
                target_lang=self.target_lang,
                meta={"engine": "stub", "note": "deep_translator not available", "cache": "miss"}
            )
            self._cache_put(key, res)
            return res

        try:
            translated = self._translator.translate(text)
        except Exception as e:
            translated = text
            engine_meta = {"engine": "deep_translator", "error": str(e), "cache": "miss"}
        else:
            engine_meta = {"engine": "deep_translator", "cache": "miss"}

        res = TranslationResult(
            original_text=text,
            translated_text=translated,
            detected_source_lang=detected,
            target_lang=self.target_lang,
            meta=engine_meta
        )
        self._cache_put(key, res)
        return res

__all__ = ["SimpleTranslator", "TranslationResult"]
