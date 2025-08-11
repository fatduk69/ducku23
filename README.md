# OCR Agent

A command-line tool that detects scanned PDFs and applies Optical Character Recognition (OCR) using free tools.

## Installation

The script requires Python 3.10+ and the following system tools: [Tesseract](https://tesseract-ocr.github.io/), [OCRmyPDF](https://ocrmypdf.readthedocs.io/), and [Ghostscript](https://www.ghostscript.com/).

### Ubuntu / Debian
```bash
sudo apt-get install tesseract-ocr ocrmypdf ghostscript
pip install PyPDF2 watchdog
```

### macOS (Homebrew)
```bash
brew install tesseract ocrmypdf ghostscript
pip install PyPDF2 watchdog
```

### Windows
1. Install Tesseract, OCRmyPDF, and Ghostscript from their official installers.
2. Ensure all binaries are on your `PATH`.
3. Install Python dependencies:
```bash
pip install PyPDF2 watchdog
```

## Usage

Process a single PDF and create a searchable output:
```bash
python ocr_agent.py input.pdf -o output.pdf -l fra
```

Process a directory recursively using multiple languages and jobs:
```bash
python ocr_agent.py in_dir -O out_dir -l fra+eng --jobs 4
```

Watch a directory and OCR new PDFs as they appear:
```bash
python ocr_agent.py in_dir -O out_dir -l eng --watch
```

## FAQ

### ocrmypdf or tesseract not found
Make sure the tools are installed and available on the `PATH`. The script will emit an `[ERROR]` message and exit with a non-zero code when a dependency is missing.

### PDF already has text but was reprocessed
By default, PDFs that already contain text are skipped. Use `--force` to process them anyway.

### Why is only a `.txt` file produced?
If `ocrmypdf` is unavailable, the script falls back to `tesseract` and produces a `.txt` file instead of a PDF.

## License

MIT
