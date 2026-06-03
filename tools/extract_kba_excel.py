#!/usr/bin/env python3
"""
Script per estrarre e strutturare dati KBA da file Excel e produrre output Markdown.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

# Configurazione logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configurazione percorsi
EXCEL_FILE = Path("Inbox/merged_enriched_260505.xlsx")
OUTPUT_FILE = Path("Team/Handoff/2026-05-05_estrazione-kba-excel.md")


def load_excel_data(file_path: Path) -> pd.DataFrame:
    """
    Carica i dati dal file Excel.

    Args:
        file_path (Path): Percorso del file Excel.

    Returns:
        pd.DataFrame: DataFrame con i dati caricati.
    """
    try:
        logger.info(f"Caricamento dati da {file_path}")
        df = pd.read_excel(file_path, engine="openpyxl")
        logger.info(f"Caricati {len(df)} record")
        return df
    except Exception as e:
        logger.error(f"Errore nel caricamento del file Excel: {e}")
        raise


def extract_kba_data(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Estrae i dati KBA dal DataFrame.

    Assumiamo colonne: 'ID', 'Descrizione', 'Azioni Patching/Installazione', 'Ubicazioni Applicative'
    Adatta se necessario in base ai dati reali.

    Args:
        df (pd.DataFrame): DataFrame di input.

    Returns:
        List[Dict[str, Any]]: Lista di dizionari con dati KBA.
    """
    # Colonne attese basate sulla struttura del file Excel
    expected_columns = [
        "KBA Number",
        "Title",
        "Workaround",
        "Suggested Notes",
        "Site",
        "Node Name / Node Assignment",
    ]

    # Verifica colonne presenti
    missing_columns = [col for col in expected_columns if col not in df.columns]
    if missing_columns:
        logger.warning(f"Colonne mancanti: {missing_columns}")
        # Procedi con quelle disponibili

    kba_list = []
    for _, row in df.iterrows():
        # Combina Workaround e Suggested Notes per azioni
        azioni = row.get("Workaround", "") or row.get("Suggested Notes", "N/A")
        ubicazioni = f"{row.get('Site', '')} - {row.get('Node Name / Node Assignment', '')}".strip(
            " - "
        )

        kba = {
            "ID": row.get("KBA Number", "N/A"),
            "Descrizione": row.get("Title", "N/A"),
            "Azioni Patching/Installazione": azioni,
            "Ubicazioni Applicative": ubicazioni,
        }
        kba_list.append(kba)

    logger.info(f"Estratti {len(kba_list)} record KBA")
    return kba_list


def generate_markdown_table(kba_list: List[Dict[str, Any]]) -> str:
    """
    Genera una tabella Markdown dalla lista KBA.

    Args:
        kba_list (List[Dict[str, Any]]): Lista di dati KBA.

    Returns:
        str: Stringa Markdown con tabella.
    """
    if not kba_list:
        return "Nessun dato KBA trovato."

    # Header tabella
    header = "| ID | Descrizione | Azioni Patching/Installazione | Ubicazioni Applicative |\n"
    separator = "|----|-------------|--------------------------------|-------------------------|\n"

    # Righe
    rows = ""
    for kba in kba_list:
        row = f"| {kba['ID']} | {kba['Descrizione']} | {kba['Azioni Patching/Installazione']} | {kba['Ubicazioni Applicative']} |\n"
        rows += row

    return header + separator + rows


def save_markdown_output(content: str, file_path: Path):
    """
    Salva il contenuto Markdown nel file specificato.

    Args:
        content (str): Contenuto Markdown.
        file_path (Path): Percorso del file di output.
    """
    try:
        # Frontmatter per conformità vault
        frontmatter = """---
tags: [kba, extraction, excel]
date: 2026-05-05
---

# Estrazione KBA da Excel

"""
        full_content = frontmatter + content

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        logger.info(f"Output salvato in {file_path}")
    except Exception as e:
        logger.error(f"Errore nel salvataggio del file: {e}")
        raise


def main():
    """
    Funzione principale.
    """
    try:
        # Carica dati
        df = load_excel_data(EXCEL_FILE)

        # Estrai KBA
        kba_list = extract_kba_data(df)

        # Genera Markdown
        markdown_table = generate_markdown_table(kba_list)

        # Salva output
        save_markdown_output(markdown_table, OUTPUT_FILE)

        logger.info("Processo completato con successo")

    except Exception as e:
        logger.error(f"Errore durante l'esecuzione: {e}")
        raise


if __name__ == "__main__":
    main()
