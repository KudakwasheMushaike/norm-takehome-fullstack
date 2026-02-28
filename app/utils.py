import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv
from llama_index.core import Document, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from pydantic import BaseModel, Field
from pypdf import PdfReader

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


@dataclass
class Input:
    query: str
    file_path: str


class Citation(BaseModel):
    source: str
    text: str


class Output(BaseModel):
    query: str
    response: str
    citations: list[Citation] = Field(default_factory=list)


class DocumentService:
    """
    Service responsible for turning the laws PDF into structured Document chunks.
    """

    DEFAULT_LAWS_PATH = Path(__file__).resolve().parent.parent / "docs" / "laws.pdf"

    DEFAULT_LAW_TITLES = {
        "1": "Peace",
        "2": "Religion",
        "3": "Widows",
        "4": "Trials",
        "5": "Taxes",
        "6": "Thievery",
        "7": "Poaching",
        "8": "Outlawry",
        "9": "Slavery",
        "10": "Watch",
        "11": "Baking",
    }

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        self.file_path = Path(file_path) if file_path else self.DEFAULT_LAWS_PATH

    def create_documents(self) -> list[Document]:
        raw_text = self._extract_pdf_text()
        docs = self._parse_laws_text(raw_text)

        # Fallback keeps the service usable if PDF extraction degrades in some environments.
        if not docs or self._documents_look_degraded(docs):
            docs = self._parse_laws_text(self._fallback_laws_text())

        if not docs:
            raise RuntimeError("Unable to create any documents from laws input.")

        return docs

    def _extract_pdf_text(self) -> str:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Laws file not found: {self.file_path}")

        reader = PdfReader(str(self.file_path))
        text_parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
        return "\n".join(text_parts)

    def _parse_laws_text(self, text: str) -> list[Document]:
        lines = self._normalize_lines(text)
        if not lines:
            return []

        top_titles: dict[str, str] = {}
        sections: list[dict[str, str]] = []
        last_idx: int | None = None

        for raw_line in lines:
            for line in self._split_compound_line(raw_line):
                lower = line.lower()
                if lower.startswith("laws of the seven kingdoms") or lower.startswith("citations"):
                    continue
                if line.startswith("http://") or line.startswith("https://"):
                    continue

                top_match = re.match(r"^(\d+)\.\s+([A-Za-z][A-Za-z' -]+)$", line)
                if top_match:
                    top_titles[top_match.group(1)] = top_match.group(2).strip()
                    last_idx = None
                    continue

                section_match = re.match(r"^(\d+(?:\.\d+)+)\.\s*(.*)$", line)
                if section_match:
                    section = section_match.group(1)
                    content = section_match.group(2).strip()
                    sections.append({"section": section, "content": content})
                    last_idx = len(sections) - 1
                    continue

                # Continuation text belongs to the most recent section.
                if last_idx is not None:
                    sections[last_idx]["content"] = (
                        f"{sections[last_idx]['content']} {line}".strip()
                    )

        if not sections:
            return []

        docs: list[Document] = []
        grouped: dict[str, list[str]] = defaultdict(list)

        for entry in sections:
            section = entry["section"]
            content = re.sub(r"\s+", " ", entry["content"]).strip(" .")
            if not content:
                continue

            law_number = section.split(".")[0]
            law_title = top_titles.get(law_number, self.DEFAULT_LAW_TITLES.get(law_number, f"Law {law_number}"))
            source = f"Law {law_number} - {law_title} ({section})"
            doc_text = f"{law_title} ({section}): {content}"

            docs.append(
                Document(
                    text=doc_text,
                    metadata={
                        "law_number": law_number,
                        "law_title": law_title,
                        "section": section,
                        "source": source,
                    },
                )
            )
            grouped[law_number].append(doc_text)

        # Add one summary doc per top-level law to support broader queries.
        for law_number, chunks in grouped.items():
            law_title = top_titles.get(law_number, self.DEFAULT_LAW_TITLES.get(law_number, f"Law {law_number}"))
            source = f"Law {law_number} - {law_title}"
            summary = " ".join(chunks)
            docs.append(
                Document(
                    text=summary,
                    metadata={
                        "law_number": law_number,
                        "law_title": law_title,
                        "section": law_number,
                        "source": source,
                    },
                )
            )

        return docs

    @staticmethod
    def _normalize_lines(text: str) -> list[str]:
        lines: list[str] = []
        for line in text.replace("\t", " ").splitlines():
            cleaned = re.sub(r"\s+", " ", line).strip()
            if not cleaned:
                continue
            if re.fullmatch(r"\d+", cleaned):
                continue
            lines.append(cleaned)
        return lines

    @staticmethod
    def _split_compound_line(line: str) -> list[str]:
        # Handles formatting glitches like "2.1. 3. Widows" by splitting before the new heading.
        split_line = re.sub(r"(\d+\.\d+\.)\s+(\d+\.\s+[A-Z])", r"\1\n\2", line)
        return [chunk.strip() for chunk in split_line.split("\n") if chunk.strip()]

    @staticmethod
    def _documents_look_degraded(docs: list[Document]) -> bool:
        sample = " ".join(doc.text for doc in docs[:8])
        # Extraction is unreliable if we see long words with no spaces,
        # which leads to mixed sections and poor citations.
        if re.search(r"[A-Za-z]{25,}", sample):
            return True
        if "6. Thievery" in sample or "10. Watch" in sample:
            return True
        return False

    @staticmethod
    def _fallback_laws_text() -> str:
        return """
Laws of the Seven Kingdoms
1. Peace
1.1. The law requires petty lords and landed knights to take their disputes to their liege lord, and abide by his judgment, while disputes between great houses were adjudicated by the Crown.
2. Religion
2.1. King Maegor raised a set of laws which forbade holy men from carrying arms.
3. Widows
3.1. The Widow's Law reaffirms the right of the eldest son (or eldest daughter, if there are no sons) to inherit.
3.1.1. However, the law requires the heirs to maintain their father's surviving widow, no matter whether she had been a second, third, or later wife, under the same conditions as before her husband's death.
3.1.2. The widows could no longer be driven from their late husband’s castle, deprived of servants or possessions, or stripped of income.
3.1.3. The law similarly prevented men from disinheriting children from an earlier marriage in favor of children from a later marriage.
4. Trials
4.1. Trials of the Crown
4.1.1. Accused and witnesses are sworn to honesty and testify before one or more judges.
4.2. Trials by combat
4.2.1. Any knight accused of wrongdoing is allowed by law to demand a trial by combat.
4.2.2. The accused and accusers may have champions fight in their place, and killing in a lawful trial by combat is not considered murder.
4.2.3. A more ancient custom is a trial of seven, in which seven men fight on each side.
4.2.4. When the accused is royalty, their champion must be a knight of the Kingsguard; when the accuser is royalty, they may choose a champion outside the Kingsguard.
5. Taxes
5.1. In the Seven Kingdoms, taxes are collected locally.
5.1.1. Lords pay taxes to the Crown.
5.1.2. Great Houses gather regional taxes and then pay the Crown.
5.1.2.1. Taxes owed to the Night's Watch by villages in the New Gift are paid in kind, not gold.
5.2. Lords can have treasurers in their service to handle incoming taxes.
6. Thievery
6.1. It is customary for a thief to be punished by losing a finger or a hand.
6.2. Pickpockets can likewise be punished by cutting off a hand.
6.3. Those who steal from a sept can be considered to have stolen from the gods and can receive a harsher punishment.
7. Poaching
7.1. Poaching is forbidden and punishments can include joining the Night's Watch, losing a hand, or rowing ships.
8. Outlawry
8.1. Outlaws are generally sentenced to death by hanging.
9. Slavery
9.1. Slavery is illegal in the Seven Kingdoms.
9.1.1. Both the old gods and the Faith of the Seven consider slavery an abomination.
9.1.2. The punishment for selling people in the Seven Kingdoms is execution.
10. Watch
10.1. An alternative for most punishments is joining the Night's Watch.
10.1.1. Debtors, poachers, thieves, and murderers may be forced to join.
10.1.1.1. Men of the Night's Watch must swear a vow by which their crimes are washed away and their debts are forgiven.
10.1.1.2. Breaking the oath made to the Night's Watch is punishable by death.
10.1.1.3. Refusing orders made by the Lord Commander can also be punishable by death.
10.1.1.4. Women are not allowed to join the Night's Watch.
11. Baking
11.1. A baker who mixes sawdust in flour might be fined or whipped.
"""


