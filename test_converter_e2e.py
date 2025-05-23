import subprocess
import os
import json
import pytest
from pathlib import Path

# Define the root of the project.
# Assumes test_converter_e2e.py is in a 'tests' or 'tests/e2e' subdirectory of the project root.
# If test_converter_e2e.py is at project_root/tests/test_converter_e2e.py, then .parent is project_root/tests, .parent.parent is project_root
# If test_converter_e2e.py is at project_root/test_converter_e2e.py, then .parent is project_root. Adjust accordingly.
# Given the typical project structure, parent.parent is more likely if tests are in tests/e2e/.
# If tests are directly in a `tests` dir, then parent should be enough.
# Let's assume a `tests` directory at the project root:
PROJECT_ROOT = Path(__file__).resolve().parent.parent

LATEX2JSON_SCRIPT = str(PROJECT_ROOT / "latex2json.py")
JSON2DOCX_SCRIPT = str(PROJECT_ROOT / "json2docx.py")
TEST_DATA_DIR = PROJECT_ROOT / "test_data_e2e"
SCHEMA_DIR = PROJECT_ROOT / "schema" # Schema directory
DOCUMENT_SCHEMA_FILE = SCHEMA_DIR / "document_schema.json"


# Autouse fixture to ensure the schema directory and file exist.
# This is more of a safeguard; the schema should be part of the repository.
@pytest.fixture(scope="session", autouse=True)
def ensure_schema_file_exists():
    """
    Ensures that the schema/document_schema.json file exists at the project root,
    creating a minimal dummy version if it's not found. This is crucial for E2E tests
    where scripts are run as subprocesses from the project root.
    """
    # PROJECT_ROOT is already defined above as Path(__file__).resolve().parent.parent
    # This assumes test_converter_e2e.py is in a subdirectory like 'tests/'
    # so that PROJECT_ROOT correctly points to the repository root.

    target_schema_dir = PROJECT_ROOT / "schema"
    target_schema_file = target_schema_dir / "document_schema.json"

    if not target_schema_file.exists():
        print(f"Schema file {target_schema_file} not found. Creating a dummy one for e2e tests.")
        target_schema_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a minimal valid JSON schema, sufficient for the scripts to load
        dummy_schema_content = {
            "type": "object",
            "properties": {
                "properties": {"type": "object"},
                "template_path": {"type": "string"}, # Used by json2docx
                "page_layout": {"type": "object"},   # Used by json2docx
                "content": {
                    "type": "array",
                    "items": {"type": "object"} # General placeholder for content items
                }
            },
            "required": ["properties", "content"] # Minimal requirement
        }
        with open(target_schema_file, "w") as f:
            json.dump(dummy_schema_content, f, indent=4)
        
        # The scripts latex2json.py and json2docx.py also look for "document_schema.json"
        # directly in the CWD as a fallback if "schema/document_schema.json" is not found.
        # For robustness in E2E tests where CWD is PROJECT_ROOT, ensuring 
        # PROJECT_ROOT/schema/document_schema.json is the primary goal.
        # latex2json.py has logic to copy schema/document_schema.json to CWD if the former exists
        # and the CWD version doesn't. This fixture makes that logic succeed if schema was missing.
        
        # Also, ensure a schema file directly in PROJECT_ROOT if scripts expect that as a fallback,
        # though the primary path is schema/document_schema.json
        # For now, only creating PROJECT_ROOT/schema/document_schema.json as per instructions.
        # root_schema_file = PROJECT_ROOT / "document_schema.json"
        # if not root_schema_file.exists():
        #    with open(root_schema_file, "w") as f:
        #        json.dump(dummy_schema_content, f, indent=4)

    else:
        print(f"Found schema file at {target_schema_file}.")

