import pytest # Keep pytest import
# Removed sys and os imports as sys.path manipulation is no longer needed
from tex_to_docx_converter import parse_latex_to_json

# Test functions for parse_latex_to_json (11 functions as defined before)

def test_parse_title():
    latex_input = "\\title{My Test Title}"
    expected_json = [{'type': 'title', 'content': 'My Test Title'}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_section():
    latex_input = "\\section{Section One}"
    expected_json = [{'type': 'heading1', 'content': 'Section One'}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_subsection():
    latex_input = "\\subsection{Subsection A}"
    expected_json = [{'type': 'heading2', 'content': 'Subsection A'}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_simple_paragraph():
    latex_input = "Just a plain paragraph."
    expected_json = [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'Just a plain paragraph.'}]}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_paragraph_with_bold():
    latex_input = "Some \\textbf{bold} text."
    expected_json = [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'Some '}, {'type': 'text', 'value': '**bold**'}, {'type': 'text', 'value': ' text.'}]}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_paragraph_with_italic():
    latex_input = "An \\textit{italic} word."
    expected_json = [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'An '}, {'type': 'text', 'value': '*italic*'}, {'type': 'text', 'value': ' word.'}]}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_itemize_list_simple():
    latex_input = "\\begin{itemize}\\item First item\\item Second item\\end{itemize}"
    expected_json = [
        {'type': 'list_item_bullet', 'content': [{'type': 'text', 'value': 'First item'}]},
        {'type': 'list_item_bullet', 'content': [{'type': 'text', 'value': 'Second item'}]}
    ]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_image_no_options():
    latex_input = "\\includegraphics{images/my_pic.png}"
    expected_json = [{'type': 'image', 'path': 'images/my_pic.png', 'options': {}}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_image_with_width_option():
    latex_input = "\\includegraphics[width=10cm]{images/another_pic.jpeg}"
    expected_json = [{'type': 'image', 'path': 'images/another_pic.jpeg', 'options': {'width': '10cm'}}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_citet_with_prenote():
    latex_input = "A citation \\citet[see p.~15]{ref1} here."
    expected_json = [{'type': 'paragraph', 'content': [
        {'type': 'text', 'value': 'A citation '},
        {'type': 'citation', 'command': 'citet', 'keys': ['ref1'], 'prenote': 'see p.~15', 'postnote': ''},
        {'type': 'text', 'value': ' here.'}
    ]}]
    assert parse_latex_to_json(latex_input) == expected_json

def test_parse_citep_multiple_keys():
    latex_input = "Another one \\citep{ref2, ref3}."
    expected_json = [{'type': 'paragraph', 'content': [
        {'type': 'text', 'value': 'Another one '},
        {'type': 'citation', 'command': 'citep', 'keys': ['ref2', 'ref3'], 'prenote': '', 'postnote': ''},
        {'type': 'text', 'value': '.'}
    ]}]
    assert parse_latex_to_json(latex_input) == expected_json
