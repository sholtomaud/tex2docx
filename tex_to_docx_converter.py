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


# Compiled regexes for citation commands
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

# Removed zotero_instr_text_print_count global variable

def _apply_basic_formatting_to_str(text_segment: str) -> str:
    if not text_segment: return ""
    content = re.sub(r'\\textbf\{(.*?)\}', r'**\1**', text_segment)
    content = re.sub(r'\\textit\{(.*?)\}', r'*\1*', content)
    return content

def process_inline_elements(text_line: str) -> list:
    elements = []
    current_pos = 0
    
    while current_pos < len(text_line):
        earliest_match = None
        earliest_match_pos = len(text_line)
        command_name_for_match = None
        match_obj = None

        for cmd_name, cmd_re in CITATION_COMMANDS:
            match = cmd_re.search(text_line, current_pos)
            if match and match.start() < earliest_match_pos:
                earliest_match_pos = match.start()
                earliest_match = match
                command_name_for_match = cmd_name
                match_obj = match

        if earliest_match:
            if earliest_match.start() > current_pos:
                pre_text = text_line[current_pos:earliest_match.start()]
                elements.append({'type': 'text', 'value': _apply_basic_formatting_to_str(pre_text)})
            
            prenote = ""
            keys_str = ""
            if command_name_for_match == 'citeauthor':
                keys_str = match_obj.group(1)
            else: 
                prenote = match_obj.group(1) if match_obj.group(1) else ""
                keys_str = match_obj.group(2)
            
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
            if current_pos < len(text_line):
                post_text = text_line[current_pos:]
                elements.append({'type': 'text', 'value': _apply_basic_formatting_to_str(post_text)})
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
    current_paragraph_text = ""
    in_itemize_env = False
    in_enumerate_env = False

    for line in lines:
        line = line.strip()

        if line == r'\end{itemize}':
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            in_itemize_env = False
            continue
        
        if line == r'\end{enumerate}':
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            in_enumerate_env = False
            continue

        if line == r'\begin{itemize}':
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            in_itemize_env = True
            continue

        if line == r'\begin{enumerate}':
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            in_enumerate_env = True
            continue

        if in_itemize_env:
            item_match = re.match(r'\\item\s*(.*)', line)
            if item_match:
                if current_paragraph_text: 
                    json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                    current_paragraph_text = ""
                item_content_line = item_match.group(1).strip()
                json_output.append({'type': 'list_item_bullet', 'content': process_inline_elements(item_content_line)})
            else: 
                current_paragraph_text += " " + line 
            continue 
            
        if in_enumerate_env:
            item_match = re.match(r'\\item\s*(.*)', line)
            if item_match:
                if current_paragraph_text: 
                    json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                    current_paragraph_text = ""
                item_content_line = item_match.group(1).strip()
                json_output.append({'type': 'list_item_ordered', 'content': process_inline_elements(item_content_line)})
            else: 
                current_paragraph_text += " " + line
            continue

        if not line: 
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            continue

        title_match = re.match(r'\\title\{(.*)\}', line)
        if title_match:
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            json_output.append({'type': 'title', 'content': _apply_basic_formatting_to_str(title_match.group(1).strip())})
            continue

        section_match = re.match(r'\\section\{(.*)\}', line)
        if section_match:
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            json_output.append({'type': 'heading1', 'content': _apply_basic_formatting_to_str(section_match.group(1).strip())})
            continue

        subsection_match = re.match(r'\\subsection\{(.*)\}', line)
        if subsection_match:
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            json_output.append({'type': 'heading2', 'content': _apply_basic_formatting_to_str(subsection_match.group(1).strip())})
            continue
        
        image_match = re.match(r'\\includegraphics(?:\[(.*?)\])?\{(.*?)\}', line)
        if image_match:
            if current_paragraph_text:
                json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
                current_paragraph_text = ""
            options_str = image_match.group(1)
            image_path = image_match.group(2).strip()
            options_dict = parse_latex_options(options_str)
            json_output.append({'type': 'image', 'path': image_path, 'options': options_dict})
            continue
        
        if current_paragraph_text:
            current_paragraph_text += " " + line 
        else:
            current_paragraph_text = line

    if current_paragraph_text:
        json_output.append({'type': 'paragraph', 'content': process_inline_elements(current_paragraph_text.strip())})
    return json_output

# --- DOCX Generation ---

