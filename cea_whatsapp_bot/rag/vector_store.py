# rag/vector_store.py — versión sin FAISS (usa numpy + coseno)
from typing import List, Tuple
import os, glob, re
from dataclasses import dataclass
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # degrade si no está

@dataclass
class DocChunk:
    text: str
    source: str

class VectorStore:
    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.model = None
        self.chunks: List[DocChunk] = []
        self.embs: np.ndarray | None = None

    def _load_model(self):
        if SentenceTransformer and self.model is None:
            # modelo ligero y estable
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def load(self):
        # 1) carga textos
        paths = glob.glob(os.path.join(self.kb_path, "**", "*.md"), recursive=True)
        texts: List[str] = []
        for p in paths:
            raw = open(p, "r", encoding="utf-8").read()
            for block in re.split(r"\n\n+", raw):
                t = block.strip()
                if len(t) > 40:
                    texts.append(t)
                    self.chunks.append(DocChunk(text=t, source=p))
        if not texts:
            self.embs = None
            return

        # 2) crea embeddings en memoria (sin FAISS)
        self._load_model()
        if self.model is None:
            # sin modelo, degradar a búsqueda por keywords
            self.embs = None
            return

        X = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        self.embs = X  # (n, d) normalizados

    def _keyword_search(self, query: str, k: int = 3) -> List[Tuple[str, str]]:
        q = (query or "").lower()
        if not q or not self.chunks:
            return []
        scored = []
        q_words = [w for w in re.split(r"\W+", q) if w]
        for c in self.chunks:
            text_l = c.text.lower()
            score = sum(text_l.count(w) for w in q_words)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(c.text, c.source) for score, c in scored[:k]]

    def search(self, query: str, k: int = 3) -> List[Tuple[str, str]]:
        if self.embs is None:
            # no embeddings → keyword
            return self._keyword_search(query, k)

        # similitud coseno = dot porque ya normalizamos
        qv = self.model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
        sims = np.dot(self.embs, qv)  # (n,)
        idxs = np.argsort(-sims)[:k]
        out = []
        for i in idxs:
            out.append((self.chunks[i].text, self.chunks[i].source))
        return out
