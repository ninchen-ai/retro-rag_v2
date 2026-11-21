"""Erste CLI für eine lokale Markdown-Importvorschau."""

import argparse
from pathlib import Path

from retro_rag.importer.markdown import read_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Retro-RAG-V2 Markdown-Importvorschau")
    parser.add_argument("file", type=Path, help="Lokale Markdown-Quelldatei")
    parser.add_argument("--source-id", required=True, help="Stabile externe Quellkennung")
    parser.add_argument("--max-chars", type=int, default=4000)
    parser.add_argument("--out", type=Path, help="Ausgabepfad für Importvertrag (JSON)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="JSON-Vorschau auf Datenträger schreiben; keine DB-Übernahme",
    )
    args = parser.parse_args()
    result = read_markdown(args.file, args.source_id, args.max_chars)
    data = result.model_dump_json(indent=2)
    if args.apply:
        if args.out is None:
            parser.error("--apply erfordert --out")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data + "\n", encoding="utf-8")
        print(f"Importvertrag erzeugt: {args.out}")
    else:
        print(data)


if __name__ == "__main__":
    main()