def construct_zotero_json_payload(citation_obj: dict) -> tuple[str, str]:
    citation_id = str(uuid.uuid4())
    keys = citation_obj.get('keys', [])
    prenote = citation_obj.get('prenote', '')
    command = citation_obj.get('command', 'citep') 

    plain_citation_parts = []
    if prenote:
        plain_citation_parts.append(prenote)
    keys_display_str = ", ".join(keys)
    plain_citation_parts.append(keys_display_str)
    
    if command in ['citep', 'citeyearpar']:
        plain_citation_for_display = f"({'; '.join(plain_citation_parts)})"
    elif command == 'citet':
        plain_citation_for_display = f"{keys_display_str}"
        if prenote:
             plain_citation_for_display += f", {prenote}"
    elif command == 'citeauthor':
        plain_citation_for_display = keys_display_str
    else: 
        plain_citation_for_display = f"({'; '.join(plain_citation_parts)})"

    citation_items = []
    first_item = True
    for key in keys:
        item_data = {"id": key, "type": "book"}
        current_prenote = prenote if first_item else ""
        first_item = False
        citation_items.append({
            "itemData": item_data, "prefix": current_prenote, "suffix": "",
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
    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', text_with_markers)
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
    
    for item in json_data:
        item_type = item.get('type')
        
        if item_type == 'title':
            title_text = item.get('content', 'Untitled')
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
            if item_type == 'paragraph':
                p = doc.add_paragraph()
            elif item_type == 'list_item_bullet':
                p = doc.add_paragraph(style='ListBullet')
            else: # list_item_ordered
                p = doc.add_paragraph(style='ListNumber')

            for content_element in item.get('content', []):
                element_type = content_element.get('type')
                if element_type == 'text':
                    add_runs_for_formatted_text(p, content_element.get('value', ''))
                elif element_type == 'citation':
                    zotero_json_string, plain_citation_text = construct_zotero_json_payload(content_element)
                    instr_text = f" ADDIN ZOTERO_ITEM CSL_CITATION {zotero_json_string}"
                    
                    # Removed the debug print for instr_text here
                    
                    run = p.add_run()
                    fldSimple = OxmlElement('w:fldSimple')
                    fldSimple.set(qn('w:instr'), instr_text)
                    sub_r = OxmlElement('w:r')
                    sub_t = OxmlElement('w:t')
                    sub_t.text = plain_citation_text 
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
                    if 'cm' in width_str: width_val = Cm(float(re.sub(r'[^\d\.]', '', width_str)))
                    elif 'in' in width_str: width_val = Inches(float(re.sub(r'[^\d\.]', '', width_str)))
                    elif '\\textwidth' in width_str: print(f"Warning: Relative width '{width_str}' for image {image_path} not directly supported.")
                    else: print(f"Warning: Unknown width unit in '{width_str}' for image {image_path}.")
                if width_val: doc.add_picture(image_path, width=width_val)
                else: doc.add_picture(image_path)
            except FileNotFoundError: # Should be caught by os.path.exists, but good for robustness
                print(f"Error: Image file not found at {image_path} (checked again). Skipping.")
                p = doc.add_paragraph(); add_runs_for_formatted_text(p, f"[Image not found: {image_path}]")
            except Exception as e:
                print(f"Error adding image {image_path}: {e}. Skipping.")
                p = doc.add_paragraph(); add_runs_for_formatted_text(p, f"[Error adding image: {image_path}]")

    doc.save(output_docx_path)
    # Moved the success message to main()

def main():
    parser = argparse.ArgumentParser(description='Convert LaTeX .tex file to .docx with Zotero citations.')
    parser.add_argument('input_file', help='Path to the input LaTeX (.tex) file')
    parser.add_argument('output_file', help='Path for the output DOCX (.docx) file')
    args = parser.parse_args()

    try:
        print(f"Starting conversion of '{args.input_file}' to '{args.output_file}'...")
        with open(args.input_file, 'r', encoding='utf-8') as f:
            latex_text = f.read()
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
    except Exception as e: # Catch other potential errors during file reading
        print(f"Error reading input file '{args.input_file}': {e}")
        sys.exit(1)

    try:
        parsed_json_data = parse_latex_to_json(latex_text)
        
        # Optional: For debugging, you might save the intermediate JSON
        # with open('intermediate_parsed.json', 'w', encoding='utf-8') as jf:
        #     json.dump(parsed_json_data, jf, indent=2)

        generate_docx(parsed_json_data, args.output_file)
        print(f"Conversion successful! Output written to '{args.output_file}'")

    except Exception as e:
        print(f"An error occurred during LaTeX parsing or DOCX generation: {e}")
        # For more detailed debugging, uncomment the following lines:
        # import traceback
        # print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
