"""
Gestione del database SQLite per l'indicizzazione dei documenti convertiti.

Implementa lo schema completo con tabella documents, indice FTS5 per
la ricerca full-text e trigger per il mantenimento della sincronizzazione.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

from tools.pdf_converter.config import TOOL_VERSION, paths as default_paths
from tools.pdf_converter.models import ConversionResult


# ---------------------------------------------------------------------------
# DDL — Schema del database
# ---------------------------------------------------------------------------

_DDL_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Identificazione
    filename                 TEXT NOT NULL,
    slug                     TEXT NOT NULL UNIQUE,
    -- Path (relativi alla root del progetto)
    pdf_path                 TEXT NOT NULL,
    md_path                  TEXT,
    images_dir               TEXT,
    -- Metadati PDF
    title                    TEXT,
    author                   TEXT,
    subject                  TEXT,
    num_pages                INTEGER NOT NULL,
    num_images               INTEGER DEFAULT 0,
    file_size_bytes          INTEGER,
    file_hash                TEXT,
    -- Metadati di processing
    converted_at             TEXT NOT NULL,
    processing_time_seconds  REAL,
    md_size_bytes            INTEGER,
    tool_version             TEXT,
    -- Classificazione utente (compilabile in seguito)
    tags                     TEXT,
    category                 TEXT,
    notes                    TEXT,
    -- Stato
    status                   TEXT NOT NULL DEFAULT 'completed',
    error_message            TEXT
);
"""

_DDL_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    filename, title, author, tags, category, notes,
    content='documents',
    content_rowid='id'
);
"""

_DDL_TRIGGER_INSERT = """
CREATE TRIGGER IF NOT EXISTS documents_ai
AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, filename, title, author, tags, category, notes)
    VALUES (new.id, new.filename, new.title, new.author, new.tags, new.category, new.notes);
END;
"""

_DDL_TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS documents_ad
AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, title, author, tags, category, notes)
    VALUES ('delete', old.id, old.filename, old.title, old.author, old.tags, old.category, old.notes);
END;
"""

_DDL_TRIGGER_UPDATE = """
CREATE TRIGGER IF NOT EXISTS documents_au
AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, title, author, tags, category, notes)
    VALUES ('delete', old.id, old.filename, old.title, old.author, old.tags, old.category, old.notes);
    INSERT INTO documents_fts(rowid, filename, title, author, tags, category, notes)
    VALUES (new.id, new.filename, new.title, new.author, new.tags, new.category, new.notes);
END;
"""

_DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_documents_slug ON documents(slug);",
    "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);",
    "CREATE INDEX IF NOT EXISTS idx_documents_converted_at ON documents(converted_at);",
    "CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);",
]


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------


