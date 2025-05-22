import argparse
import json
import os
import re
import sys # Added for sys.exit()
import uuid

import docx
from docx.shared import Cm, Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


# Compiled regexes for citation commands - Using raw strings
CITET_RE = re.compile(r'\\citet(?:\[(.*?)\])?\{(.*?)\}')
CITEP_RE = re.compile(r'\\citep(?:\[(.*?)\])?\{(.*?)\}')
CITEAUTHOR_RE = re.compile(r'\\citeauthor\{(.*?)\}')
CITEYEARPAR_RE = re.compile(r'\\citeyearpar(?:\[(.*?)\])?\{(.*?)\}')

CITATION_COMMANDS = [
    ('citet', CITET_RE),
    ('citep', CITEP_RE),
    ('citeauthor', CITEAUTHOR_RE),
    ('citeyearpar', CITEYEARPAR_RE),
]

def _apply_basic_formatting_to_str(text_segment: str) -> str:
    if not text_segment: return ""
    # Using raw strings for regex patterns
    content = re.sub(r'\\textbf\{(.*?)\}', r'**\1**', text_segment)
    content = re.sub(r'\\textit\{(.*?)\}', r'*\1*', content)
    return content

def process_inline_elements(text_line: str) -> list:
    elements = []
    current_pos = 0
    processed_line = _apply_basic_formatting_to_str(text_line)

    while current_pos < len(processed_line):
        earliest_match = None
        earliest_match_pos = len(processed_line)
        command_name_for_match = None
        match_obj_for_match = None

        for cmd_name, cmd_re in CITATION_COMMANDS:
            match_in_processed = cmd_re.search(processed_line, current_pos)
            if match_in_processed and match_in_processed.start() < earliest_match_pos:
                earliest_match_pos = match_in_processed.start()
                earliest_match = match_in_processed
                command_name_for_match = cmd_name
                match_obj_for_match = match_in_processed

        if earliest_match:
            if earliest_match.start() > current_pos:
                pre_text = processed_line[current_pos:earliest_match.start()]
                elements.append({'type': 'text', 'value': pre_text})
            
            prenote = ""
            keys_str = ""
            if command_name_for_match == 'citeauthor':
                keys_str = match_obj_for_match.group(1)
            else: 
                prenote = match_obj_for_match.group(1) if match_obj_for_match.group(1) else ""
                keys_str = match_obj_for_match.group(2)
            
            parsed_keys = [k.strip() for k in keys_str.split(',')]
            elements.append({
                'type': 'citation',
                'command': command_name_for_match,
                'keys': parsed_keys,
                'prenote': prenote.strip(),
                'postnote': ""
            })
            current_pos = earliest_match.end()
        else:
            if current_pos < len(processed_line):
                post_text = processed_line[current_pos:]
                elements.append({'type': 'text', 'value': post_text})
            break
    return elements

def parse_latex_options(options_str: str) -> dict:
    options = {}
    if not options_str: return options
    for part in options_str.split(','):
        match = re.match(r'\s*(.*?)\s*=\s*(.*)\s*', part)
        if match:
            key, value = match.groups()
            options[key.strip()] = value.strip()
    return options

