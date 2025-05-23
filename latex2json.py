import re
import json
from datetime import datetime, timezone
import os

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    print("Warning: jsonschema library not found. JSON validation will be skipped.")

# --- LaTeX Color Name to Hex Mapping ---
LATEX_COLOR_TO_HEX = {
    "black": "#000000", "white": "#FFFFFF", "red": "#FF0000",
    "green": "#00FF00", "blue": "#0000FF", "cyan": "#00FFFF",
    "magenta": "#FF00FF", "yellow": "#FFFF00", "gray": "#808080",
    "AliceBlue": "#F0F8FF", "AntiqueWhite": "#FAEBD7", "Aqua": "#00FFFF",
    "Aquamarine": "#7FFFD4", "Azure": "#F0FFFF", "Beige": "#F5F5DC",
    "Bisque": "#FFE4C4", "BlanchedAlmond": "#FFEBCD", "BlueViolet": "#8A2BE2",
    "Brown": "#A52A2A", "BurlyWood": "#DEB887", "CadetBlue": "#5F9EA0",
    "Chartreuse": "#7FFF00", "Chocolate": "#D2691E", "Coral": "#FF7F50",
    "CornflowerBlue": "#6495ED", "Cornsilk": "#FFF8DC", "Crimson": "#DC143C",
    "DarkBlue": "#00008B", "DarkCyan": "#008B8B", "DarkGoldenRod": "#B8860B",
    "DarkGray": "#A9A9A9", "DarkGrey": "#A9A9A9", "DarkGreen": "#006400",
    "Green": "#008000", "Blue": "#0000FF", 
}