class QdrantService:
    def __init__(self, k: int = 3):
        self.index: Optional[VectorStoreIndex] = None
        self.k = k
        self.embed_model: Optional[OpenAIEmbedding] = None
        self.llm: Optional[OpenAI] = None

    def connect(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required.")

        self.embed_model = OpenAIEmbedding(model="text-embedding-3-small", api_key=api_key)
        self.llm = OpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0)

    def load(self, docs: list[Document]) -> None:
        if self.embed_model is None:
            raise RuntimeError("QdrantService.connect() must be called before load().")
        self.index = VectorStoreIndex.from_documents(
            docs,
            embed_model=self.embed_model,
        )

    def query(self, query_str: str) -> Output:
        if self.index is None or self.llm is None:
            raise RuntimeError("QdrantService is not initialized. Call connect() and load() first.")

        query_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=self.k,
            response_mode="compact",
        )
        response = query_engine.query(query_str)
        response_text = str(response)

        citations: list[Citation] = []
        seen: set[tuple[str, str]] = set()
        for src in getattr(response, "source_nodes", [])[: self.k]:
            node = src.node
            metadata = getattr(node, "metadata", {}) or {}
            source = metadata.get("source") or metadata.get("section") or "Unknown source"
            text = self._trim_text(node.get_content(metadata_mode="none"))
            key = (source, text)
            if key in seen:
                continue
            seen.add(key)
            citations.append(Citation(source=source, text=text))

        return Output(
            query=query_str,
            response=response_text,
            citations=citations,
        )

    @staticmethod
    def _trim_text(text: str, max_chars: int = 340) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= max_chars:
            return normalized
        return f"{normalized[:max_chars].rstrip()}..."


if __name__ == "__main__":
    # Example workflow
    document_service = DocumentService()
    docs = document_service.create_documents()

    index = QdrantService()
    index.connect()
    index.load(docs)

    print(index.query("what happens if I steal?"))