@pytest.fixture(scope="session", autouse=True)
def ensure_test_data_exists_and_is_writable(tmp_path_factory):
    """
    Fixture to ensure that the test_data_e2e directory and its files are present.
    Also ensures that the scripts can write to the test_data_e2e directory if needed (e.g. for image path resolution).
    However, scripts should primarily write to tmp_path for outputs.
    """
    if not TEST_DATA_DIR.exists():
        TEST_DATA_DIR.mkdir(parents=True, exist_ok=True) # Create if doesn't exist

    # Create dummy files if they don't exist (idempotent)
    files_to_create = {
        "simple.tex": """\\documentclass{article}
\\title{Simple Document}
\\author{Test Author}
\\date{\\today}
\\begin{document}
\\maketitle
\\section{Introduction}
This is a simple paragraph with some \\textbf{bold text} and \\textit{italic text}.
\\end{document}""",
        "complex.tex": """\\documentclass{article}
\\usepackage{graphicx}
\\title{Complex Document}
\\author{Another Test Author}
\\date{\\today}
\\begin{document}
\\maketitle
\\section{First Section}
This is a paragraph in the first section.
\\subsection{Subsection 1.1}
This subsection contains a list.
\\begin{itemize}
    \\item Item A
    \\item Item B
    \\item Item C
\\end{itemize}
\\subsection{Subsection 1.2}
This subsection has a numbered list.
\\begin{enumerate}
    \\item Numbered One
    \\item Numbered Two
\\end{enumerate}
\\section{Second Section}
This section includes an image and a table.
\\begin{figure}[h!]
    \\centering
    \\includegraphics[width=0.5\\textwidth]{test_image.png}
    \\caption{This is a test image.}
    \\label{fig:test}
\\end{figure}
Here is a simple table:
\\begin{table}[h!]
    \\centering
    \\begin{tabular}{|l|r|}
        \\hline
        Left Column & Right Column \\\\
        \\hline
        Cell 1L & Cell 1R \\\\
        Cell 2L & Cell 2R \\\\
        \\hline
    \\end{tabular}
    \\caption{A simple test table.}
    \\label{tab:test}
\\end{table}
This is a citation test \\citep{test_key}.
\\end{document}""",
        "missing_image.tex": """\\documentclass{article}
\\usepackage{graphicx}
\\title{Document with Missing Image}
\\author{Error Tester}
\\date{\\today}
\\begin{document}
\\maketitle
\\section{Image Test}
This section attempts to include an image that does not exist.
\\begin{figure}[h!]
    \\centering
    \\includegraphics[width=0.5\\textwidth]{nonexistent_image.png}
    \\caption{A missing image.}
    \\label{fig:missing}
\\end{figure}
Another paragraph after the figure attempt.
\\end{document}""",
        "test_image.png": b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\x00\x00\x00\x00IEND\xaeB`\x82' # Minimal PNG
    }

    for filename, content in files_to_create.items():
        file_path = TEST_DATA_DIR / filename
        if not file_path.exists():
            if isinstance(content, str):
                file_path.write_text(content)
            else: # bytes for image
                file_path.write_bytes(content)
    
    assert (TEST_DATA_DIR / "test_image.png").exists()


def run_script(command_parts, script_name):
    """Helper to run a script and capture its output, asserting success."""
    process = subprocess.run(command_parts, capture_output=True, text=True, check=False, cwd=PROJECT_ROOT)
    
    if process.returncode != 0:
        print(f"{script_name} stdout:")
        print(process.stdout)
        print(f"{script_name} stderr:")
        print(process.stderr)
    
    assert process.returncode == 0, f"{script_name} failed with stderr: {process.stderr}"
    return process


def test_e2e_simple_conversion(tmp_path):
    """Test end-to-end conversion for a simple LaTeX file."""
    tex_file = TEST_DATA_DIR / "simple.tex"
    json_output_file = tmp_path / "simple.json"
    docx_output_file = tmp_path / "simple.docx"

    # Run latex2json.py
    run_script(
        ["python", LATEX2JSON_SCRIPT, str(tex_file), "--output", str(json_output_file)],
        "latex2json.py (simple)"
    )
    assert json_output_file.exists(), "JSON output file was not created."
    assert json_output_file.stat().st_size > 0, "JSON output file is empty."

    # Run json2docx.py
    run_script(
        ["python", JSON2DOCX_SCRIPT, str(docx_output_file), "--config", str(json_output_file)],
        "json2docx.py (simple)"
    )
    assert docx_output_file.exists(), "DOCX output file was not created."
    assert docx_output_file.stat().st_size > 0, "DOCX output file is empty."


def test_e2e_complex_conversion(tmp_path):
    """Test end-to-end conversion for a complex LaTeX file."""
    tex_file = TEST_DATA_DIR / "complex.tex"
    json_output_file = tmp_path / "complex.json"
    docx_output_file = tmp_path / "complex.docx"

    # Ensure the image is available in the correct relative path for latex2json.py
    # The script resolves paths relative to the .tex file's location or graphicspath.
    # Here, complex.tex references 'test_image.png' directly, so it should be in TEST_DATA_DIR.
    assert (TEST_DATA_DIR / "test_image.png").exists()

    # Run latex2json.py
    # The script's CWD will be PROJECT_ROOT. It needs to find test_image.png relative to complex.tex
    # The LatexToJsonConverter class's _find_image_path needs to handle this.
    # It typically checks CWD, then graphicspath, then relative to tex_file.parent.
    # Since complex.tex is in TEST_DATA_DIR, and image is also there, it should be found.
    run_script(
        ["python", LATEX2JSON_SCRIPT, str(tex_file), "--output", str(json_output_file)],
        "latex2json.py (complex)"
    )
    assert json_output_file.exists(), "Complex JSON output file was not created."
    assert json_output_file.stat().st_size > 0, "Complex JSON output file is empty."

    # Run json2docx.py
    run_script(
        ["python", JSON2DOCX_SCRIPT, str(docx_output_file), "--config", str(json_output_file)],
        "json2docx.py (complex)"
    )
    assert docx_output_file.exists(), "Complex DOCX output file was not created."
    assert docx_output_file.stat().st_size > 0, "Complex DOCX output file is empty."


def test_e2e_missing_image_error(tmp_path):
    """Test handling of missing images in the pipeline."""
    tex_file = TEST_DATA_DIR / "missing_image.tex"
    json_output_file = tmp_path / "missing_image.json"
    docx_output_file = tmp_path / "missing_image.docx"

    # Run latex2json.py
    l2j_process = subprocess.run(
        ["python", LATEX2JSON_SCRIPT, str(tex_file), "--output", str(json_output_file)],
        capture_output=True, text=True, check=False, cwd=PROJECT_ROOT
    )
    
    if l2j_process.returncode != 0: # Should ideally be 0 if it only warns
        print("latex2json.py stdout (missing_image):")
        print(l2j_process.stdout)
        print("latex2json.py stderr (missing_image):")
        print(l2j_process.stderr)
    # The script is designed to warn and continue for missing images.
    assert l2j_process.returncode == 0, f"latex2json.py failed unexpectedly for missing_image.tex: {l2j_process.stderr}"
    assert "Warning: Image 'nonexistent_image.png' not found" in l2j_process.stderr, \
        f"Expected warning for missing image not found in stderr. Stderr: {l2j_process.stderr}"
    
    assert json_output_file.exists(), "JSON output file for missing image was not created."
    assert json_output_file.stat().st_size > 0, "JSON output file for missing image is empty."

    # Run json2docx.py
    j2d_process = subprocess.run(
        ["python", JSON2DOCX_SCRIPT, str(docx_output_file), "--config", str(json_output_file)],
        capture_output=True, text=True, check=False, cwd=PROJECT_ROOT
    )

    if j2d_process.returncode != 0:
        print("json2docx.py stdout (missing_image):")
        print(j2d_process.stdout)
        print("json2docx.py stderr (missing_image):")
        print(j2d_process.stderr)
    
    # json2docx.py should also complete, printing an error for the specific missing image and adding a placeholder.
    assert j2d_process.returncode == 0, f"json2docx.py failed for missing_image.json: {j2d_process.stderr}"
    # Check for the specific error message in stderr (as per json2docx.py's current behavior)
    assert "Error loading image" in j2d_process.stderr
    assert "nonexistent_image.png" in j2d_process.stderr
    assert "Placeholder added." in j2d_process.stderr

    assert docx_output_file.exists(), "DOCX output file for missing image was not created."
    assert docx_output_file.stat().st_size > 0, "DOCX output file for missing image is empty."

# Note: If malformed.tex was to be tested, a similar structure would be used:
# def test_e2e_malformed_latex(tmp_path):
#     tex_file = TEST_DATA_DIR / "malformed.tex" # Assuming malformed.tex is created by ensure_test_data_exists
#     json_output_file = tmp_path / "malformed.json"
#
#     l2j_process = subprocess.run(
#         ["python", LATEX2JSON_SCRIPT, str(tex_file), "--output", str(json_output_file)],
#         capture_output=True, text=True, check=False, cwd=PROJECT_ROOT
#     )
#     # Example: Assert that the script fails or specific error is in stderr
#     assert l2j_process.returncode != 0, "latex2json.py should have failed for malformed.tex"
#     assert "Error: Malformed LaTeX detected" in l2j_process.stderr # Adjust based on actual error message
#     assert not json_output_file.exists() # Or it might create an empty/error JSON
#
#     # No json2docx run if latex2json fails critically
#     pass
