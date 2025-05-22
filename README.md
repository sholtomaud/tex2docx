# LaTeX to DOCX Converter with Zotero Citation Support

## Purpose

This Python script converts LaTeX (.tex) files into Microsoft Word (.docx) documents. Its key feature is the ability to translate LaTeX citation commands (such as `\citep`, `\citet`, `\citeauthor`, `\citeyearpar`) into Zotero-compatible field codes within the generated DOCX file. This allows users to continue managing their citations with Zotero in Word, with the Zotero plugin able to refresh and update bibliographies from these citations.

The script aims to support a simplified set of LaTeX styles and elements, including:
- Titles
- Headings (sections, subsections)
- Paragraphs
- Bold and Italic text
- Unordered (itemize) and Ordered (enumerate) lists
- Images (`\includegraphics`)

## Dependencies

The script requires the following Python libraries, listed in `requirements.txt`:
- `python-docx>=0.8.11` (for creating and manipulating DOCX files)
- `lxml>=4.5.0` (used by `python-docx` for XML processing)

You can install them using pip:
```bash
pip install -r requirements.txt
```

## How to Run

Execute the script from your command line:

```bash
python tex_to_docx_converter.py <input_file.tex> <output_file.docx>
```

Replace `<input_file.tex>` with the path to your source LaTeX file and `<output_file.docx>` with the desired path for the generated Word document.

**Example:**

```bash
python tex_to_docx_converter.py my_article.tex my_article_converted.docx
```

## Zotero Integration Example

If your LaTeX file contains a citation like:

```latex
This is supported by recent findings \citep[see p.~42]{doe2023novelwidget}.
```

The script will convert this into a special field in the DOCX document. When opened in Microsoft Word with the Zotero plugin active, Zotero will recognize this field. You can then use Zotero's "Refresh" or "Update Citations" feature to correctly format the citation and include it in your bibliography, just as if you had inserted it using Zotero directly in Word.

The goal is to bridge the gap between LaTeX-based writing workflows and Zotero's powerful citation management within Word.

## Testing

The project includes a comprehensive testing setup to ensure reliability and correctness.

### Test Suites

Two main test suites are available:

*   **`test_parser.py`**: This suite contains unit tests that focus specifically on the LaTeX parsing logic located in `tex_to_docx_converter.py`. These tests verify the correct translation of various LaTeX commands and structures into the intermediate JSON format. The internal tests mentioned previously (run with `--run-internal-tests`) are a subset of these parser tests.
*   **`test_converter_e2e.py`**: This suite provides end-to-end tests for the full TeX to DOCX conversion process. These tests execute the `tex_to_docx_converter.py` script as a subprocess, simulating real-world usage. They cover scenarios like:
    *   Successful conversion of documents with valid images.
    *   Correct error handling and script termination when problematic or missing images are encountered.
    *   Verification of output DOCX files and error messages in the script's output.

### Running Tests

To run all tests (both unit and end-to-end), ensure you have `pytest` and all other dependencies from `requirements.txt` installed. You can typically install these using:
```bash
pip install -r requirements.txt
pip install pytest pytest-cov # If pytest and coverage tool are not in requirements
```

Then, execute `pytest` from the root directory of the project:
```bash
pytest
```
This will discover and run all tests in files named `test_*.py` or `*_test.py`.

### Improved Error Handling

The converter now incorporates stricter error handling, especially for image processing. If an image referenced in the LaTeX document cannot be processed (e.g., due to file corruption, an unsupported format, or the file not being a true image), the script will report the error and terminate. This prevents the generation of incomplete DOCX files with missing or improperly processed images and provides clearer feedback to the user.

## Known Issues

- **Single-Line List Environments:** The LaTeX parser currently does not correctly interpret `itemize` or `enumerate` list environments if the entire environment (including `\begin`, `\item`s, and `\end`) is written on a single line. List items should be on separate lines for correct parsing. This was identified by the internal test `test_parse_itemize_list_simple`.

---

*Further details on advanced usage and contributions will be added later.*
