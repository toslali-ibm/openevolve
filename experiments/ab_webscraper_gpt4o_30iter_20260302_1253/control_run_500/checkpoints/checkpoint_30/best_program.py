"""
Web scraper for extracting API documentation from HTML pages.

This initial implementation provides basic HTML parsing functionality
that will be evolved to handle complex documentation structures.

The LLM will have access to actual documentation pages through optillm's
readurls plugin, allowing it to understand the specific HTML structure
and improve the parsing logic accordingly.
"""

from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import re


# EVOLVE-BLOCK-START
def scrape_api_docs(html_content: str) -> List[Dict[str, any]]:
    """
    Extract API documentation from HTML content.

    Args:
        html_content: Raw HTML content of a documentation page

    Returns:
        List of dictionaries containing function documentation
    """
    soup = BeautifulSoup(html_content, "html.parser")
    functions = []

    seen = set()
    
    # 1. Look for dt/dd pairs (Sphinx-style docs) - functions, classes, and attributes
    for dt in soup.find_all("dt"):
        sig_text = dt.get_text(strip=True)
        # Accept both function signatures and class/attribute definitions
        if "(" in sig_text or sig_text.startswith("class ") or "=" in sig_text:
            dd = dt.find_next_sibling("dd")
            desc = ""
            if dd:
                # Get all paragraphs and dl elements in the dd for fuller description
                desc_parts = []
                for elem in dd.find_all(['p', 'dl'], recursive=False):
                    text = elem.get_text(strip=True)
                    if text:
                        desc_parts.append(text)
                desc = " ".join(desc_parts[:3])[:600]
                if not desc:
                    desc = dd.get_text(strip=True)[:600]
            
            name = sig_text.split("(")[0].strip()
            if "class " in name:
                name = name.replace("class ", "").strip()
            key = f"{name}|{sig_text}"
            if key not in seen:
                seen.add(key)
                functions.append({
                    "name": name,
                    "signature": sig_text,
                    "description": desc,
                    "parameters": extract_parameters(sig_text) if "(" in sig_text else [],
                    "return_type": extract_return_type(sig_text),
                })

    # 2. Look for headers with descriptions
    for tag in ["h1", "h2", "h3", "h4", "h5"]:
        for header in soup.find_all(tag):
            text = header.get_text(strip=True)
            if "(" in text or text.startswith("class "):
                # Get multiple paragraphs and code blocks for better description
                desc_parts = []
                next_elem = header.find_next_sibling()
                while next_elem and next_elem.name in ["p", "pre", "div"] and len(desc_parts) < 4:
                    desc_parts.append(next_elem.get_text(strip=True))
                    next_elem = next_elem.find_next_sibling()
                desc = " ".join(desc_parts)[:600]
                
                name = text.split("(")[0].strip()
                if "class " in name:
                    name = name.replace("class ", "").strip()
                key = f"{name}|{text}"
                if key not in seen:
                    seen.add(key)
                    functions.append({
                        "name": name,
                        "signature": text,
                        "description": desc,
                        "parameters": extract_parameters(text) if "(" in text else [],
                        "return_type": extract_return_type(text),
                    })

    # 3. Look for code/pre blocks with signatures
    for block in soup.find_all(["code", "pre"]):
        text = block.get_text(strip=True)
        if "(" in text or text.startswith("class ") or (text.count("=") == 1 and text.count("\n") == 0):
            parent = block.parent
            desc = ""
            if parent:
                # Look for description in following siblings
                desc_parts = []
                next_elem = parent.find_next_sibling()
                count = 0
                while next_elem and count < 3:
                    if next_elem.name in ["p", "div"]:
                        desc_parts.append(next_elem.get_text(strip=True))
                        count += 1
                    next_elem = next_elem.find_next_sibling()
                desc = " ".join(desc_parts)[:600]
            
            name = text.split("(")[0].strip()
            if "class " in name:
                name = name.replace("class ", "").strip()
            if "=" in name and "(" not in name:
                name = name.split("=")[0].strip()
            key = f"{name}|{text}"
            if key not in seen and name:
                seen.add(key)
                functions.append({
                    "name": name,
                    "signature": text,
                    "description": desc,
                    "parameters": extract_parameters(text) if "(" in text else [],
                    "return_type": extract_return_type(text),
                })

    return functions[:50]  # Increased limit to capture more


def extract_parameters(signature: str) -> List[Dict[str, str]]:
    """Extract parameter information from a function signature."""
    params = []
    match = re.search(r"\((.*?)\)", signature)
    if match:
        param_string = match.group(1).strip()
        if param_string:
            # Handle nested parentheses
            parts = []
            current = []
            depth = 0
            for char in param_string + ",":
                if char in "([{":
                    depth += 1
                    current.append(char)
                elif char in ")]}":
                    depth -= 1
                    current.append(char)
                elif char == "," and depth == 0:
                    parts.append("".join(current).strip())
                    current = []
                else:
                    current.append(char)
            
            for part in parts:
                if not part:
                    continue
                
                # Extract name, type, default
                name = part
                param_type = ""
                default = None
                
                if "=" in part:
                    name, default = part.split("=", 1)
                    default = default.strip()
                
                if ":" in name:
                    name, param_type = name.split(":", 1)
                    param_type = param_type.strip()
                
                name = name.strip().lstrip("*")
                
                if name:
                    params.append({
                        "name": name,
                        "type": param_type,
                        "default": default,
                        "description": "",
                    })
    return params


def extract_return_type(signature: str) -> str:
    """Extract return type from function signature."""
    # Look for -> return_type pattern
    match = re.search(r"->\s*([^:{\n]+?)(?:\s*[:{]|$)", signature)
    if match:
        ret_type = match.group(1).strip()
        # Clean up common trailing characters
        ret_type = ret_type.rstrip(",;")
        return ret_type
    return ""


def format_documentation(api_docs: List[Dict[str, any]]) -> str:
    """
    Format extracted documentation into a readable string.

    Args:
        api_docs: List of API documentation dictionaries

    Returns:
        Formatted documentation string
    """
    output = []
    for doc in api_docs:
        output.append(f"Function: {doc['name']}")
        output.append(f"Signature: {doc['signature']}")
        if doc.get("return_type"):
            output.append(f"Returns: {doc['return_type']}")
        output.append(f"Description: {doc['description']}")

        if doc.get("parameters"):
            output.append("Parameters:")
            for param in doc["parameters"]:
                param_info = param['name']
                if param.get('type'):
                    param_info += f" ({param['type']})"
                if param.get('default'):
                    param_info += f" = {param['default']}"
                output.append(f"  - {param_info}")

        output.append("")  # Empty line between functions

    return "\n".join(output)


# EVOLVE-BLOCK-END


# Example usage and test
if __name__ == "__main__":
    # Sample HTML for testing basic functionality
    sample_html = """
    <html>
    <body>
        <div class="function">
            <code>json.dumps(obj, indent=2)</code>
            <p>Serialize obj to a JSON formatted string.</p>
        </div>
        <div class="function">
            <code>json.loads(s)</code>
            <p>Deserialize s to a Python object.</p>
        </div>
    </body>
    </html>
    """

    docs = scrape_api_docs(sample_html)
    print(format_documentation(docs))
    print(f"\nExtracted {len(docs)} functions")