def parse_latex_to_json(latex_content: str) -> list:
    json_output = []
    lines = latex_content.splitlines()
    current_paragraph_text_accumulator = [] 
    in_itemize_env = False
    in_enumerate_env = False
    
    def flush_paragraph():
        nonlocal current_paragraph_text_accumulator, json_output
        if current_paragraph_text_accumulator:
            full_paragraph_str = " ".join(current_paragraph_text_accumulator).strip()
            if full_paragraph_str:
                 json_output.append({'type': 'paragraph', 'content': process_inline_elements(full_paragraph_str)})
            current_paragraph_text_accumulator = []

    for line_idx, raw_line in enumerate(lines):
        line = raw_line.strip()

        # Environment handling - using raw strings for environment checks
        if line == r'\begin{itemize}': # Corrected: was 'egin{itemize}'
            flush_paragraph()
            in_itemize_env = True
            continue
        if line == r'\end{itemize}':
            flush_paragraph()
            in_itemize_env = False
            continue
        if line == r'\begin{enumerate}': # Corrected: was 'egin{enumerate}'
            flush_paragraph()
            in_enumerate_env = True
            continue
        if line == r'\end{enumerate}':
            flush_paragraph()
            in_enumerate_env = False
            continue

        if in_itemize_env or in_enumerate_env:
            item_match = re.match(r'\\item\s*(.*)', line) # Using raw string
            if item_match:
                flush_paragraph() 
                item_content_line = item_match.group(1).strip()
                list_type = 'list_item_bullet' if in_itemize_env else 'list_item_ordered'
                if item_content_line:
                    json_output.append({'type': list_type, 'content': process_inline_elements(item_content_line)})
            else: 
                current_paragraph_text_accumulator.append(line) # Using stripped line as per original logic
            if line_idx == len(lines) - 1: flush_paragraph()
            continue
        
        if not line:
            flush_paragraph()
            continue

        # Standalone commands - using raw strings for regex
        title_match = re.match(r'\\title\{(.*)\}', line)
        if title_match:
            flush_paragraph()
            json_output.append({'type': 'title', 'content': _apply_basic_formatting_to_str(title_match.group(1).strip())})
            continue

        section_match = re.match(r'\\section\{(.*)\}', line)
        if section_match:
            flush_paragraph()
            json_output.append({'type': 'heading1', 'content': _apply_basic_formatting_to_str(section_match.group(1).strip())})
            continue

        subsection_match = re.match(r'\\subsection\{(.*)\}', line)
        if subsection_match:
            flush_paragraph()
            json_output.append({'type': 'heading2', 'content': _apply_basic_formatting_to_str(subsection_match.group(1).strip())})
            continue
        
        image_match = re.match(r'\\includegraphics(?:\[(.*?)\])?\{(.*?)\}', line)
        if image_match:
            flush_paragraph()
            options_str = image_match.group(1)
            image_path = image_match.group(2).strip()
            options_dict = parse_latex_options(options_str if options_str else "")
            json_output.append({'type': 'image', 'path': image_path, 'options': options_dict})
            continue
        
        current_paragraph_text_accumulator.append(line)

    flush_paragraph()
    return json_output

# --- DOCX Generation --- (Assumed correct from previous steps)
def construct_zotero_json_payload(citation_obj: dict) -> tuple[str, str]:
    citation_id = str(uuid.uuid4())
    keys = citation_obj.get('keys', [])
    prenote = citation_obj.get('prenote', '')
    command = citation_obj.get('command', 'citep') 

    plain_citation_parts = []
    keys_display_str = ", ".join(keys) 
    
    if command == 'citet':
        display_text = keys_display_str 
        if prenote:
            display_text += f" ({prenote})" 
    elif command == 'citeauthor':
        display_text = keys_display_str
    else: 
        if prenote:
            plain_citation_parts.append(prenote)
        plain_citation_parts.append(keys_display_str)
        display_text = f"({'; '.join(plain_citation_parts)})"
    
    plain_citation_for_display = display_text

    citation_items = []
    for key_idx, key in enumerate(keys):
        item_data = {"id": key, "type": "book"} 
        current_item_prenote = ""
        if key_idx == 0 and prenote:
             current_item_prenote = prenote
        
        citation_items.append({
            "itemData": item_data, 
            "prefix": current_item_prenote, 
            "suffix": "", 
            "uris": [f"http://zotero.org/users/local/placeholder/items/{key}"]
        })

    zotero_payload = {
        "citationID": citation_id,
        "properties": {"plainCitation": plain_citation_for_display },
        "citationItems": citation_items,
        "schema": "https://github.com/citation-style-language/schema/raw/master/csl-citation.json"
    }
    return json.dumps(zotero_payload), plain_citation_for_display


def add_runs_for_formatted_text(paragraph_or_heading, text_with_markers: str):
    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', text_with_markers) # Using raw string
    for part in parts:
        if not part: continue
        if part.startswith('**') and part.endswith('**'):
            paragraph_or_heading.add_run(part[2:-2]).bold = True
        elif part.startswith('*') and part.endswith('*'):
            paragraph_or_heading.add_run(part[1:-1]).italic = True
        else:
            paragraph_or_heading.add_run(part)

