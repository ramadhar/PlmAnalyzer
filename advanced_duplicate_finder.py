#!/usr/bin/env python3
"""
Advanced Duplicate Finder with Optional Sentence Transformer Support
This module provides enhanced duplicate detection using sentence transformers
when available, falling back to lightweight methods when not.

Usage:
    # Basic usage (lightweight)
    finder = AdvancedDuplicateFinder(csv_file_path)
    
    # With sentence transformer (if available)
    finder = AdvancedDuplicateFinder(csv_file_path, use_transformer=True)
"""

import os
import csv
import re
import difflib
import math
import hashlib
import json
import pickle
from dataclasses import dataclass
from collections import Counter
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

@dataclass
class _EmbeddingMeta:
    csv_path: str
    csv_sha256: str
    model_name: str
    embedding_dim: int
    issue_count: int


class AdvancedDuplicateFinder:
    """Advanced duplicate finder with optional sentence transformer support"""
    def __init__(self,
                 csv_file_path: str | None = None,
                 use_transformer: bool = False,
                 model_name: str = 'all-MiniLM-L6-v2',
                 cache_dir: str = 'cache',
                 enable_translation: bool = False,
                 translation_target_lang: str = 'en'):
        self.issues_database: list[dict] = []
        self.csv_file_path = csv_file_path
        self.use_transformer = use_transformer
        self.transformer_model = None
        self.model_name = model_name
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.enable_translation = enable_translation
        self.translation_target_lang = translation_target_lang
        self._translator = None
        self._lang_detector_ready = False
        # Embedding cache statistics
        self.cache_hit = False
        self.cache_miss = False
        self._last_cache_files: Tuple[str, str] | None = None

        # Load issues & initialize optional components
        if self.csv_file_path and os.path.exists(self.csv_file_path):
            self.load_issues_from_csv(self.csv_file_path)
        if self.use_transformer:
            self._initialize_transformer()
        if self.enable_translation:
            self._initialize_translation()

    def _initialize_translation(self):
        try:
            from deep_translator import GoogleTranslator  # noqa: F401
            from langdetect import detect  # noqa: F401
            self._translator = GoogleTranslator(source='auto', target=self.translation_target_lang)
            self._lang_detector_ready = True
        except Exception as e:
            logger.warning(f"Translation support not available: {e}")
            self.enable_translation = False
    
    def _csv_sha256(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def _cache_files(self) -> Tuple[str, str]:
        """Return paths for embedding and meta cache files for current CSV/model."""
        if not self.csv_file_path:
            return "", ""
        base = os.path.splitext(os.path.basename(self.csv_file_path))[0]
        emb_file = os.path.join(self.cache_dir, f"{base}.{self.model_name}.embeddings.pkl")
        meta_file = os.path.join(self.cache_dir, f"{base}.{self.model_name}.meta.json")
        self._last_cache_files = (emb_file, meta_file)
        return emb_file, meta_file

    def _load_cached_embeddings(self) -> bool:
        emb_file, meta_file = self._cache_files()
        if not (emb_file and os.path.isfile(emb_file) and os.path.isfile(meta_file)):
            return False
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            current_hash = self._csv_sha256(self.csv_file_path)
            if meta.get('csv_sha256') != current_hash:
                return False
            with open(emb_file, 'rb') as f:
                embeddings = pickle.load(f)
            if len(embeddings) != len(self.issues_database):
                return False
            for issue, emb in zip(self.issues_database, embeddings):
                issue['_embedding'] = emb
            logger.info("Loaded cached embeddings (%d) from %s", len(embeddings), emb_file)
            self.cache_hit = True
            return True
        except Exception as e:
            logger.warning("Failed loading cached embeddings: %s", e)
            return False

    def _save_cached_embeddings(self):
        emb_file, meta_file = self._cache_files()
        if not emb_file:
            return
        try:
            embeddings = [i.get('_embedding') for i in self.issues_database]
            with open(emb_file, 'wb') as f:
                pickle.dump(embeddings, f)
            meta = _EmbeddingMeta(
                csv_path=self.csv_file_path,
                csv_sha256=self._csv_sha256(self.csv_file_path),
                model_name=self.model_name,
                embedding_dim=int(getattr(embeddings[0], 'shape', [0])[-1]) if embeddings and embeddings[0] is not None else 0,
                issue_count=len(embeddings)
            )
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(meta.__dict__, f, indent=2)
            logger.info("Saved embeddings cache to %s", emb_file)
        except Exception as e:
            logger.warning("Failed saving embeddings cache: %s", e)

    def _initialize_transformer(self):
        """Initialize sentence transformer if available"""
        try:
            # Try to import sentence transformers
            from sentence_transformers import SentenceTransformer
            import torch
            
            # Use a lightweight model to minimize size
            model_name = self.model_name  # allow override
            logger.info(f"Initializing sentence transformer: {model_name}")
            self.transformer_model = SentenceTransformer(model_name)
            
            # Pre-compute embeddings for all issues
            self._compute_issue_embeddings()
            
            logger.info("Sentence transformer initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Sentence transformers not available: {e}")
            logger.info("Falling back to lightweight similarity methods")
            self.use_transformer = False
            self.transformer_model = None
        except Exception as e:
            logger.error(f"Error initializing transformer: {e}")
            self.use_transformer = False
            self.transformer_model = None
    
    def _compute_issue_embeddings(self):
        """Pre-compute embeddings for all issues in database"""
        if not self.transformer_model or not self.issues_database:
            return
        
        logger.info("Computing embeddings for all issues...")
        # Try cache first
        if self._load_cached_embeddings():
            return
        
        # Prepare texts for embedding
        issue_texts = []
        for issue in self.issues_database:
            title = issue.get('problem_title', '') or issue.get('title', '') or issue.get('issue_title', '')
            description = issue.get('problem_description', '') or issue.get('description', '') or issue.get('issue_description', '')
            logs = issue.get('logs_analysis', '') or issue.get('logs', '') or issue.get('analysis', '')
            
            combined_text = f"{title} {description} {logs}".strip()
            issue_texts.append(combined_text)
        
        # Compute embeddings
        try:
            embeddings = self.transformer_model.encode(issue_texts, convert_to_tensor=True, show_progress_bar=False, batch_size=64)
            
            # Store embeddings with issues
            for i, issue in enumerate(self.issues_database):
                issue['_embedding'] = embeddings[i]
            
            logger.info(f"Computed embeddings for {len(self.issues_database)} issues")
            self._save_cached_embeddings()
            self.cache_miss = True  # We had to compute embeddings (i.e., cache miss)
            
        except Exception as e:
            logger.error(f"Error computing embeddings: {e}")
            self.use_transformer = False
            self.transformer_model = None
    
    def load_issues_from_csv(self, csv_file_path: str):
        """Load issues from CSV file"""
        try:
            with open(csv_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    # Normalize column names
                    normalized_row = {}
                    for key, value in row.items():
                        normalized_key = key.strip().lower().replace(' ', '_')
                        normalized_row[normalized_key] = value.strip() if value else ""
                    
                    # Ensure required fields exist
                    if 'plm_id' in normalized_row and normalized_row['plm_id']:
                        self.issues_database.append(normalized_row)
            
            logger.info(f"Loaded {len(self.issues_database)} issues from CSV")
            
            # Recompute embeddings if transformer is available
            if self.transformer_model:
                self._compute_issue_embeddings()
                
        except Exception as e:
            logger.error(f"Error loading CSV: {str(e)}")
            self.issues_database = []
    
    def _maybe_translate(self, text: str) -> str:
        if not (self.enable_translation and self._translator and text):
            return text
        try:
            from langdetect import detect
            lang = detect(text)
            if lang and lang.lower().startswith(self.translation_target_lang.lower()):
                return text
            translated = self._translator.translate(text)
            return translated or text
        except Exception as e:
            logger.debug(f"Translation skipped: {e}")
            return text

    def preprocess_text(self, text: str) -> str:
        """Preprocess text for better similarity matching"""
        if not text:
            return ""

        # Optionally translate to target language first
        text = self._maybe_translate(text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def calculate_transformer_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity using sentence transformer"""
        if not self.transformer_model:
            return 0.0
        
        try:
            # Encode both texts
            embeddings = self.transformer_model.encode([text1, text2], convert_to_tensor=True)
            
            # Calculate cosine similarity
            from torch.nn.functional import cosine_similarity
            similarity = cosine_similarity(embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0))
            
            # Convert to percentage (0-100)
            return float(similarity.item() * 100)
            
        except Exception as e:
            logger.error(f"Error calculating transformer similarity: {e}")
            return 0.0
    
    def calculate_lightweight_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity using lightweight methods"""
        if not text1 or not text2:
            return 0.0
        
        # Preprocess texts
        processed_text1 = self.preprocess_text(text1)
        processed_text2 = self.preprocess_text(text2)
        
        if not processed_text1 or not processed_text2:
            return 0.0
        
        # Method 1: Sequence Matcher (good for overall similarity)
        sequence_score = difflib.SequenceMatcher(None, processed_text1, processed_text2).ratio()
        
        # Method 2: Word overlap (good for keyword matching)
        words1 = set(processed_text1.split())
        words2 = set(processed_text2.split())
        
        if words1 and words2:
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            word_overlap_score = len(intersection) / len(union) if union else 0.0
        else:
            word_overlap_score = 0.0
        
        # Method 3: Length similarity (penalize very different lengths)
        len1, len2 = len(processed_text1), len(processed_text2)
        length_similarity = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 0.0
        
        # Method 4: Common phrase detection
        phrase_score = self._calculate_phrase_similarity(processed_text1, processed_text2)
        
        # Weighted combination of all scores
        final_score = (
            sequence_score * 0.4 +      # 40% weight to sequence similarity
            word_overlap_score * 0.3 +   # 30% weight to word overlap
            length_similarity * 0.2 +    # 20% weight to length similarity
            phrase_score * 0.1           # 10% weight to phrase similarity
        )
        
        return round(final_score * 100, 2)  # Convert to percentage
    
    def _calculate_phrase_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity based on common phrases"""
        # Extract 3-4 word phrases
        words1 = text1.split()
        words2 = text2.split()
        
        phrases1 = set()
        phrases2 = set()
        
        # Generate 3-word phrases
        for i in range(len(words1) - 2):
            phrases1.add(' '.join(words1[i:i+3]))
        
        for i in range(len(words2) - 2):
            phrases2.add(' '.join(words2[i:i+3]))
        
        # Generate 4-word phrases
        for i in range(len(words1) - 3):
            phrases1.add(' '.join(words1[i:i+4]))
        
        for i in range(len(words2) - 3):
            phrases2.add(' '.join(words2[i:i+4]))
        
        if phrases1 and phrases2:
            intersection = phrases1.intersection(phrases2)
            union = phrases1.union(phrases2)
            return len(intersection) / len(union) if union else 0.0
        
        return 0.0
    
    def find_duplicates(self, problem_title: str, problem_content: str, 
                       threshold: float = 80.0, max_results: int = 5) -> List[Dict]:
        """Find duplicate issues above similarity threshold"""
        if not self.issues_database:
            return []
        
        # Combine title and content for analysis
        combined_input = f"{problem_title} {problem_content}"
        if self.enable_translation:
            combined_input = self._maybe_translate(combined_input)
        
        # Calculate similarity scores for all issues
        scored_issues = []
        
        for issue in self.issues_database:
            # Get issue text (combine title and description)
            issue_title = issue.get('problem_title', '') or issue.get('title', '') or issue.get('issue_title', '')
            issue_description = issue.get('problem_description', '') or issue.get('description', '') or issue.get('issue_description', '')
            issue_logs = issue.get('logs_analysis', '') or issue.get('logs', '') or issue.get('analysis', '')
            
            issue_text = f"{issue_title} {issue_description} {issue_logs}"
            if self.enable_translation:
                issue_text = self._maybe_translate(issue_text)
            
            # Calculate similarity score using appropriate method
            if self.use_transformer and self.transformer_model:
                similarity_score = self.calculate_transformer_similarity(combined_input, issue_text)
            else:
                similarity_score = self.calculate_lightweight_similarity(combined_input, issue_text)
            
            if similarity_score >= threshold:
                scored_issues.append({
                    'plm_id': issue.get('plm_id', 'Unknown'),
                    'title': issue_title,
                    'description': issue_description,
                    'similarity_score': similarity_score,
                    'logs_analysis': issue_logs,
                    'issue_data': issue,  # Keep full issue data for reference
                    'method_used': 'Transformer' if self.use_transformer else 'Lightweight'
                })
        
        # Sort by similarity score (highest first) and limit results
        scored_issues.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored_issues[:max_results]
    
    def get_issue_statistics(self) -> Dict:
        """Get statistics about the loaded issues database"""
        if not self.issues_database:
            return {
                'total_issues': 0,
                'unique_plm_ids': 0,
                'sample_columns': [],
                'transformer_available': self.use_transformer
            }
        
        unique_plm_ids = set()
        for issue in self.issues_database:
            if issue.get('plm_id'):
                unique_plm_ids.add(issue['plm_id'])
        
        sample_columns = list(self.issues_database[0].keys()) if self.issues_database else []
        
        return {
            'total_issues': len(self.issues_database),
            'unique_plm_ids': len(unique_plm_ids),
            'sample_columns': sample_columns,
            'transformer_available': self.use_transformer,
            'transformer_model': self.transformer_model.__class__.__name__ if self.transformer_model else 'None'
        }
    
    def get_similarity_method_info(self) -> Dict:
        """Get information about the similarity method being used"""
        if self.use_transformer and self.transformer_model:
            return {
                'method': 'Sentence Transformer',
                'model': self.transformer_model.__class__.__name__,
                'accuracy': 'High',
                'speed': 'Medium',
                'memory_usage': 'High',
                'description': 'Uses advanced neural network embeddings for semantic similarity',
                'cache': self.get_cache_stats()
            }
        else:
            return {
                'method': 'Lightweight Text Similarity',
                'model': 'Rule-based algorithms',
                'accuracy': 'Medium',
                'speed': 'Fast',
                'memory_usage': 'Low',
                'description': 'Uses text preprocessing, word overlap, and sequence matching',
                'cache': self.get_cache_stats()
            }

    def get_cache_stats(self) -> Dict:
        emb_file, meta_file = self._last_cache_files if self._last_cache_files else ('', '')
        return {
            'embedding_cache_hit': self.cache_hit,
            'embedding_cache_miss': self.cache_miss,
            'embedding_cache_files': {
                'embeddings': emb_file,
                'meta': meta_file
            }
        }

# Example usage and testing
if __name__ == "__main__":
    # Test the advanced duplicate finder
    print("Testing Advanced Duplicate Finder...")
    
    # Create a test instance (without transformer for now)
    finder = AdvancedDuplicateFinder(use_transformer=False)
    
    # Test similarity calculation
    text1 = "Camera app crashes when switching to front camera"
    text2 = "Camera application freezes when changing to selfie mode"
    
    similarity = finder.calculate_lightweight_similarity(text1, text2)
    print(f"Similarity between texts: {similarity:.2f}%")
    
    print("Advanced Duplicate Finder test completed!")
