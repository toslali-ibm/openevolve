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
# HYPOTHESIS-1: Searching all text for function patterns will increase completeness by finding functions in diverse HTML structures
# MECHANISM-1: Many docs use plain text or non-standard tags; regex search of all text captures more functions than tag-specific searches
# EXPECT-1: completeness > 0.38
# RESULT-1: REFUTED (actual=0.375)

# HYPOTHESIS-2: Extracting descriptions from all nearby text nodes within 200 chars will improve completeness without hurting accuracy
# MECHANISM-2: Descriptions often appear in various tags near signatures; broad text extraction captures more context
# EXPECT-2: accuracy > 0.70
# RESULT-2: CONFIRMED (actual=0.8333333333333334)

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

    # Strategy: Find all function-like patterns in text, then extract context
    # Pattern: word_chars followed by parentheses
    pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(([^)]*)\)')
    
    # Search in structured elements first
    for tag in soup.find_all(['dt', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'div', 'span']):
        text = tag.get_text()
        for match in pattern.finditer(text):
            name = match.group(1)
            if name and len(name) > 1 and name not in seen:
                seen.add(name)
                sig = match.group(0)
                
                # Get description from surrounding context
                desc = get_description(tag, soup)
                
                functions.append({
                    "name": name,
                    "signature": sig,
                    "description": desc,
                    "parameters": extract_parameters(sig),
                })
                
                if len(functions) >= 25:
                    break
        if len(functions) >= 25:
            break
    
    return functions[:25]


def get_description(element, soup) -> str:
    """Extract description from element context."""
    # Try next sibling
    next_elem = element.find_next_sibling()
    if next_elem:
        text = next_elem.get_text(strip=True)
        if text and len(text) > 10:
            return text[:150]
    
    # Try parent's next sibling
    if element.parent:
        next_elem = element.parent.find_next_sibling()
        if next_elem:
            text = next_elem.get_text(strip=True)
            if text and len(text) > 10:
                return text[:150]
    
    return "No description found"


def extract_parameters(signature: str) -> List[Dict[str, str]]:
    """Extract parameter information from a function signature."""
    params = []
    match = re.search(r"\((.*?)\)", signature)
    if match:
        param_string = match.group(1).strip()
        if param_string:
            # Simple split by comma
            for part in param_string.split(","):
                part = part.strip()
                if part and part not in ["self", "cls", "..."]:
                    # Extract name (before : or =)
                    name = re.split(r'[=:]', part)[0].strip()
                    if name:
                        params.append({
                            "name": name,
                            "type": "unknown",
                            "default": None,
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