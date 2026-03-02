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
# HYPOTHESIS-1: Searching for all dt elements (not just class=sig) will increase completeness by capturing functions in non-Sphinx documentation formats
# MECHANISM-1: Many docs use plain dt/dd pairs without the sig class, which our current dt filter misses entirely
# EXPECT-1: completeness > 0.40
# RESULT-1: REFUTED (actual=0.375)

# HYPOTHESIS-2: Looking for pre and samp tags will improve completeness by finding code examples in diverse documentation styles
# MECHANISM-2: Documentation often uses pre or samp tags for function signatures instead of code tags
# EXPECT-2: completeness > 0.38
# RESULT-2: REFUTED (actual=0.375)

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

    # 1. Look for dt elements (both with and without sig class)
    dt_blocks = soup.find_all("dt")
    for block in dt_blocks:
        text = block.get_text(strip=True)
        # Check if it looks like a function
        if "(" in text and ")" in text:
            name = text.split("(")[0].strip().split()[-1]  # Get last word before (
            functions.append({
                "name": name,
                "signature": text,
                "description": "No description found",
                "parameters": extract_parameters(text),
            })

    # 2. Look for code, pre, and samp blocks
    for tag in ["code", "pre", "samp"]:
        blocks = soup.find_all(tag)
        for block in blocks:
            text = block.get_text(strip=True)
            if "(" in text and ")" in text and len(text) < 300:  # Avoid large code blocks
                name = text.split("(")[0].strip().split()[-1]
                functions.append({
                    "name": name,
                    "signature": text,
                    "description": "No description found",
                    "parameters": extract_parameters(text),
                })

    # 3. Look for function signatures in headers (h2, h3, h4)
    for tag in ["h2", "h3", "h4"]:
        blocks = soup.find_all(tag)
        for block in blocks:
            text = block.get_text(strip=True)
            if "(" in text and ")" in text:
                name = text.split("(")[0].strip().split()[-1]
                functions.append({
                    "name": name,
                    "signature": text,
                    "description": "No description found",
                    "parameters": extract_parameters(text),
                })

    # 4. Look for class="function" or class="method" divs
    for cls in ["function", "method", "api"]:
        blocks = soup.find_all(class_=cls)
        for block in blocks:
            text = block.get_text(strip=True)
            if "(" in text and ")" in text:
                name = text.split("(")[0].strip().split()[-1]
                functions.append({
                    "name": name,
                    "signature": text[:200],  # Limit signature length
                    "description": "No description found",
                    "parameters": extract_parameters(text),
                })

    return functions


def extract_parameters(signature: str) -> List[Dict[str, str]]:
    """
    Extract parameter information from a function signature.

    Args:
        signature: Function signature string

    Returns:
        List of parameter dictionaries
    """
    params = []
    match = re.search(r"\((.*?)\)", signature)
    if match:
        param_string = match.group(1)
        if param_string and param_string.strip():
            # Split on comma but handle nested structures
            param_parts = re.split(r',(?![^(]*\))', param_string)
            for part in param_parts:
                part = part.strip()
                if part and part not in ['...', '*', '**']:
                    # Extract name, handling type annotations and defaults
                    name = part.split("=")[0].split(":")[0].strip()
                    name = name.lstrip('*').strip()
                    if name and name.isidentifier():
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