class DocumentIndexer:
    """
    Gestisce il database SQLite per l'indicizzazione dei documenti PDF convertiti.

    Ogni istanza rappresenta una connessione al database specificato.
    Il database viene creato automaticamente se non esiste.

    Esempio d'uso:
        indexer = DocumentIndexer()
        indexer.init_db()
        indexer.index_document(result)
        docs = indexer.list_documents()
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Inizializza l'indexer con il path al database SQLite.

        Args:
            db_path: Path al file .db. Usa il default da config se None.
        """
        self.db_path = db_path or default_paths.database
        # Assicura che la cartella data/ esista
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """
        Apre una connessione al database con row_factory configurata.

        Returns:
            Connessione sqlite3 con row_factory = sqlite3.Row
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Abilita WAL mode per migliori performance in lettura concorrente
        conn.execute("PRAGMA journal_mode=WAL;")
        # Abilita foreign keys
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_db(self) -> None:
        """
        Inizializza il database creando tabelle, indici FTS e trigger.

        Operazione idempotente: usa CREATE IF NOT EXISTS per tutti gli oggetti.
        Sicuro da chiamare ogni volta che il tool parte.

        Raises:
            sqlite3.Error: se la creazione del database fallisce
        """
        logger.info(f"Inizializzazione database: {self.db_path}")

        with self._connect() as conn:
            # Tabella principale
            conn.execute(_DDL_DOCUMENTS)

            # Indice full-text FTS5
            conn.execute(_DDL_FTS)

            # Trigger per sincronizzazione FTS
            conn.execute(_DDL_TRIGGER_INSERT)
            conn.execute(_DDL_TRIGGER_DELETE)
            conn.execute(_DDL_TRIGGER_UPDATE)

            # Indici sulle colonne piu' usate nelle query
            for ddl in _DDL_INDEXES:
                conn.execute(ddl)

            # Migrazione: aggiungi colonna file_hash se non esiste (per versioni precedenti)
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT;")
                logger.info("Migrazione: aggiunta colonna file_hash alla tabella documents")
            except sqlite3.OperationalError:
                # Colonna gia' esiste
                pass

            conn.commit()

        logger.success(f"Database pronto: {self.db_path}")

    def is_already_converted(self, slug: str, file_hash: str | None = None) -> bool:
        """
        Verifica se un documento e' gia' stato convertito con successo e non modificato.

        Controlla la presenza dello slug nel DB con status 'completed'.
        Se file_hash e' fornito, verifica anche che il hash corrisponda per rilevare modifiche.
        Documenti con status 'error' vengono considerati non convertiti.
        Record senza file_hash (legacy) vengono considerati come modificati.

        Args:
            slug: Slug normalizzato del documento da verificare
            file_hash: SHA256 hash del file attuale (se fornito, controlla modifiche)

        Returns:
            True se il documento e' gia' indicizzato con status 'completed' e hash invariato
        """
        with self._connect() as conn:
            if file_hash:
                # Controlla status e hash
                row = conn.execute(
                    "SELECT id FROM documents WHERE slug = ? AND status = 'completed' AND file_hash = ?",
                    (slug, file_hash),
                ).fetchone()
            else:
                # Fallback: solo status (per compatibilita')
                row = conn.execute(
                    "SELECT id FROM documents WHERE slug = ? AND status = 'completed'",
                    (slug,),
                ).fetchone()
        return row is not None

    def index_document(self, result: ConversionResult) -> int:
        """
        Inserisce o aggiorna il record di un documento nel database.

        Se il documento (identificato dallo slug) e' gia' presente,
        lo aggiorna con i nuovi dati (utile con --force).
        Se e' nuovo, lo inserisce.

        Args:
            result: ConversionResult completo della conversione

        Returns:
            ID del record inserito o aggiornato

        Raises:
            sqlite3.Error: se l'operazione sul database fallisce
        """
        data = result.to_db_dict(tool_version=TOOL_VERSION)

        with self._connect() as conn:
            # Verifica se esiste gia' un record con questo slug
            existing = conn.execute(
                "SELECT id FROM documents WHERE slug = ?",
                (data["slug"],),
            ).fetchone()

            if existing:
                # Aggiornamento: rimuovi id dai dati (non va aggiornato)
                record_id = existing["id"]
                update_fields = {k: v for k, v in data.items() if k != "slug"}
                set_clause = ", ".join(f"{k} = :{k}" for k in update_fields)
                update_fields["slug"] = data["slug"]
                conn.execute(
                    f"UPDATE documents SET {set_clause} WHERE slug = :slug",
                    update_fields,
                )
                logger.debug(f"Record aggiornato nel DB: {data['filename']} (id={record_id})")
            else:
                # Inserimento nuovo record
                columns = ", ".join(data.keys())
                placeholders = ", ".join(f":{k}" for k in data.keys())
                cursor = conn.execute(
                    f"INSERT INTO documents ({columns}) VALUES ({placeholders})",
                    data,
                )
                record_id = cursor.lastrowid
                logger.debug(f"Record inserito nel DB: {data['filename']} (id={record_id})")

            conn.commit()

        return record_id

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Esegue una ricerca full-text sui documenti indicizzati.

        Usa l'indice FTS5 per cercare nei campi filename, title, author,
        tags, category e notes. La query supporta la sintassi FTS5:
        AND, OR, NOT, prefisso con *, frasi con "".

        Args:
            query: Stringa di ricerca (es. "vendite AND Q1", "report*")
            limit: Numero massimo di risultati da ritornare

        Returns:
            Lista di dizionari con i campi del documento
        """
        sql = """
            SELECT d.*
            FROM documents d
            WHERE d.id IN (
                SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?
            )
            ORDER BY d.converted_at DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (query, limit)).fetchall()

        return [dict(row) for row in rows]

    def list_documents(
        self,
        sort_by: str = "converted_at",
        ascending: bool = False,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Ritorna la lista dei documenti indicizzati con ordinamento e filtri.

        Args:
            sort_by: Campo per l'ordinamento ('converted_at', 'filename', 'num_pages')
            ascending: True per ordinamento crescente, False per decrescente
            limit: Numero massimo di documenti da ritornare
            status_filter: Filtra per status ('completed', 'error', None per tutti)

        Returns:
            Lista di dizionari con i campi del documento
        """
        # Whitelist dei campi ordinabili per sicurezza (evita SQL injection)
        allowed_sort_fields = {"converted_at", "filename", "num_pages", "file_size_bytes", "title"}
        if sort_by not in allowed_sort_fields:
            sort_by = "converted_at"

        direction = "ASC" if ascending else "DESC"

        where_clause = ""
        params: list[Any] = []
        if status_filter:
            where_clause = "WHERE status = ?"
            params.append(status_filter)

        params.append(limit)

        sql = f"""
            SELECT * FROM documents
            {where_clause}
            ORDER BY {sort_by} {direction}
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """
        Ritorna statistiche aggregate sui documenti indicizzati.

        Returns:
            Dizionario con:
            - total_documents: numero totale di documenti
            - completed: documenti convertiti con successo
            - errors: documenti con errori
            - total_pages: somma totale delle pagine
            - total_images: somma totale delle immagini estratte
            - avg_processing_time: tempo medio di elaborazione in secondi
            - total_size_mb: dimensione totale PDF in MB
        """
        sql = """
            SELECT
                COUNT(*) as total_documents,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                COALESCE(SUM(num_pages), 0) as total_pages,
                COALESCE(SUM(num_images), 0) as total_images,
                COALESCE(AVG(CASE WHEN status = 'completed' THEN processing_time_seconds END), 0.0) as avg_processing_time,
                COALESCE(SUM(file_size_bytes), 0) / 1048576.0 as total_size_mb
            FROM documents
        """
        with self._connect() as conn:
            row = conn.execute(sql).fetchone()

        return dict(row) if row else {}
