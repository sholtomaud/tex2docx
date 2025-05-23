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

The script requires the following Python libraries, as listed in `requirements.txt`:
- `python-docx>=0.8.11`: For creating and manipulating DOCX files.
- `lxml>=4.5.0`: Used by `python-docx` for XML processing.
- `Pillow>=8.0.0`: Used for image handling, particularly for determining image dimensions.
- `jsonschema>=3.2.0`: Used for validating the structure of the intermediate JSON.

You can install all necessary dependencies using pip:
```bash
pip install -r requirements.txt
```

## How to Run

The conversion from LaTeX to DOCX is a two-step process:

1.  **Convert LaTeX to JSON:**
    Use the `latex2json.py` script to convert your LaTeX file into an intermediate JSON format.

    ```bash
    python latex2json.py <input_file.tex> --output <intermediate_json_file.json>
    ```
    *   `<input_file.tex>`: Path to your source LaTeX file.
    *   `<intermediate_json_file.json>`: Desired path for the generated JSON file.

    **Example:**
    ```bash
    python latex2json.py my_article.tex --output my_article.json
    ```

2.  **Convert JSON to DOCX:**
    Use the `json2docx.py` script to convert the intermediate JSON file into a DOCX document.

    ```bash
    python json2docx.py <output_file.docx> --config <intermediate_json_file.json>
    ```
    *   `<output_file.docx>`: Desired path for the final DOCX document.
    *   `<intermediate_json_file.json>`: Path to the JSON file generated in the previous step.

    **Example:**
    ```bash
    python json2docx.py my_article_converted.docx --config my_article.json
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

*   **`test_parser.py`**: This suite contains unit tests that focus specifically on the LaTeX parsing logic within the `LatexToJsonConverter` class (used by `latex2json.py`). These tests verify the correct translation of various LaTeX commands and structures into the intermediate JSON format.
*   **`test_converter_e2e.py`**: This suite provides end-to-end tests for the full LaTeX to DOCX conversion pipeline. These tests execute the `latex2json.py` and `json2docx.py` scripts as subprocesses, simulating real-world usage with sample LaTeX files located in the `test_data_e2e/` directory. They cover scenarios like:
    *   Successful conversion of simple and complex documents (including images, lists, tables).
    *   Correct error handling and warnings for missing images.
    *   Verification of output files and script behavior.

### Running Tests

To run all tests (both unit and end-to-end), ensure you have `pytest` and all other dependencies from `requirements.txt` installed. `pytest` is included in `requirements.txt`. You can install dependencies using:
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

The `latex2json.py` script incorporates error handling for issues like missing images, printing warnings but attempting to continue. The `json2docx.py` script will also attempt to handle missing image data gracefully by inserting placeholders. The end-to-end tests verify this behavior.

## Known Issues

- **Single-Line List Environments:** The LaTeX parser currently does not correctly interpret `itemize` or `enumerate` list environments if the entire environment (including `\begin`, `\item`s, and `\end`) is written on a single line. List items should be on separate lines for correct parsing. This was identified by the internal test `test_parse_itemize_list_simple`.

---

*Further details on advanced usage and contributions will be added later.*
