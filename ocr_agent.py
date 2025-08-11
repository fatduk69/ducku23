#!/usr/bin/env python3
"""OCR Agent CLI.

This script detects whether PDF files contain searchable text and, if not,
performs OCR using ``ocrmypdf`` or, as a fallback, ``tesseract``. It can
process single files, directories (recursively), or watch a directory for new
PDF files.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from PyPDF2 import PdfReader
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

LOGGER = logging.getLogger("ocr_agent")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


class MissingDependencyError(RuntimeError):
    """Raised when a required external tool is missing."""


def ensure_tools(tools: Iterable[str]) -> None:
    """Ensure that all required tools exist on the system path.

    Parameters
    ----------
    tools:
        Iterable of tool names to check with :func:`shutil.which`.

    Raises
    ------
    MissingDependencyError
        If any tool is missing.
    """

    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        for tool in missing:
            LOGGER.error("Missing required tool: %s", tool)
        raise MissingDependencyError(
            f"Missing required tool(s): {', '.join(missing)}"
        )


def pdf_has_text(path: Path, max_pages: int = 5, char_threshold: int = 20) -> bool:
    """Return True if the PDF appears to contain text.

    Only the first ``max_pages`` pages are scanned to speed up the operation.
    If the accumulated text length across scanned pages exceeds ``char_threshold``
    the PDF is considered to contain text.
    """

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pragma: no cover - corrupt PDF
        LOGGER.error("Failed to read PDF '%s': %s", path, exc)
        return False

    text = ""
    for page in reader.pages[:max_pages]:
        try:
            text += page.extract_text() or ""
        except Exception:  # pragma: no cover - PyPDF2 edge cases
            continue
        if len(text) >= char_threshold:
            return True
    return len(text) >= char_threshold


def ocr_with_ocrmypdf(
    inp: Path,
    out: Path,
    lang: str,
    jobs: int,
    optimize: bool,
) -> bool:
    """Perform OCR using ocrmypdf."""

    cmd = [
        "ocrmypdf",
        "--language",
        lang,
        "--jobs",
        str(jobs),
        "--output-type",
        "pdf",
        str(inp),
        str(out),
    ]
    if optimize:
        cmd[1:1] = ["--optimize", "3"]

    LOGGER.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        LOGGER.error("ocrmypdf failed: %s", result.stderr.strip())
        return False
    return True


def fallback_txt_ocr(inp: Path, out_txt: Path, lang: str) -> bool:
    """Fallback OCR using tesseract to produce a text file."""

    tmp_base = out_txt.with_suffix("")
    cmd = ["tesseract", str(inp), str(tmp_base), "-l", lang]
    LOGGER.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        LOGGER.error("tesseract failed: %s", result.stderr.strip())
        return False
    generated = tmp_base.with_suffix(".txt")
    if generated != out_txt:
        generated.rename(out_txt)
    return True


def process_file(
    inp: Path,
    out: Optional[Path],
    lang: str,
    jobs: int,
    optimize: bool,
    force: bool = False,
) -> None:
    """Process a single PDF file."""

    if not force and pdf_has_text(inp):
        LOGGER.info("[SKIP] %s already contains text", inp)
        return

    ensure_tools(["tesseract"])  # always required

    if shutil.which("ocrmypdf"):
        ensure_tools(["ocrmypdf"])
        if out is None:
            out = inp.with_name(inp.stem + "_ocr.pdf")
        if not ocr_with_ocrmypdf(inp, out, lang, jobs, optimize):
            raise SystemExit(1)
    else:
        LOGGER.warning(
            "ocrmypdf not found; falling back to plain tesseract producing .txt"
        )
        ensure_tools(["gs"])  # tesseract uses gs for PDFs
        if out is None:
            out = inp.with_suffix(".txt")
        else:
            out = out.with_suffix(".txt")
        if not fallback_txt_ocr(inp, out, lang):
            raise SystemExit(1)


def process_dir(
    inp_dir: Path,
    out_dir: Path,
    lang: str,
    jobs: int,
    optimize: bool,
    force: bool,
) -> None:
    """Recursively process a directory of PDFs."""

    for pdf_path in inp_dir.rglob("*.pdf"):
        rel = pdf_path.relative_to(inp_dir)
        target = out_dir / rel
        if shutil.which("ocrmypdf"):
            target = target.with_suffix(".pdf")
        else:
            target = target.with_suffix(".txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        process_file(pdf_path, target, lang, jobs, optimize, force)


class WatchHandler(FileSystemEventHandler):
    """Handle new PDF files in a watched directory."""

    def __init__(
        self,
        in_root: Path,
        out_root: Path,
        lang: str,
        jobs: int,
        optimize: bool,
        force: bool,
    ) -> None:
        super().__init__()
        self.in_root = in_root
        self.out_root = out_root
        self.lang = lang
        self.jobs = jobs
        self.optimize = optimize
        self.force = force

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".pdf":
            return
        rel = path.relative_to(self.in_root)
        target = self.out_root / rel
        if shutil.which("ocrmypdf"):
            target = target.with_suffix(".pdf")
        else:
            target = target.with_suffix(".txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        process_file(path, target, self.lang, self.jobs, self.optimize, self.force)


def watch_dir(
    inp_dir: Path,
    out_dir: Path,
    lang: str,
    jobs: int,
    optimize: bool,
    force: bool,
) -> None:
    """Watch ``inp_dir`` for new PDFs and OCR them on arrival."""

    handler = WatchHandler(inp_dir, out_dir, lang, jobs, optimize, force)
    observer = Observer()
    observer.schedule(handler, str(inp_dir), recursive=True)
    observer.start()
    LOGGER.info("Watching %s for new PDF files", inp_dir)
    try:
        while True:
            observer.join(1)
    except KeyboardInterrupt:  # pragma: no cover - manual stop
        observer.stop()
    observer.join()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OCR scanned PDF files")
    parser.add_argument("input", type=Path, help="input PDF file or directory")
    parser.add_argument("-o", "--output", type=Path, help="output PDF path")
    parser.add_argument("-O", "--output-dir", type=Path, help="output directory")
    parser.add_argument(
        "-l", "--lang", default="eng", help="OCR languages, e.g. 'fra' or 'fra+eng'"
    )
    parser.add_argument("--jobs", type=int, default=1, help="parallel jobs for ocrmypdf")
    parser.add_argument("--optimize", action="store_true", help="enable optimization")
    parser.add_argument("--force", action="store_true", help="OCR even if text exists")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="watch a directory for new PDFs",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    inp = args.input
    if not inp.exists():
        LOGGER.error("Input path does not exist: %s", inp)
        return 1

    try:
        if inp.is_file():
            process_file(
                inp, args.output, args.lang, args.jobs, args.optimize, args.force
            )
            return 0

        out_dir = args.output_dir or args.output
        if out_dir is None:
            out_dir = inp
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.watch:
            watch_dir(inp, out_dir, args.lang, args.jobs, args.optimize, args.force)
        else:
            process_dir(
                inp, out_dir, args.lang, args.jobs, args.optimize, args.force
            )
        return 0
    except MissingDependencyError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
