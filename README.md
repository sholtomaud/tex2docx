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

The script requires the following Python libraries:
- `python-docx` (for creating and manipulating DOCX files)
- `lxml` (used by `python-docx` for XML processing)

You can install them using pip:
```bash
pip install python-docx lxml
```
*(A `requirements.txt` file will be added later for easier dependency management).*

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

---

*Further details on advanced usage, testing, and contributions
