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
    # dvipsnames examples
    "AliceBlue": "#F0F8FF", "AntiqueWhite": "#FAEBD7", "Aqua": "#00FFFF",
    "Aquamarine": "#7FFFD4", "Azure": "#F0FFFF", "Beige": "#F5F5DC",
    "Bisque": "#FFE4C4", "BlanchedAlmond": "#FFEBCD", "BlueViolet": "#8A2BE2",
    "Brown": "#A52A2A", "BurlyWood": "#DEB887", "CadetBlue": "#5F9EA0",
    "Chartreuse": "#7FFF00", "Chocolate": "#D2691E", "Coral": "#FF7F50",
    "CornflowerBlue": "#6495ED", "Cornsilk": "#FFF8DC", "Crimson": "#DC143C",
    "DarkBlue": "#00008B", "DarkCyan": "#008B8B", "DarkGoldenRod": "#B8860B",
    "DarkGray": "#A9A9A9", "DarkGrey": "#A9A9A9", "DarkGreen": "#006400",
    # svgnames examples (often loaded with xcolor)
    "Green": "#008000", "Blue": "#0000FF", # Note: some names might overlap if multiple color sets are used
}

class LatexToJsonConverter:
    def __init__(self, latex_filepath, schema_filepath="document_schema.json"):
        self.latex_filepath = latex_filepath
        self.schema_filepath = schema_filepath
        self.latex_content = ""
        self.base_dir = os.path.dirname(os.path.abspath(latex_filepath))
        self.json_output = self._get_default_json()
        self.macros = {}
        self.defined_colors = LATEX_COLOR_TO_HEX.copy()
        self.graphicspath = ["./", ""] # Default: current dir and root of project
        self.schema = self._load_schema()
        self.current_text_width_inches = 6.5 # Default assumption for \textwidth, \linewidth

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
                "title": "Untitled Document",
                "author": "Unknown Author",
                "subject": "",
                "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            "template_path": "",
            "page_layout": {
                "orientation": "portrait",
                "margins": { "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0 }
            },
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
            print("JSON Validation Error:")
            print(f"  Message: {e.message}")
            print(f"  Path: {list(e.path)}")
            print(f"  Schema Path: {list(e.schema_path)}")
            # To see the problematic data:
            # current = e.instance
            # for key in e.path:
            #     try:
            #         current = current[key]
            #     except (KeyError, TypeError, IndexError):
            #         break
            # print(f"  Problematic instance segment: {current}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during JSON validation: {e}")
            return False

    def _clean_latex_text_segment(self, text):
        text = text.replace(r"~", " ")
        text = text.replace(r"\'e", "é").replace(r"\'a", "á") # Add more common accents
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
            name = name.strip() # Ensure no leading/trailing spaces in color name
            if model == "HTML":
                if re.match(r"^[0-9A-Fa-f]{6}$", spec):
                    self.defined_colors[name] = f"#{spec.upper()}"
            elif model == "rgb":
                try:
                    r, g, b = [float(x.strip()) for x in spec.split(',')]
                    r_hex = format(min(255, int(r * 255)), '02X')
                    g_hex = format(min(255, int(g * 255)), '02X')
                    b_hex = format(min(255, int(b * 255)), '02X')
                    self.defined_colors[name] = f"#{r_hex}{g_hex}{b_hex}"
                except ValueError:
                    print(f"Warning: Could not parse rgb color spec '{spec}' for color '{name}'.")

    def _expand_macros(self, text, depth=0):
        if depth > 10: return text
        original_text = text
        for cmd, replacement in self.macros.items():
            escaped_cmd = re.escape(cmd)
            try:
                text = re.sub(r"\\" + escaped_cmd + r"(?!\w)", lambda m: replacement, text)
            except re.error:
                text = text.replace(f"\\{cmd}", replacement)

        if text != original_text:
            return self._expand_macros(text, depth + 1)
        return text

    def _parse_preamble(self, preamble_text):
        title_str_for_content = None
        title_match = re.search(r"\\title\{(.*?)\}", preamble_text, re.DOTALL)
        if title_match:
            title_str_for_content = self._strip_latex_commands(self._expand_macros(title_match.group(1).strip()))
            self.json_output["properties"]["title"] = title_str_for_content
        
        pdftitle_match = re.search(r"pdftitle=\{(.*?)\}", preamble_text, re.DOTALL)
        if pdftitle_match and not self.json_output["properties"].get("title"):
             self.json_output["properties"]["title"] = self._strip_latex_commands(self._expand_macros(pdftitle_match.group(1).strip()))

        author_match = re.search(r"\\author\{(.*?)\}", preamble_text, re.DOTALL)
        if author_match:
            self.json_output["properties"]["author"] = self._strip_latex_commands(self._expand_macros(author_match.group(1).strip()))

        # Add title as a "title_paragraph" to content if found from \title
        if title_str_for_content:
             # Ensure content array exists
            if "content" not in self.json_output: self.json_output["content"] = []
            self.json_output["content"].append({
                "type": "title_paragraph",
                "content": [{"type": "text", "text": title_str_for_content}]
            })

        documentclass_match = re.search(r"\\documentclass\[(.*?)\]", preamble_text)
        page_width_inches = 8.5 # Default Letter
        if documentclass_match:
            options = documentclass_match.group(1)
            if "landscape" in options:
                self.json_output["page_layout"]["orientation"] = "landscape"
            if "a4paper" in options: page_width_inches = 8.27
            # Add other paper sizes if needed

        geometry_match = re.search(r"\\geometry\{(.*?)\}", preamble_text)
        if geometry_match:
            margins_str = geometry_match.group(1)
            margins_map = self.json_output["page_layout"].setdefault("margins", {})
            for m_type in ["top", "bottom", "left", "right", "margin"]:
                m_match = re.search(fr"{m_type}\s*=\s*([\d.]+)\s*(in|cm|mm|pt)?", margins_str)
                if m_match:
                    val = float(m_match.group(1))
                    unit = m_match.group(2)
                    if unit == "cm": val /= 2.54
                    elif unit == "mm": val /= 25.4
                    elif unit == "pt": val /= 72.0
                    
                    if m_type == "margin":
                        for k_margin in ["top", "bottom", "left", "right"]:
                            margins_map[k_margin] = round(val, 2)
                    else:
                        margins_map[m_type] = round(val, 2)
            
            current_page_width = page_width_inches
            if self.json_output["page_layout"]["orientation"] == "landscape":
                current_page_width = 11.69 if "a4paper" in (documentclass_match.group(1) if documentclass_match else "") else 11.0
            
            left_margin = margins_map.get("left", 1.0)
            right_margin = margins_map.get("right", 1.0)
            self.current_text_width_inches = max(0.1, current_page_width - left_margin - right_margin)

        graphicspath_match = re.search(r"\\graphicspath\{\s*\{(.*?)\}\s*\}", preamble_text, re.DOTALL)
        if graphicspath_match:
            paths_str = graphicspath_match.group(1).strip()
            self.graphicspath = [p.strip() for p in paths_str.split("}{") if p.strip()]

    def _strip_latex_commands(self, text, keep_content=True):
        text = str(text)
        for _ in range(3):
            prev_text = text
            text = re.sub(r"\\[a-zA-Z@]+(?:\[[^\]]*\])?\{(.*?)\}", r"\1" if keep_content else "", text)
            text = re.sub(r"\\[a-zA-Z@]+", "", text)
            if text == prev_text: break
        text = text.replace("{", "").replace("}", "")
        return self._clean_latex_text_segment(text.strip())

    def _parse_inline_text_to_content_items(self, latex_string):
        content_items = []
        latex_string = self._expand_macros(latex_string)

        def generate_runs(text_segment, current_formatting):
            runs = []
            last_pos = 0

            inline_pattern = re.compile(
                r"(\\textbf\{(.*?)\})" +  # Alt 1: Grp 1 (full), Grp 2 (content)
                r"|(\\textit\{(.*?)\})" + # Alt 2: Grp 3 (full), Grp 4 (content)
                r"|(\\emph\{(.*?)\})" +  # Alt 3: Grp 5 (full), Grp 6 (content)
                r"|(\\underline\{(.*?)\})" + # Alt 4: Grp 7 (full), Grp 8 (content)
                r"|(\\texttt\{(.*?)\})" + # Alt 5: Grp 9 (full), Grp 10 (content)
                r"|(\\textcolor\{([a-zA-Z0-9_]+)\}\{(.*?)\})" +  # Alt 6: Grp 11 (full), Grp 12 (color), Grp 13 (content)
                r"|(\{\s*\\color\{([a-zA-Z0-9_]+)\}(.*?)\})" +  # Alt 7: Grp 14 (full), Grp 15 (color), Grp 16 (content)
                r"|(\\url\{(.*?)\})" + # Alt 8: Grp 17 (full), Grp 18 (content)
                r"|(\\href\{[^}]*\}\{(.*?)\})" +  # Alt 9: Grp 19 (full), Grp 20 (content)
                # Alt 10: Grp 21 (full), Grp 22 (opt_arg), Grp 23 (key). Note: (?:cite...) is non-capturing for the command name itself.
                r"|(\\(?:cite|citep|citet|citeauthor)(?:\[(.*?)\])?\{(.*?)\})" +
                r"|(\\[a-zA-Z@]+)"  # Alt 11: Grp 24 (cmd_text)
            , re.DOTALL)

            for match in inline_pattern.finditer(text_segment):
                start, end = match.span()
                
                if start > last_pos:
                    plain_text = self._clean_latex_text_segment(text_segment[last_pos:start])
                    if plain_text:
                        runs.append({"type": "text", "text": plain_text, "formatting": current_formatting.copy() if current_formatting else {}})
                
                new_formatting = current_formatting.copy()
                content_to_recurse = ""

                if match.group(1): # \textbf 
                    new_formatting["bold"] = True
                    content_to_recurse = match.group(2)
                elif match.group(3): # \textit 
                    new_formatting["italic"] = True
                    content_to_recurse = match.group(4)
                elif match.group(5): # \emph
                    new_formatting["italic"] = True
                    content_to_recurse = match.group(6)
                elif match.group(7): # \underline
                    new_formatting["underline"] = True
                    content_to_recurse = match.group(8)
                elif match.group(9): # \texttt
                    new_formatting["font_name"] = "Courier New" # Example monospace
                    content_to_recurse = match.group(10)
                elif match.group(11): # \textcolor
                    color_name = match.group(12) 
                    hex_color = self.defined_colors.get(color_name)
                    if hex_color: new_formatting["color"] = hex_color
                    else: print(f"Warning: Undefined color '{color_name}' used in textcolor.")
                    content_to_recurse = match.group(13) 
                elif match.group(14): # {\color ...}
                    color_name = match.group(15) 
                    hex_color = self.defined_colors.get(color_name)
                    if hex_color: new_formatting["color"] = hex_color
                    else: print(f"Warning: Undefined color '{color_name}' used in color group.")
                    content_to_recurse = match.group(16) 
                elif match.group(17): # \url
                    url_content = self._clean_latex_text_segment(match.group(18)) 
                    runs.append({"type": "text", "text": url_content, "formatting": current_formatting.copy() if current_formatting else {}})
                elif match.group(19): # \href
                    display_text = self._clean_latex_text_segment(match.group(20)) 
                    runs.append({"type": "text", "text": display_text, "formatting": current_formatting.copy() if current_formatting else {}})
                elif match.group(21): # Citation
                    key_text = match.group(23) # Content of {...} (key)
                    # opt_arg_text = match.group(22) # Content of [...] (optional argument)
                    runs.append({
                        "type": "citation",
                        "display_text": f"[{key_text}]", # Placeholder display text
                        "field_data": {"key": key_text, "latex_command": match.group(21)} # Minimal field_data
                    })
                elif match.group(24): # Other command (\\[a-zA-Z@]+)
                    # print(f"Stripping/ignoring command: {match.group(24)}") # For debugging
                    pass 
                else: # Should not be reached if regex is exhaustive for commands and text is handled outside
                    unhandled_text = self._clean_latex_text_segment(match.group(0))
                    if unhandled_text:
                         runs.append({"type": "text", "text": f"[Unhandled Regex M.: {unhandled_text}]", "formatting": current_formatting.copy() if current_formatting else {}})

                if content_to_recurse:
                    runs.extend(generate_runs(content_to_recurse, new_formatting))
                
                last_pos = end
            
            if last_pos < len(text_segment):
                plain_text = self._clean_latex_text_segment(text_segment[last_pos:])
                if plain_text:
                    runs.append({"type": "text", "text": plain_text, "formatting": current_formatting.copy() if current_formatting else {}})
            
            return runs

        raw_items = generate_runs(latex_string, {})
        
        merged_items = []
        if raw_items:
            for item in raw_items:
                if item["type"] == "text":
                    if "text" not in item: item["text"] = ""
                    if "formatting" in item and not item["formatting"]: # Remove empty formatting dict
                        del item["formatting"]
                
                if merged_items and \
                   merged_items[-1]["type"] == "text" and item["type"] == "text" and \
                   merged_items[-1].get("formatting") == item.get("formatting"):
                    merged_items[-1]["text"] += item["text"]
                elif item.get("text", "").strip() or item["type"] != "text":
                    merged_items.append(item)
        
        return [item for item in merged_items if item.get("text", "").strip() or item.get("type") != "text"]


    def _find_image_path(self, image_name):
        if os.path.isabs(image_name) and os.path.exists(image_name):
            return image_name
        
        for prefix in [""] + self.graphicspath:
            current_prefix_path = os.path.join(self.base_dir, prefix)
            path_to_check = os.path.normpath(os.path.join(current_prefix_path, image_name))
            if os.path.exists(path_to_check):
                return path_to_check
        print(f"Warning: Image '{image_name}' not found with graphicspaths: {self.graphicspath} relative to {self.base_dir}")
        return image_name

    def _parse_latex_dimension(self, dim_str):
        if not dim_str: return None
        dim_str = self._expand_macros(dim_str) # Expand if dimension is a macro
        match = re.match(r"([\d.]+)\s*(in|cm|mm|pt|em|ex|\\textwidth|\\linewidth)?", dim_str)
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            if unit == "in": return val
            if unit == "cm": return val / 2.54
            if unit == "mm": return val / 25.4
            if unit == "pt": return val / 72.0
            if unit in ["\\textwidth", "\\linewidth"]: return val * self.current_text_width_inches
            return val / 72.0 # Default to points
        return None

    def _parse_body(self, body_text_raw):
        body_text_cleaned = re.sub(r"(?<!\\)%.*", "", body_text_raw)
        body_text_cleaned = re.sub(r"%TC:ignore.*?%TC:endignore", "", body_text_cleaned, flags=re.DOTALL)

        block_pattern = re.compile(
            r"\\(section|subsection|subsubsection)(?:\[(.*?)\])?\{(.*?)\}" 
            r"|\\begin\{(figure|table|itemize|enumerate|quotation|verbatim|longtable|tabularx|tabular|subcaption|subfigure)\}(.*?)\\end\{\4\}" 
            r"|\\(newpage|clearpage)" 
            r"|\\(printbibliography|bibliography\{(.*?)\})" 
            , re.DOTALL
        )

        current_pos = 0
        while current_pos < len(body_text_cleaned):
            match = block_pattern.search(body_text_cleaned, current_pos)
            
            text_before_match_raw = ""
            if not match:
                text_before_match_raw = body_text_cleaned[current_pos:]
                current_pos = len(body_text_cleaned) 
            else:
                text_before_match_raw = body_text_cleaned[current_pos:match.start()]
                current_pos = match.end()

            if text_before_match_raw.strip():
                paragraphs_latex = re.split(r'\n\s*\n+', text_before_match_raw.strip())
                for para_latex in paragraphs_latex:
                    if para_latex.strip():
                        para_content_items = self._parse_inline_text_to_content_items(para_latex.strip())
                        if para_content_items:
                            self.json_output["content"].append({
                                "type": "normal",
                                "content": para_content_items
                            })
            if not match: break

            if match.group(1): # Section
                sec_type_str, sec_title_raw = match.group(1), match.group(3).strip()
                heading_type = f"heading{ {'section': 1, 'subsection': 2, 'subsubsection': 3}.get(sec_type_str, 1) }"
                sec_title_items = self._parse_inline_text_to_content_items(sec_title_raw)
                if sec_title_items:
                    self.json_output["content"].append({"type": heading_type, "content": sec_title_items})

            elif match.group(4): # Environment
                env_name, env_content_raw = match.group(4), match.group(5)

                if env_name == "figure":
                    img_match = re.search(r"\\includegraphics(?:\[(.*?)\])?\{(.*?)\}", env_content_raw, re.DOTALL)
                    caption_match = re.search(r"\\caption\{(.*?)\}", env_content_raw, re.DOTALL)
                    if img_match:
                        img_opts_str, img_path_raw = img_match.group(1), img_match.group(2)
                        image_item = {
                            "type": "image",
                            "path": self._find_image_path(self._expand_macros(img_path_raw)),
                            "preserve_aspect_ratio": True
                        }
                        width_val, height_val = None, None
                        if img_opts_str:
                            img_opts_expanded = self._expand_macros(img_opts_str)
                            w_m = re.search(r"width\s*=\s*([^,\]]+)", img_opts_expanded)
                            if w_m: width_val = self._parse_latex_dimension(w_m.group(1).strip())
                            h_m = re.search(r"height\s*=\s*([^,\]]+)", img_opts_expanded)
                            if h_m: height_val = self._parse_latex_dimension(h_m.group(1).strip())
                        
                        if width_val is not None: image_item["width_inches"] = round(max(0.1, width_val), 2)
                        if height_val is not None: image_item["height_inches"] = round(max(0.1, height_val), 2)
                        
                        if caption_match:
                            image_item["caption"] = self._strip_latex_commands(caption_match.group(1).strip())
                        
                        self.json_output["content"].append({"type": "normal", "content": [image_item]})
                
                elif env_name in ["subfigure", "subcaption"]: pass

                elif env_name in ["itemize", "enumerate"]:
                    list_obj = {
                        "type": "list",
                        "list_type": "bullet" if env_name == "itemize" else "number",
                        "level": 0, "items": []
                    }
                    item_matches = re.finditer(r"\\item(?:\s+|\[.*?\]\s*)(.*?)(?=\\item|\\end\{" + env_name + r"\}|\Z)", env_content_raw, re.DOTALL | re.IGNORECASE)
                    for item_match in item_matches:
                        item_content_raw = item_match.group(1).strip()
                        if not item_content_raw: continue
                        parsed_item_runs = self._parse_inline_text_to_content_items(item_content_raw)
                        if not parsed_item_runs: continue

                        if len(parsed_item_runs) == 1 and parsed_item_runs[0]["type"] == "text":
                            list_item_obj = {"text": parsed_item_runs[0]["text"]}
                            if "formatting" in parsed_item_runs[0] and parsed_item_runs[0]["formatting"]:
                                list_item_obj["formatting"] = parsed_item_runs[0]["formatting"]
                            list_obj["items"].append(list_item_obj)
                        else:
                            full_text = "".join(run.get("text", "") for run in parsed_item_runs if run["type"] == "text")
                            if not full_text and parsed_item_runs: full_text = f"[Complex: {parsed_item_runs[0]['type']}]"
                            list_obj["items"].append({"text": self._strip_latex_commands(full_text)})
                    if list_obj["items"]: self.json_output["content"].append(list_obj)
                
                elif env_name == "quotation":
                    quote_items = self._parse_inline_text_to_content_items(env_content_raw.strip())
                    if quote_items:
                        self.json_output["content"].append({
                            "type": "normal", 
                            "formatting": {"left_indent": 0.5, "right_indent": 0.5}, 
                            "content": quote_items
                        })
                
                elif env_name == "verbatim":
                     self.json_output["content"].append({
                        "type": "normal", 
                        "content": [{"type": "text", "text": env_content_raw.strip(), "formatting": {"font_name": "Courier New"}}]
                    })

                elif env_name in ["table", "longtable", "tabularx", "tabular"]:
                    table_obj = {"type": "table", "data": []}
                    rows_latex = env_content_raw.strip().split("\\\\")
                    for row_latex in rows_latex:
                        row_latex_clean = row_latex.strip()
                        if not row_latex_clean or row_latex_clean.startswith(("\\hline", "\\cline")): continue
                        cells_latex = row_latex_clean.split("&")
                        table_row_json = []
                        for cell_latex in cells_latex:
                            cell_items = self._parse_inline_text_to_content_items(cell_latex.strip())
                            if not cell_items: table_row_json.append("")
                            elif len(cell_items) == 1 and cell_items[0]["type"] == "text":
                                cell_obj = {"text": cell_items[0]["text"]}
                                if "formatting" in cell_items[0] and cell_items[0]["formatting"]:
                                    cell_obj["formatting"] = cell_items[0]["formatting"]
                                table_row_json.append(cell_obj)
                            else:
                                cell_text = "".join(ci.get("text", "") for ci in cell_items if ci["type"] == "text")
                                table_row_json.append(self._strip_latex_commands(cell_text))
                        if any(c for c in table_row_json if (isinstance(c, str) and c.strip()) or (isinstance(c, dict) and c.get("text","").strip())):
                            table_obj["data"].append(table_row_json)
                    if table_obj["data"]: self.json_output["content"].append(table_obj)

            elif match.group(6): # Page break
                self.json_output["content"].append({"type": "page_break"})

            elif match.group(7): # Bibliography
                bib_field_data = {}
                if match.group(8): bib_field_data["source_file"] = self._expand_macros(match.group(8).strip())
                self.json_output["content"].append({
                    "type": "bibliography", "display_text": "References", "field_data": bib_field_data
                })
        
        # Final schema compliance check for content items
        final_content_list = []
        for content_block in self.json_output.get("content", []):
            is_block_valid = True
            if "type" not in content_block: is_block_valid = False
            
            if content_block.get("type") in ["normal", "heading1", "heading2", "heading3", "title_paragraph"]: # Paragraph types
                if "content" not in content_block: content_block["content"] = [] # Ensure content array
                valid_para_items = []
                for item in content_block.get("content", []):
                    if item.get("type") == "text":
                        if "text" not in item: item["text"] = ""
                    elif item.get("type") == "citation":
                        if "field_data" not in item: item["field_data"] = {}
                        if "display_text" not in item: item["display_text"] = ""
                    elif item.get("type") == "image":
                        if "path" not in item: item["path"] = "error_path.png"; is_block_valid = False # Path is required
                        if "preserve_aspect_ratio" not in item: item["preserve_aspect_ratio"] = True
                    # Add more content_item type checks if needed
                    valid_para_items.append(item)
                content_block["content"] = valid_para_items
            elif content_block.get("type") == "table":
                if "data" not in content_block: content_block["data"] = []; is_block_valid = False # Data is required
            elif content_block.get("type") == "list":
                if "items" not in content_block: content_block["items"] = []; is_block_valid = False # Items are required
                if "list_type" not in content_block: content_block["list_type"] = "bullet" # Default if missing
            
            if is_block_valid: final_content_list.append(content_block)
            else: print(f"Warning: Invalid content block removed: {content_block}")
        self.json_output["content"] = final_content_list


    def convert(self):
        try:
            with open(self.latex_filepath, 'r', encoding='utf-8') as f:
                self.latex_content = f.read()
        except FileNotFoundError:
            print(f"Error: File not found at {self.latex_filepath}")
            return None
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

        doc_env_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", self.latex_content, re.DOTALL)
        if not doc_env_match:
            print("Warning: Could not find document environment. Treating all content as body.")
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
            print("JSON output failed validation against the schema. Review warnings/errors.")
        
        return self.json_output

# --- Main execution ---
if __name__ == '__main__':
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
This is the first paragraph. It includes some \textbf{bold text} and some \textit{italic text}.
Here is a sentence with \important{very important information}.
And now, \textbf{\textit{bold and italic}}! Followed by \underline{underlined text}.
We can also have \texttt{monospace text}. A URL: \url{https://example.com}.
A citation \citep{cox_fish_2023, cox_fish_2023a}. Another one \citep{cox_fish_2023a}.

\subsection{Lists and Things}
An itemized list:
\begin{itemize}
    \item First simple item.
    \item Second item with \textbf{bold parts} and \textit{italic parts}.
    \item A \textcolor{Blue}{blue item}.
    \item {\color{Green}A green item using group syntax}.
\end{itemize}
A numbered list:
\begin{enumerate}
    \item Number one.
    \item Number two, also with \important{emphasis}.
\end{enumerate}

\section{Figures and Tables}
\begin{figure}[h!]
    \centering
    \includegraphics[width=0.5\textwidth, height=5cm]{test.JPG}
    \caption{This is a caption for the example image.}
    \label{fig:example}
\end{figure}

Here is a table:
\begin{tabular}{|l|c|r|}
\hline
Header 1 & Header 2 & Header 3 \\
\hline
Cell 1.1 & Cell 1.2 with \textbf{bold} & Cell 1.3 \\
Cell 2.1 & \textit{Cell 2.2 italic} & Cell 2.3 with \url{https://example.org} \\
\hline
\end{tabular}

\begin{quotation}
This is a quotation environment. It should be indented.
It can also contain \textbf{formatted text}.
\end{quotation}

\newpage
This is after a page break.

\printbibliography 

\end{document}
    """
    test_latex_file = "example_converter_input.tex"
    with open(test_latex_file, "w", encoding="utf-8") as f:
        f.write(example_latex_content)

    dummy_image_name = "example_image.png"
    if not os.path.exists(dummy_image_name):
        with open(dummy_image_name, "wb") as f: 
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\x99c`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82')

    # Ensure schema file exists for the test
    schema_filename = "document_schema.json"
    
    converter = LatexToJsonConverter(test_latex_file, schema_filepath=schema_filename)
    json_data = converter.convert()

    if json_data:
        output_json_file = "converted_latex_strict_v2.json"
        with open(output_json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        print(f"Conversion successful. Output written to {output_json_file}")
    else:
        print("Conversion failed or produced invalid JSON.")