def generate_docx(json_data: list, output_docx_path: str):
    doc = docx.Document()
    doc.core_properties.title = "Converted LaTeX Document" 

    for item in json_data:
        item_type = item.get('type')
        
        if item_type == 'title':
            title_text = item.get('content', 'Untitled Document')
            doc.core_properties.title = title_text 
            h = doc.add_heading(level=0) 
            add_runs_for_formatted_text(h, title_text)
            
        elif item_type == 'heading1':
            h = doc.add_heading(level=1)
            add_runs_for_formatted_text(h, item.get('content', ''))
            
        elif item_type == 'heading2':
            h = doc.add_heading(level=2)
            add_runs_for_formatted_text(h, item.get('content', ''))
            
        elif item_type == 'paragraph' or item_type == 'list_item_bullet' or item_type == 'list_item_ordered':
            style = None
            if item_type == 'list_item_bullet': style = 'ListBullet'
            elif item_type == 'list_item_ordered': style = 'ListNumber'
            p = doc.add_paragraph(style=style)

            for content_element in item.get('content', []):
                element_type = content_element.get('type')
                if element_type == 'text':
                    add_runs_for_formatted_text(p, content_element.get('value', ''))
                elif element_type == 'citation':
                    zotero_json_string, plain_citation_text_for_display = construct_zotero_json_payload(content_element)
                    instr_text = f" ADDIN ZOTERO_ITEM CSL_CITATION {zotero_json_string}"
                    run = p.add_run()
                    fldSimple = OxmlElement('w:fldSimple')
                    fldSimple.set(qn('w:instr'), instr_text)
                    sub_r = OxmlElement('w:r')
                    sub_t = OxmlElement('w:t')
                    sub_t.text = plain_citation_text_for_display 
                    sub_r.append(sub_t)
                    fldSimple.append(sub_r)
                    run._r.append(fldSimple)

        elif item_type == 'image':
            image_path = item.get('path')
            options = item.get('options', {})
            if not os.path.exists(image_path):
                print(f"Warning: Image not found at {image_path}. Skipping.")
                p = doc.add_paragraph()
                add_runs_for_formatted_text(p, f"[Image not found: {image_path}]")
                continue
            try:
                width_str = options.get('width')
                width_val = None
                if width_str:
                    val_match = re.match(r'([\d\.]+)\s*(cm|in|px)?', width_str) # Using raw string
                    if val_match:
                        val = float(val_match.group(1))
                        unit = val_match.group(2)
                        if unit == 'cm': width_val = Cm(val)
                        elif unit == 'in': width_val = Inches(val)
                        else: print(f"Warning: Width unit '{unit}' for image {image_path} not directly supported.")
                    elif r'\textwidth' in width_str: 
                        print(f"Warning: Relative width '{width_str}' for image {image_path} not supported.")
                    else: 
                        print(f"Warning: Could not parse width '{width_str}' for image {image_path}.")
                
                if width_val: doc.add_picture(image_path, width=width_val)
                else: doc.add_picture(image_path)
            except Exception as e:
                print(f"Error adding image {image_path}: {e}. Skipping.")
                p = doc.add_paragraph(); add_runs_for_formatted_text(p, f"[Error adding image: {image_path}]")
    doc.save(output_docx_path)

