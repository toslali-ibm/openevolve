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
# HYPOTHESIS-1: Using regex pattern matching on all structured elements will increase accuracy by finding more valid functions
# MECHANISM-1: Regex captures function signatures more precisely than string splitting, reducing false positives from partial matches
# EXPECT-1: accuracy > 0.76
# RESULT-1: PENDING

# HYPOTHESIS-2: Filtering out single-character and common word false positives will improve accuracy
# MECHANISM-2: Generic text like "a", "if", "or" get matched as functions, filtering these reduces noise
# EXPECT-2: accuracy > 0.78
# RESULT-2: PENDING

# HYPOTHESIS-3: Increasing search scope to 25 functions will improve completeness without sacrificing accuracy
# MECHANISM-3: More functions extracted means higher completeness, while quality filters maintain accuracy
# EXPECT-3: completeness > 0.36
# RESULT-3: PENDING

def scrape_api_docs(html_content: str) -> List[Dict[str, any]]:
    """
    Extract API documentation from HTML content.

    Args:
        html_content: Raw HTML content of a documentation page

    Returns:
        List of dictionaries containing function documentation
    """
    soup = BeautifulSoup(html_content, "html.parser")
    func_dict = {}  # Use dict to deduplicate by name
    
    # Regex pattern for function signatures: name followed by parentheses
    pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(([^)]*)\)')
    
    # Common words to filter out (not valid function names)
    invalid_names = {"the", "a", "an", "if", "or", "and", "is", "in", "to", "of", "for", "as", "at", "by"}

    # 1. Look for dt elements with sig class (highest priority - most structured)
    dt_blocks = soup.find_all("dt", class_="sig")
    for block in dt_blocks:
        sig_name = block.find(class_="sig-name")
        if sig_name:
            name = sig_name.get_text(strip=True)
            if is_valid_name(name, invalid_names):
                signature = block.get_text(strip=True)
                desc = get_description_from_sibling(block)
                
                func_dict[name] = {
                    "name": name,
                    "signature": signature,
                    "description": desc,
                    "parameters": extract_parameters(signature),
                }

    # 2. Use regex to find functions in structured elements
    for tag in soup.find_all(['code', 'pre', 'h2', 'h3', 'h4', 'div', 'span']):
        text = tag.get_text()
        for match in pattern.finditer(text):
            name = match.group(1)
            if is_valid_name(name, invalid_names) and name not in func_dict:
                sig = match.group(0)
                desc = get_description_from_sibling(tag)
                
                func_dict[name] = {
                    "name": name,
                    "signature": sig,
                    "description": desc,
                    "parameters": extract_parameters(sig),
                }
                
                if len(func_dict) >= 25:
                    break
        if len(func_dict) >= 25:
            break

    return list(func_dict.values())[:25]


def is_valid_name(name: str, invalid_names: set) -> bool:
    """Check if a name is valid for a function."""
    if not name or len(name) < 2:
        return False
    if name.lower() in invalid_names:
        return False
    # Must start with letter or underscore
    if not (name[0].isalpha() or name[0] == '_'):
        return False
    return True


def get_description_from_sibling(element) -> str:
    """Extract description from element's siblings."""
    # Try dd sibling (for dt elements)
    if element.name == "dt":
        dd = element.find_next_sibling("dd")
        if dd:
            text = dd.get_text(strip=True)
            if text and len(text) > 10:
                return text[:200]
    
    # Try next sibling paragraph or div
    next_elem = element.find_next_sibling()
    if next_elem and next_elem.name in ["p", "div"]:
        text = next_elem.get_text(strip=True)
        if text and len(text) > 10:
            return text[:200]
    
    # Try parent's next sibling
    if element.parent:
        next_elem = element.parent.find_next_sibling()
        if next_elem and next_elem.name in ["p", "div"]:
            text = next_elem.get_text(strip=True)
            if text and len(text) > 10:
                return text[:200]
    
    return "No description found"


def extract_parameters(signature: str) -> List[Dict[str, str]]:
    """Extract parameter information from a function signature."""
    params = []
    match = re.search(r"\((.*?)\)", signature)
    if match:
        param_string = match.group(1).strip()
        if param_string:
            # Split by comma
            param_parts = [p.strip() for p in param_string.split(",")]
            for part in param_parts:
                if not part or part in ["self", "cls", "...", "*", "**"]:
                    continue
                
                # Extract name (before : or =)
                name = re.split(r'[=:]', part)[0].strip()
                if not name or len(name) < 1:
                    continue
                
                # Extract type hint if present
                param_type = "unknown"
                if ":" in part:
                    type_match = re.search(r":\s*([^=]+)", part)
                    if type_match:
                        param_type = type_match.group(1).strip()
                
                # Extract default value if present
                default = None
                if "=" in part:
                    default = part.split("=")[-1].strip()
                
                params.append({
                    "name": name,
                    "type": param_type,
                    "default": default,
                    "description": "",
                })
    return params


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
        output.append(f"Description: {doc['description']}")

        if doc.get("parameters"):
            output.append("Parameters:")
            for param in doc["parameters"]:
                output.append(f"  - {param['name']}: {param.get('description', 'No description')}")

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