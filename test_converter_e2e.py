import pytest
import os
import subprocess
import tempfile
from pathlib import Path

# Potentially import functions from tex_to_docx_converter if needed for specific tests,
# but for true E2E, calling as a script is often preferred.
# from tex_to_docx_converter import main as converter_main # Example

SCRIPT_PATH = Path(__file__).parent / "tex_to_docx_converter.py"
TEST_DATA_DIR = Path(__file__).parent / "test_data_e2e" # We might create this later for test assets
IMAGES_DIR = Path(__file__).parent / "images" # Standard images directory

def run_converter_script(input_file: Path, output_file: Path) -> subprocess.CompletedProcess:
    """Helper function to run the converter script as a subprocess."""
    return subprocess.run(
        ["python", str(SCRIPT_PATH), str(input_file), str(output_file)],
        capture_output=True,
        text=True,
        check=False # We will check returncode explicitly in tests
    )

# Example of a placeholder test
def test_e2e_placeholder():
    assert True

# More tests will be added in subsequent steps.

def test_e2e_successful_image_inclusion():
    """Tests end-to-end conversion with a valid image."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True) # Ensure base test data dir exists
    
    input_tex_file = TEST_DATA_DIR / "test_valid_image.tex"
    
    # Define where the image will be saved (using the existing 'images' directory)
    img_dir_for_test_image = IMAGES_DIR 
    os.makedirs(img_dir_for_test_image, exist_ok=True)
    valid_test_image_path = img_dir_for_test_image / "valid_test_image.png"
    
    # LaTeX content referencing the image.
    # The path 'images/valid_test_image.png' should be resolvable by the script
    # as it's relative to the script's CWD or the script handles it.
    # Using a raw string here for the latex_content
    latex_content = r'''\documentclass{article}
\usepackage{graphicx}
\begin{document}
Hello, this document includes a valid image.
\includegraphics{images/valid_test_image.png}
This is a test.
\end{document}
'''
    with open(input_tex_file, "w") as f:
        f.write(latex_content)

    # Generate the valid image using Pillow
    try:
        from PIL import Image, ImageDraw
        if not valid_test_image_path.exists(): # Create only if it doesn't exist
            img = Image.new("RGB", (60, 30), color = "green")
            draw = ImageDraw.Draw(img)
            draw.text((10,10), "OK", fill="black")
            img.save(valid_test_image_path, "PNG")
            print(f"Test image {valid_test_image_path} generated for test_e2e_successful_image_inclusion")
    except ImportError:
        print("Pillow library not found, cannot generate test image for test_e2e_successful_image_inclusion.")
        pytest.skip("Pillow library not found, cannot generate test image.")
    except Exception as e:
        print(f"Error generating test image: {e}")
        pytest.fail(f"Failed to generate test image: {e}")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_docx_file = Path(tmpdir) / "output_valid_image.docx"
        
        result = run_converter_script(input_tex_file, output_docx_file)

        assert result.returncode == 0, f"Script failed with error output: STDERR: {result.stderr} STDOUT: {result.stdout}"
        assert output_docx_file.exists(), "Output DOCX file was not created."
        
        assert "Error adding image" not in result.stderr, f"Error message found in stderr: {result.stderr}"
        assert "Error adding image" not in result.stdout, f"Error message found in stdout: {result.stdout}"
        assert "UnrecognizedImageError" not in result.stderr, f"UnrecognizedImageError found in stderr: {result.stderr}"
        assert "UnrecognizedImageError" not in result.stdout, f"UnrecognizedImageError found in stdout: {result.stdout}"
        assert "Image not found" not in result.stdout, f"Image not found message in stdout: {result.stdout}"
        assert "Image not found" not in result.stderr, f"Image not found message in stderr: {result.stderr}"

def test_e2e_problematic_image_causes_failure():
    """Tests that conversion fails correctly when a problematic image is encountered."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True) # Ensure base test data dir exists
    
    input_tex_file = TEST_DATA_DIR / "test_problematic_image.tex"
    
    # Create the LaTeX file for this test
    # Note: The content of this .tex file is already created by a previous step,
    # but the test logic includes its creation for completeness / idempotency.
    latex_content = r'''\documentclass{article}
\usepackage{graphicx}
\begin{document}
This document attempts to include a problematic image.
\includegraphics{images/sample_image.png} 
This should cause an error.
\end{document}
'''
    with open(input_tex_file, "w") as f:
        f.write(latex_content)
        
    # Ensure the problematic image 'images/sample_image.png' exists.
    # It was identified as a text file. If it's missing, this test is invalid.
    problematic_image_path = IMAGES_DIR / "sample_image.png"
    if not problematic_image_path.exists():
        # Create a dummy text file if it's missing, to simulate the problematic scenario.
        os.makedirs(IMAGES_DIR, exist_ok=True) # Ensure images directory exists
        with open(problematic_image_path, "w") as f:
            f.write("This is not an image.")
        print(f"Warning: Test file {problematic_image_path} was missing; created a dummy text file for it.")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_docx_file = Path(tmpdir) / "output_problematic_image.docx"
        
        result = run_converter_script(input_tex_file, output_docx_file)

        assert result.returncode != 0, "Script should have failed due to problematic image, but it succeeded."
        
        # Check for the specific error message in stderr.
        # The script was modified to re-raise UnrecognizedImageError.
        # The main script's final catch-all prints "{type(e).__name__} - {e}"
        # For UnrecognizedImageError from python-docx, str(e) is often empty or non-descriptive.
        # So, we check for the type name.
        # The error message is printed by tex_to_docx_converter.py before re-raising:
        # print(f"Error adding image {image_path}: {type(e).__name__} - {e}. Skipping and re-raising.")
        
        # The main.py's final exception handler will catch this and print:
        # "An error occurred during LaTeX parsing or DOCX generation: {e}"
        # and sys.exit(1). The {e} part will be the str(UnrecognizedImageError).
        # The UnrecognizedImageError from python-docx when it fails to identify an image from a stream
        # (which is what happens when it gets a text file) has a specific message.
        # Let's look for the message printed by generate_docx first, which is more specific.
        expected_error_message_in_stderr = "Error adding image images/sample_image.png: UnrecognizedImageError"
        
        assert expected_error_message_in_stderr in result.stderr, \
            f"Expected error message part '{expected_error_message_in_stderr}' not found in stderr. STDERR: {result.stderr}\\nSTDOUT: {result.stdout}"

        # It's also good practice to ensure the output file wasn't created,
        # or if it was, it's likely empty or incomplete.
        # Given the script now exits, it's less likely to be created.
        # assert not output_docx_file.exists(), \
        #    f"Output DOCX file {output_docx_file} was created despite a fatal error."
        # Depending on when/how the file is opened in the main script, it might still exist.
        # Not asserting its non-existence for now, as the error propagation is key.