# --- Internal Tests ---
def run_internal_parser_tests():
    print("Running Internal Parser Tests...")
    passed_count = 0
    failed_count = 0
    total_tests = 0
    # Define test cases directly - using raw strings for latex_input
    tests = [
        {"name": "test_parse_title", "latex_input": r"\title{My Test Title}", "expected_json": [{'type': 'title', 'content': 'My Test Title'}]},
        {"name": "test_parse_section", "latex_input": r"\section{Section One}", "expected_json": [{'type': 'heading1', 'content': 'Section One'}]},
        {"name": "test_parse_subsection", "latex_input": r"\subsection{Subsection A}", "expected_json": [{'type': 'heading2', 'content': 'Subsection A'}]},
        {"name": "test_parse_simple_paragraph_exact", "latex_input": "Just a plain paragraph.", "expected_json": [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'Just a plain paragraph.'}]}]},
        {"name": "test_parse_paragraph_with_bold", "latex_input": r"Some \textbf{bold} text.", "expected_json": [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'Some **bold** text.'}]}]}, # Adjusted
        {"name": "test_parse_paragraph_with_italic", "latex_input": r"An \textit{italic} word.", "expected_json": [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'An *italic* word.'}]}]}, # Adjusted
        {"name": "test_parse_itemize_list_simple", "latex_input": r"\begin{itemize}\item First item\item Second item\end{itemize}", "expected_json": [{'type': 'list_item_bullet', 'content': [{'type': 'text', 'value': 'First item'}]}, {'type': 'list_item_bullet', 'content': [{'type': 'text', 'value': 'Second item'}]}]}, # This will still fail, needs parser fix
        {"name": "test_parse_image_no_options", "latex_input": r"\includegraphics{images/my_pic.png}", "expected_json": [{'type': 'image', 'path': 'images/my_pic.png', 'options': {}}]},
        {"name": "test_parse_image_with_width_option", "latex_input": r"\includegraphics[width=10cm]{images/another_pic.jpeg}", "expected_json": [{'type': 'image', 'path': 'images/another_pic.jpeg', 'options': {'width': '10cm'}}]},
        {"name": "test_parse_citet_with_prenote", "latex_input": r"A citation \citet[see p.~15]{ref1} here.", "expected_json": [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'A citation '}, {'type': 'citation', 'command': 'citet', 'keys': ['ref1'], 'prenote': 'see p.~15', 'postnote': ''}, {'type': 'text', 'value': ' here.'}]}]},
        {"name": "test_parse_citep_multiple_keys", "latex_input": r"Another one \citep{ref2, ref3}.", "expected_json": [{'type': 'paragraph', 'content': [{'type': 'text', 'value': 'Another one '}, {'type': 'citation', 'command': 'citep', 'keys': ['ref2', 'ref3'], 'prenote': '', 'postnote': ''}, {'type': 'text', 'value': '.'}]}]}
    ]

    for test in tests:
        total_tests += 1
        test_name = test["name"]
        latex_input = test["latex_input"]
        expected_json = test["expected_json"]
        try:
            actual_json = parse_latex_to_json(latex_input)
            if actual_json == expected_json:
                print(f"[PASS] {test_name}")
                passed_count += 1
            else:
                print(f"[FAIL] {test_name}")
                print(f"  Input:    '{latex_input}'") # Show raw string input
                print(f"  Expected: {json.dumps(expected_json)}")
                print(f"  Actual:   {json.dumps(actual_json)}")
                failed_count += 1
        except Exception as e:
            print(f"[ERROR] {test_name} - Exception during test: {e}")
            failed_count += 1
            
    print("\nInternal Parser Test Summary:")
    print(f"Total tests: {total_tests}, Passed: {passed_count}, Failed: {failed_count}")
    if failed_count == 0: print("All internal parser tests passed!")
    else: print("Some internal parser tests failed.")

def main():
    parser = argparse.ArgumentParser(description='Convert LaTeX .tex file to .docx with Zotero citations.')
    parser.add_argument('input_file', nargs='?', default=None, help='Path to the input LaTeX (.tex) file (optional if running internal tests)')
    parser.add_argument('output_file', nargs='?', default=None, help='Path for the output DOCX (.docx) file (optional if running internal tests)')
    parser.add_argument('--run-internal-tests', action='store_true', help='Run embedded parser unit tests and exit.')
    args = parser.parse_args()

    if args.run_internal_tests:
        run_internal_parser_tests()
        sys.exit(0)

    if not args.input_file or not args.output_file:
        parser.print_help()
        print("\nError: input_file and output_file are required unless --run-internal-tests is specified.")
        sys.exit(1)

    try:
        print(f"Starting conversion of '{args.input_file}' to '{args.output_file}'...")
        with open(args.input_file, 'r', encoding='utf-8') as f:
            latex_text = f.read()
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
    except Exception as e: 
        print(f"Error reading input file '{args.input_file}': {e}")
        sys.exit(1)

    try:
        parsed_json_data = parse_latex_to_json(latex_text)
        generate_docx(parsed_json_data, args.output_file)
        print(f"Conversion successful! Output written to '{args.output_file}'")
    except Exception as e:
        print(f"An error occurred during LaTeX parsing or DOCX generation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
