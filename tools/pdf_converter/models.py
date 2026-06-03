"""
Modelli Pydantic per il tool pdf_converter.

Definisce le strutture dati per i metadati dei documenti e i risultati
di conversione, con validazione automatica dei campi.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """
    Metadati estratti da un file PDF tramite PyMuPDF.

    I campi title, author e subject possono essere vuoti se il PDF
    non contiene metadati incorporati.
    """

    filename: str = Field(description="Nome del file PDF originale, estensione inclusa")
    slug: str = Field(description="Slug normalizzato, usato per cartelle e DB")
    pdf_path: Path = Field(description="Path assoluto al file PDF di input")
    title: str = Field(default="", description="Titolo dai metadati PDF (puo' essere vuoto)")
    author: str = Field(default="", description="Autore dai metadati PDF (puo' essere vuoto)")
    subject: str = Field(default="", description="Soggetto dai metadati PDF (puo' essere vuoto)")
    num_pages: int = Field(ge=1, description="Numero di pagine del documento")
    file_size_bytes: int = Field(ge=0, description="Dimensione del file PDF in byte")
    file_hash: str = Field(
        default="", description="SHA256 hash del file PDF per rilevare modifiche"
    )


class ConversionResult(BaseModel):
    """
    Risultato completo di una singola operazione di conversione PDF -> Markdown.

    Contiene sia i metadati del documento sorgente che le informazioni
    sull'output prodotto (path, dimensione, immagini, tempi).
    """

    # Metadati del documento sorgente
    metadata: DocumentMetadata

    # Path del file Markdown generato (None se la conversione e' fallita)
    md_path: Path | None = Field(
        default=None, description="Path assoluto al file Markdown generato"
    )

    # Cartella immagini estratte (None se nessuna immagine o errore)
    images_dir: Path | None = Field(
        default=None, description="Path alla cartella immagini del documento"
    )

    # Numero di immagini estratte
    num_images: int = Field(default=0, ge=0, description="Numero di immagini estratte dal PDF")

    # Dimensione del file Markdown generato in byte
    md_size_bytes: int = Field(default=0, ge=0, description="Dimensione del file Markdown in byte")

    # Tempo di elaborazione in secondi
    processing_time_seconds: float = Field(
        default=0.0, ge=0.0, description="Tempo di elaborazione in secondi"
    )

    # Timestamp della conversione
    converted_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp ISO 8601 della conversione",
    )

    # Stato finale della conversione
    status: str = Field(
        default="completed",
        description="Stato: 'completed', 'error', 'skipped'",
    )

    # Messaggio di errore (valorizzato solo se status == 'error')
    error_message: str | None = Field(
        default=None,
        description="Messaggio di errore se status != 'completed'",
    )

    @property
    def success(self) -> bool:
        """Ritorna True se la conversione e' andata a buon fine."""
        return self.status == "completed"

    def to_db_dict(self, tool_version: str = "0.1.0") -> dict:
        """
        Serializza il risultato in un dizionario compatibile con lo schema SQLite.

        Il campo converted_at viene formattato come stringa ISO 8601.
        I path vengono convertiti in stringhe relative alla root del progetto.
        """
        from tools.pdf_converter.config import PROJECT_ROOT

        def _rel(p: Path | None) -> str | None:
            """Converte un path assoluto in relativo rispetto alla root."""
            if p is None:
                return None
            try:
                return str(p.relative_to(PROJECT_ROOT))
            except ValueError:
                return str(p)

        return {
            "filename": self.metadata.filename,
            "slug": self.metadata.slug,
            "pdf_path": _rel(self.metadata.pdf_path),
            "md_path": _rel(self.md_path),
            "images_dir": _rel(self.images_dir),
            "title": self.metadata.title or None,
            "author": self.metadata.author or None,
            "subject": self.metadata.subject or None,
            "num_pages": self.metadata.num_pages,
            "num_images": self.num_images,
            "file_size_bytes": self.metadata.file_size_bytes,
            "file_hash": self.metadata.file_hash or None,
            "converted_at": self.converted_at.isoformat(),
            "processing_time_seconds": self.processing_time_seconds,
            "md_size_bytes": self.md_size_bytes,
            "tool_version": tool_version,
            "status": self.status,
            "error_message": self.error_message,
        }