class LatexToJsonConverter:
    _inline_pattern_str = (
        r"(\\textbf\{(.*?)\})" +  # G1, G2:content
        r"|(\\textit\{(.*?)\})" + # G3, G4:content
        r"|(\\emph\{(.*?)\})" +  # G5, G6:content
        r"|(\\underline\{(.*?)\})" + # G7, G8:content
        r"|(\\texttt\{(.*?)\})" + # G9, G10:content
        r"|(\\textcolor\{([a-zA-Z0-9_]+)\}\{(.*?)\})" +  # G11, G12:color, G13:content
        r"|(\{\s*\\color\{([a-zA-Z0-9_]+)\}(.*?)\})" +  # G14, G15:color, G16:content
        r"|(\\url\{(.*?)\})" + # G17, G18:content
        r"|(\\href\{[^}]*\}\{(.*?)\})" +  # G19, G20:content (display text)
        r"|(\\(?:cite|citep|citet|citeauthor)(?:\[(.*?)\])?\{(.*?)\})" + # G21, G22:opt_arg, G23:key
        # Modified generic command to be less aggressive with commands followed by {
        r"|(\\[a-zA-Z@]+(?!\s*\{))"  # G24:cmd_text (generic command, not followed by {)
    )
    COMPILED_INLINE_PATTERN = re.compile(_inline_pattern_str, re.DOTALL)

    def __init__(self, latex_filepath, schema_filepath="document_schema.json"):
        self.latex_filepath = latex_filepath
        self.schema_filepath = schema_filepath
        self.latex_content = ""
        self.base_dir = os.path.dirname(os.path.abspath(latex_filepath))
        self.json_output = self._get_default_json()
        self.macros = {}
        self.defined_colors = LATEX_COLOR_TO_HEX.copy()
        self.graphicspath = ["./", ""] 
        self.schema = self._load_schema()
        self.current_text_width_inches = 6.5

    def _load_schema(self):
        if not JSONSCHEMA_AVAILABLE:
            return None
        try:
            with open(self.schema_filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Schema file '{self.schema_filepath}' not found. Validation will be skipped.")
            return None
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from schema file '{self.schema_filepath}'. Validation will be skipped.")
            return None

    def _get_default_json(self):
        return {
            "properties": {
                "title": "Untitled Document", "author": "Unknown Author", "subject": "",
                "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            "template_path": "",
            "page_layout": {"orientation": "portrait", "margins": { "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0 }},
            "content": []
        }

    def _validate_output(self):
        if not JSONSCHEMA_AVAILABLE or not self.schema:
            print("Skipping JSON validation (jsonschema not available or schema not loaded).")
            return True
        try:
            validate(instance=self.json_output, schema=self.schema)
            print("JSON validation successful against schema.")
            return True
        except ValidationError as e:
            print(f"JSON Validation Error: {e.message} at path {list(e.path)}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during JSON validation: {e}")
            return False

    def _clean_latex_text_segment(self, text):
        text = text.replace(r"~", " ")
        text = text.replace(r"\'e", "é").replace(r"\'a", "á")
        text = text.replace(r"\%", "%").replace(r"\&", "&").replace(r"\#", "#")
        text = text.replace(r"\$", "$").replace(r"\_", "_")
        text = text.replace(r"\{", "{").replace(r"\}", "}")
        text = text.replace(r"\\", "\n").replace(r"\newline", "\n")
        return text

    def _extract_definitions(self, preamble):
        for match in re.finditer(r"\\newcommand\{\s*\\(\w+)\s*\}\s*\{(.*?)\}(?!\s*\[)", preamble):
            self.macros[match.group(1)] = match.group(2)
        for match in re.finditer(r"\\definecolor\{(.*?)\}\s*\{(HTML|rgb)\}\s*\{(.*?)\}", preamble):
            name, model, spec = match.groups()
            name = name.strip()
            if model == "HTML" and re.match(r"^[0-9A-Fa-f]{6}$", spec):
                self.defined_colors[name] = f"#{spec.upper()}"
            elif model == "rgb":
                try:
                    r, g, b = [float(x.strip()) for x in spec.split(',')]
                    self.defined_colors[name] = f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
                except ValueError:
                    print(f"Warning: Could not parse rgb color spec '{spec}' for color '{name}'.")

    def _expand_macros(self, text, depth=0):
        if depth > 10: return text
        original_text = text
        for cmd, replacement in self.macros.items():
            escaped_cmd = re.escape(cmd)
            try:
                text = re.sub(r"\\" + escaped_cmd + r"(?!\w)", lambda m: replacement, text)
            except re.error: # Fallback for simple replacement if regex fails (e.g. complex command name)
                text = text.replace(f"\\{cmd}", replacement)
        return self._expand_macros(text, depth + 1) if text != original_text else text

    def _parse_preamble(self, preamble_text):
        title_str_for_content = None
        title_match = re.search(r"\\title\{(.*?)\}", preamble_text, re.DOTALL)
        if title_match:
            title_str_for_content = self._strip_latex_commands(self._expand_macros(title_match.group(1).strip()))
            self.json_output["properties"]["title"] = title_str_for_content
        
        author_match = re.search(r"\\author\{(.*?)\}", preamble_text, re.DOTALL)
        if author_match:
            self.json_output["properties"]["author"] = self._strip_latex_commands(self._expand_macros(author_match.group(1).strip()))

        if title_str_for_content:
            if "content" not in self.json_output: self.json_output["content"] = []
            self.json_output["content"].append({"type": "title_paragraph", "content": [{"type": "text", "text": title_str_for_content}]})

        # (Geometry, graphicspath, etc. parsing would go here if fully implemented)
        graphicspath_match = re.search(r"\\graphicspath\{\s*\{(.*?)\}\s*\}", preamble_text, re.DOTALL)
        if graphicspath_match:
            paths_str = graphicspath_match.group(1).strip()
            self.graphicspath = [p.strip() for p in paths_str.split("}{") if p.strip()]


    def _strip_latex_commands(self, text, keep_content=True):
        text = str(text)
        for _ in range(3): # Iterate a few times to handle nested simple commands
            prev_text = text
            text = re.sub(r"\\[a-zA-Z@]+(?:\[[^\]]*\])?\{(.*?)\}", r"\1" if keep_content else "", text)
            text = re.sub(r"\\[a-zA-Z@]+", "", text) # Strip commands without args
            if text == prev_text: break
        text = text.replace("{", "").replace("}", "") # Remove remaining braces
        return self._clean_latex_text_segment(text.strip())

    def _parse_inline_text_to_content_items(self, latex_string):
        content_items = []
        latex_string = self._expand_macros(latex_string)

        def generate_runs(text_segment, current_formatting):
            # --- BEGIN TEMPORARY DEBUG BLOCK ---
            # Using repr() for the whole segment to see all characters.
            print(f"DEBUG_PARSE: generate_runs called with segment (repr): {repr(text_segment[:70])} CF={current_formatting}")
            if text_segment.startswith("\\textit{"):
                m_debug = re.match(r"\\textit\{(.*?)\}", text_segment, re.DOTALL)
                print(f"DEBUG_PARSE: \\textit specific re.match on '{text_segment[:30]}': {'SUCCESS' if m_debug else 'FAIL'}")
                if m_debug: print(f"DEBUG_PARSE: \\textit content: '{m_debug.group(1)}'") # Removed repr for content
            
            if text_segment.startswith("\\textcolor{"):
                m_debug = re.match(r"\\textcolor\{([a-zA-Z0-9_]+)\}\{(.*?)\}", text_segment, re.DOTALL)
                print(f"DEBUG_PARSE: \\textcolor specific re.match on '{text_segment[:40]}': {'SUCCESS' if m_debug else 'FAIL'}")
                if m_debug: print(f"DEBUG_PARSE: \\textcolor color='{m_debug.group(1)}', content: '{m_debug.group(2)}'") # Removed repr for content
            # --- END TEMPORARY DEBUG BLOCK ---

            runs = []
            last_pos = 0

            for match in LatexToJsonConverter.COMPILED_INLINE_PATTERN.finditer(text_segment):
                start, end = match.span()
                
                if start > last_pos:
                    plain_text = self._clean_latex_text_segment(text_segment[last_pos:start])
                    if plain_text:
                        runs.append({"type": "text", "text": plain_text, "formatting": current_formatting.copy() if current_formatting else {}})
                
                new_formatting = current_formatting.copy()
                content_to_recurse = ""

                if match.group(1): # \textbf (G2 content)
                    new_formatting["bold"] = True
                    raw_content = match.group(2)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: \\textbf matched. Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(3): # \textit (G4 content)
                    new_formatting["italic"] = True
                    raw_content = match.group(4)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: \\textit matched. Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(5): # \emph (G6 content)
                    new_formatting["italic"] = True
                    raw_content = match.group(6)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: \\emph matched. Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(7): # \underline (G8 content)
                    new_formatting["underline"] = True
                    raw_content = match.group(8)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: \\underline matched. Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(9): # \texttt (G10 content)
                    new_formatting["font_name"] = "Courier New" 
                    raw_content = match.group(10)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: \\texttt matched. Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(11): # \textcolor (G12 color, G13 content)
                    color_name = match.group(12) 
                    hex_color = self.defined_colors.get(color_name)
                    if hex_color: new_formatting["color"] = hex_color
                    else: print(f"Warning: Undefined color '{color_name}' used in textcolor.")
                    raw_content = match.group(13)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: \\textcolor matched. Color='{color_name}', Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(14): # {\color ...} (G15 color, G16 content)
                    color_name = match.group(15) 
                    hex_color = self.defined_colors.get(color_name)
                    if hex_color: new_formatting["color"] = hex_color
                    else: print(f"Warning: Undefined color '{color_name}' used in color group.")
                    raw_content = match.group(16)
                    content_to_recurse = raw_content.strip()
                    print(f"DEBUG_PARSE: {{\\color...}} matched. Color='{color_name}', Raw_content(repr)={repr(raw_content[:50])}, Stripped_content(repr)={repr(content_to_recurse[:50])}")
                elif match.group(17): # \url (G18 content)
                    url_content = self._clean_latex_text_segment(match.group(18).strip())
                    runs.append({"type": "text", "text": url_content, "formatting": current_formatting.copy() if current_formatting else {}})
                elif match.group(19): # \href (G20 content)
                    display_text = self._clean_latex_text_segment(match.group(20).strip())
                    runs.append({"type": "text", "text": display_text, "formatting": current_formatting.copy() if current_formatting else {}})
                elif match.group(21): # Citation (G22 opt_arg, G23 key)
                    key_text = match.group(23) 
                    runs.append({
                        "type": "citation", "display_text": f"[{key_text}]", 
                        "field_data": {"key": key_text, "latex_command": match.group(21)} 
                    })
                elif match.group(24): # Other command (\\[a-zA-Z@]+)
                    idx_after_cmd = match.end()
                    if idx_after_cmd < len(text_segment) and text_segment[idx_after_cmd] == '{':
                        brace_level = 1
                        idx_arg_end = idx_after_cmd + 1
                        while idx_arg_end < len(text_segment):
                            if text_segment[idx_arg_end] == '{': brace_level += 1
                            elif text_segment[idx_arg_end] == '}':
                                brace_level -= 1
                                if brace_level == 0: break 
                            idx_arg_end += 1
                    pass 
                else: 
                    unhandled_text = self._clean_latex_text_segment(match.group(0))
                    if unhandled_text:
                         runs.append({"type": "text", "text": f"[Unhandled Regex M.: {unhandled_text}]", "formatting": current_formatting.copy() if current_formatting else {}})

                if content_to_recurse:
                    runs.extend(generate_runs(content_to_recurse, new_formatting))
                
                last_pos = end
            
            if last_pos < len(text_segment):
                plain_text_segment = text_segment[last_pos:]
                plain_text = self._clean_latex_text_segment(plain_text_segment)
                if plain_text:
                    runs.append({"type": "text", "text": plain_text, "formatting": current_formatting.copy() if current_formatting else {}})
            return runs

        raw_items = generate_runs(latex_string, {})
        merged_items = []
        if raw_items:
            for item in raw_items:
                if item["type"] == "text":
                    if "text" not in item: item["text"] = ""
                    if "formatting" in item and not item["formatting"]: del item["formatting"]
                if merged_items and merged_items[-1]["type"] == "text" and item["type"] == "text" and merged_items[-1].get("formatting") == item.get("formatting"):
                    merged_items[-1]["text"] += item["text"]
                elif item.get("text", "").strip() or item["type"] != "text":
                    merged_items.append(item)
        return [item for item in merged_items if item.get("text", "").strip() or item.get("type") != "text"]

    def _find_image_path(self, image_name):
        # (Implementation as before)
        if os.path.isabs(image_name) and os.path.exists(image_name): return image_name
        for prefix in [""] + self.graphicspath:
            current_prefix_path = os.path.join(self.base_dir, prefix)
            path_to_check = os.path.normpath(os.path.join(current_prefix_path, image_name))
            if os.path.exists(path_to_check): return path_to_check
        print(f"Warning: Image '{image_name}' not found with graphicspaths: {self.graphicspath} relative to {self.base_dir}")
        return image_name

    def _parse_latex_dimension(self, dim_str):
        # (Implementation as before)
        if not dim_str: return None
        dim_str = self._expand_macros(dim_str)
        match = re.match(r"([\d.]+)\s*(in|cm|mm|pt|em|ex|\\textwidth|\\linewidth)?", dim_str)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            if unit == "in": return val
            if unit == "cm": return val / 2.54
            if unit == "mm": return val / 25.4
            if unit == "pt": return val / 72.0
            if unit in ["\\textwidth", "\\linewidth"]: return val * self.current_text_width_inches
            return val / 72.0 
        return None

    def _parse_body(self, body_text_raw):
        body_text_cleaned = re.sub(r"(?<!\\)%.*", "", body_text_raw)
        body_text_cleaned = re.sub(r"%TC:ignore.*?%TC:endignore", "", body_text_cleaned, flags=re.DOTALL)
        block_pattern = re.compile(
            r"\\(section|subsection|subsubsection)(?:\[(.*?)\])?\{(.*?)\}" 
            r"|\\begin\{(figure|table|itemize|enumerate|quotation|verbatim|longtable|tabularx|tabular|subcaption|subfigure)\}(.*?)\\end\{\4\}" 
            r"|\\(newpage|clearpage)" 
            r"|\\(printbibliography|bibliography\{(.*?)\})" 
            , re.DOTALL)
        current_pos = 0
        while current_pos < len(body_text_cleaned):
            match = block_pattern.search(body_text_cleaned, current_pos)
            text_before_match_raw = body_text_cleaned[current_pos:(match.start() if match else len(body_text_cleaned))]
            if text_before_match_raw.strip():
                paragraphs_latex = re.split(r'\n\s*\n+', text_before_match_raw.strip())
                for para_latex in paragraphs_latex:
                    if para_latex.strip():
                        para_content_items = self._parse_inline_text_to_content_items(para_latex.strip())
                        if para_content_items:
                            self.json_output["content"].append({"type": "normal", "content": para_content_items})
            if not match: break
            current_pos = match.end()
            if match.group(1): # Section
                sec_type_str, sec_title_raw = match.group(1), match.group(3).strip()
                heading_type = f"heading{ {'section': 1, 'subsection': 2, 'subsubsection': 3}.get(sec_type_str, 1) }"
                sec_title_items = self._parse_inline_text_to_content_items(sec_title_raw)
                if sec_title_items: self.json_output["content"].append({"type": heading_type, "content": sec_title_items})
            elif match.group(4): # Environment
                env_name, env_content_raw = match.group(4), match.group(5)
                if env_name == "figure": # Simplified figure handling
                    img_match = re.search(r"\\includegraphics(?:\[(.*?)\])?\{(.*?)\}", env_content_raw, re.DOTALL)
                    if img_match: self.json_output["content"].append({"type": "normal", "content": [{"type": "image", "path": self._find_image_path(img_match.group(2))}]}) # Basic image
                elif env_name in ["itemize", "enumerate"]:
                    list_obj = {"type": "list", "list_type": "bullet" if env_name == "itemize" else "number", "level": 0, "items": []}
                    item_matches = re.finditer(r"\\item(?:\s+|\[.*?\]\s*)(.*?)(?=\\item|\\end\{" + env_name + r"\}|\Z)", env_content_raw, re.DOTALL | re.IGNORECASE)
                    for item_match in item_matches:
                        item_content_raw = item_match.group(1).strip()
                        if not item_content_raw: continue
                        parsed_item_runs = self._parse_inline_text_to_content_items(item_content_raw)
                        item_text_parts, first_run_formatting, consistent_formatting = [], None, True
                        for i, run in enumerate(parsed_item_runs):
                            if run.get("type") == "text" and "text" in run:
                                item_text_parts.append(run["text"])
                                current_run_fmt = run.get("formatting")
                                if i == 0: first_run_formatting = current_run_fmt
                                elif current_run_fmt != first_run_formatting: consistent_formatting = False
                            elif run.get("type") == "citation": item_text_parts.append(run.get("display_text","[c]")); consistent_formatting = False
                        final_item_text = "".join(item_text_parts).strip()
                        if final_item_text:
                            list_item_obj = {"text": final_item_text}
                            if consistent_formatting and first_run_formatting: list_item_obj["formatting"] = first_run_formatting
                            list_obj["items"].append(list_item_obj)
                    if list_obj["items"]: self.json_output["content"].append(list_obj)
                elif env_name == "quotation":
                    # (Implementation as before)
                    quote_items = self._parse_inline_text_to_content_items(env_content_raw.strip())
                    if quote_items: self.json_output["content"].append({"type": "normal", "formatting": {"left_indent":0.5, "right_indent":0.5}, "content": quote_items})
                elif env_name == "verbatim":
                    # (Implementation as before)
                    self.json_output["content"].append({"type":"normal", "content": [{"type":"text", "text":env_content_raw.strip(), "formatting":{"font_name":"Courier New"}}]})

                elif env_name in ["table", "longtable", "tabularx", "tabular"]:
                    table_obj = {"type": "table", "data": []}
                    processed_env_content_raw = re.sub(r"^\s*\{[\|lcrp@\s{}A-Za-z0-9\.=\[\]\(\)\,\;\:\<\>\!\$\%\^\&\*\-\+\/\?\~\\]*\}\s*", "", env_content_raw.strip(), count=1)
                    rows_latex = processed_env_content_raw.strip().split("\\\\")
                    for row_latex in rows_latex:
                        row_data_string = row_latex.strip()
                        while row_data_string.startswith("\\hline") or row_data_string.startswith("\\cline"):
                            if row_data_string.startswith("\\hline"): row_data_string = row_data_string[len("\\hline"):].strip()
                            elif row_data_string.startswith("\\cline"):
                                match_cline = re.match(r"\\cline\s*\{.*?\}(.*)", row_data_string)
                                if match_cline: row_data_string = match_cline.group(1).strip()
                                else: break 
                        if not row_data_string: continue
                        cells_latex = row_data_string.split("&")
                        table_row_json = []
                        for cell_latex in cells_latex:
                            cell_items = self._parse_inline_text_to_content_items(cell_latex.strip())
                            if not cell_items: table_row_json.append(""); continue
                            cell_text_parts, first_run_fmt, consistent_fmt = [], None, True
                            for i, run in enumerate(cell_items):
                                if run.get("type")=="text" and "text" in run: 
                                    cell_text_parts.append(run["text"])
                                    cur_fmt = run.get("formatting")
                                    if i==0: first_run_fmt = cur_fmt
                                    elif cur_fmt != first_run_fmt: consistent_fmt = False
                                elif run.get("type")=="citation": cell_text_parts.append(run.get("display_text","[c]")); consistent_fmt=False
                            final_cell_text = "".join(cell_text_parts).strip()
                            cell_obj = {"text":final_cell_text}
                            if consistent_fmt and first_run_fmt: cell_obj["formatting"]=first_run_fmt
                            table_row_json.append("" if not cell_obj["text"] and "formatting" not in cell_obj else cell_obj)
                        if any(c for c in table_row_json if (isinstance(c,str) and c.strip()) or (isinstance(c,dict) and c.get("text","").strip()) or (isinstance(c,dict) and c.get("formatting"))):
                            table_obj["data"].append(table_row_json)
                    if table_obj["data"]: self.json_output["content"].append(table_obj)
            elif match.group(6): self.json_output["content"].append({"type": "page_break"})
            elif match.group(7): self.json_output["content"].append({"type":"bibliography", "display_text":"References", "field_data": {"source_file":match.group(8).strip() if match.group(8) else ""}})
        
        # Final schema compliance (simplified)
        final_content = []
        for block in self.json_output.get("content", []):
            if block.get("type") in ["normal", "heading1", "heading2", "heading3", "title_paragraph"]:
                if not block.get("content"): block["content"] = [{"type":"text", "text":""}] # Ensure content for paragraphs
            final_content.append(block)
        self.json_output["content"] = final_content


    def convert(self):
        try:
            with open(self.latex_filepath, 'r', encoding='utf-8') as f:
                self.latex_content = f.read()
        except FileNotFoundError:
            print(f"Error: File not found at {self.latex_filepath}")
            return None
        # (Other error handling as before)

        doc_env_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", self.latex_content, re.DOTALL)
        if not doc_env_match:
            preamble_text_raw, body_text_raw = "", self.latex_content 
        else:
            preamble_text_raw, body_text_raw = self.latex_content[:doc_env_match.start()], doc_env_match.group(1)

        preamble_text_cleaned = re.sub(r"(?<!\\)%.*", "", preamble_text_raw)
        preamble_text_cleaned = re.sub(r"%TC:ignore.*?%TC:endignore", "", preamble_text_cleaned, flags=re.DOTALL)
        
        self._extract_definitions(preamble_text_cleaned)
        preamble_text_processed = self._expand_macros(preamble_text_cleaned)
        self._parse_preamble(preamble_text_processed)
        self._parse_body(body_text_raw)
        
        if not self._validate_output():
            print("JSON output failed validation. Review warnings/errors.")
        return self.json_output

import argparse # Make sure argparse is imported at the top

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Convert LaTeX file to JSON.")
    parser.add_argument("input_file", nargs='?', default=None,
                        help="Path to the input LaTeX file. If not provided, uses internal example_latex_content.")
    parser.add_argument("--output", default="converted_latex_strict_v2.json",
                        help="Path to the output JSON file (default: converted_latex_strict_v2.json).")
    args = parser.parse_args()

    input_latex_file_arg = args.input_file
    output_json_file_arg = args.output
    
    schema_filename = "document_schema.json" # Schema expected in CWD by the script
    if not os.path.exists(schema_filename) and os.path.exists("schema/document_schema.json"):
        import shutil
        shutil.copy("schema/document_schema.json", schema_filename)
        print(f"Copied {schema_filename} to current directory for script use.")

    if input_latex_file_arg:
        # Use the provided input file
        if not os.path.exists(input_latex_file_arg):
            print(f"ERROR: Input file '{input_latex_file_arg}' not found.")
            # Optionally, exit or use a default behavior
            # For this task, if a specific input is given and not found, we should probably error.
            # However, the prompt implies to run on test_input.tex which should exist.
            # For now, let's assume if input_file_arg is given, it's the one to use.
            # If it doesn't exist, the converter will fail later with FileNotFoundError.
            pass # Let the LatexToJsonConverter handle the FileNotFoundError
        
        print(f"Processing CLI input: {input_latex_file_arg} -> {output_json_file_arg}")
        converter = LatexToJsonConverter(input_latex_file_arg, schema_filepath=schema_filename)
        json_data = converter.convert()
        if json_data:
            with open(output_json_file_arg, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)
            print(f"Conversion successful. Output written to {output_json_file_arg}")
        else:
            print(f"Conversion failed for {input_latex_file_arg}.")

    else:
        # Default behavior: use internal example_latex_content and output to default name
        # This is the original __main__ block's behavior
        print("No input file provided, using internal example content.")
        example_latex_content = r"""
%TC:ignore
\documentclass[a4paper,12pt]{article}
\usepackage[english]{babel}
\usepackage{graphicx}
\usepackage[svgnames, dvipsnames]{xcolor} 
\usepackage{amsmath} 
\usepackage{url}
\usepackage{geometry}
\geometry{margin=1in, right=1.2in} 
\graphicspath{{./}{../images/}} 

\title{My Awesome Document \textit{with Style}}
\author{Dr. LaTeX User}
\date{\today}

\definecolor{mycustomred}{HTML}{CC0000}
\definecolor{mycustomgreen}{rgb}{0,0.5,0}
\newcommand{\important}[1]{\textbf{\textcolor{mycustomred}{#1}}}
\newcommand{\docname}{My Test Doc}
%TC:endignore

\begin{document}
\section{Introduction to \docname}
This is a default paragraph.
\end{document}
        """
        internal_example_file = "example_converter_input.tex"
        with open(internal_example_file, "w", encoding="utf-8") as f:
            f.write(example_latex_content)
        
        # Ensure dummy images for internal example if they don't exist
        if not os.path.exists("example_image.png"): 
            open("example_image.png", "wb").write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\x99c`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82')
        if not os.path.exists("test.JPG"): 
            open("test.JPG", "wb").write(b"dummy jpg")

        print(f"Processing internal example: {internal_example_file} -> {output_json_file_arg}")
        converter = LatexToJsonConverter(internal_example_file, schema_filepath=schema_filename)
        json_data = converter.convert()
        if json_data:
            with open(output_json_file_arg, "w", encoding="utf-8") as f: # output_json_file_arg is default "converted_latex_strict_v2.json" here
                json.dump(json_data, f, indent=4, ensure_ascii=False)
            print(f"Conversion successful. Output written to {output_json_file_arg}")
        else:
            print(f"Conversion failed for {internal_example_file}.")
