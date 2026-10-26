"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re

# Common words that carry little meaning and would otherwise dominate scores
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "i", "in", "is", "it", "of", "on", "or", "that",
    "the", "there", "these", "this", "to", "what", "when", "where", "which",
    "who", "with", "any",
}

# Guardrail: a snippet must score at least this much to count as evidence.
# If no snippet reaches it, DocuBot refuses instead of guessing.
MIN_SCORE = 2


def tokenize(text):
    """
    Lowercases text and splits it into words, dropping punctuation
    and stopwords. Underscores are kept so names like auth_utils stay whole.
    """
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return [w for w in words if w not in STOPWORDS]


def split_into_sections(filename, text):
    """
    Splits a markdown document into one snippet per heading. Each snippet
    starts at a line beginning with '#' and runs until the next heading.
    Returns a list of (filename, section_text) tuples.
    """
    sections = re.split(r"\n(?=#)", text)
    return [(filename, section.strip()) for section in sections if section.strip()]


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split documents into smaller sections so retrieval returns focused snippets
        self.sections = []  # List of (filename, section_text)
        for filename, text in self.documents:
            self.sections.extend(split_into_sections(filename, text))

        # Build a retrieval index over sections (implemented in Phase 1)
        self.index = self.build_index(self.sections)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the sections
        they appear in. Sections are identified by their position in the
        list passed in (self.sections).

        Example structure:
        {
            "token": [3, 4, 15],
            "database": [22, 23]
        }
        """
        index = {}
        for position, (_, text) in enumerate(documents):
            for word in set(tokenize(text)):
                index.setdefault(word, []).append(position)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        text_words = tokenize(text)
        score = 0
        for word in set(tokenize(query)):
            score += text_words.count(word)
        return score

    def retrieve(self, query, top_k=3):
        """
        TODO (Phase 1):
        Use the index and scoring function to select top_k relevant document snippets.

        Return a list of (filename, text) sorted by score descending.
        Snippets scoring below MIN_SCORE are dropped, so an empty list means
        the docs hold no meaningful evidence and the caller should refuse.
        """
        # Use the index to find sections sharing at least one query word
        candidates = set()
        for word in tokenize(query):
            candidates.update(self.index.get(word, []))

        scored = []
        for position in sorted(candidates):
            filename, text = self.sections[position]
            score = self.score_document(query, text)
            if score >= MIN_SCORE:
                scored.append((score, filename, text))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = [(filename, text) for _, filename, text in scored]
        return results[:top_k]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
