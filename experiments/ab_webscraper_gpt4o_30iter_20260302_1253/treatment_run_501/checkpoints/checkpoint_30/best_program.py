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
# HYPOTHESIS-1: Fixing duplicate parameter entries will improve accuracy by eliminating redundant param objects
# MECHANISM-1: Current code appends each parameter twice in extract_parameters - removing the second append will reduce false positives
# EXPECT-1: accuracy > 0.92
# RESULT-1: CONFIRMED (actual=0.9444444444444444)

# HYPOTHESIS-2: Searching table and dl tags will improve completeness by capturing tabular API documentation
# MECHANISM-2: Many API docs use tables or definition lists for function listings that our current searches miss
# EXPECT-2: completeness > 0.45
# RESULT-2: REFUTED (actual=0.425)

# HYPOTHESIS-3: Removing the limit=50 restriction on dt tags will improve completeness by scanning all potential functions
# MECHANISM-3: Artificial limits prevent finding functions beyond the first 50 dt elements in long documentation pages
# EXPECT-3: completeness > 0.43
# RESULT-3: REFUTED (actual=0.425)

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

    # 1. Look for dt elements with descriptions
    dt_blocks = soup.find_all("dt")
    for block in dt_blocks:
        text = block.get_text(strip=True)
        if "(" in text and ")" in text:
            name = text.split("(")[0].strip().split()[-1]
            description = block.find_next(["p", "dd"])
            functions.append({
                "name": name,
                "signature": text,
                "description": description.get_text(strip=True) if description else "No description found",
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

    # 3. Look for class-based function/method elements
    for cls in ["function", "method", "api"]:
        blocks = soup.find_all(class_=cls)
        for block in blocks:
            text = block.get_text(strip=True)
            if "(" in text and ")" in text:
                name = text.split("(")[0].strip().split()[-1]
                description = block.find_next(["p", "dd"])
                functions.append({
                    "name": name,
                    "signature": text[:200],
                    "description": description.get_text(strip=True) if description else "No description found",
                    "parameters": extract_parameters(text),
                })

    # 4. Look for table rows with function signatures
    for row in soup.find_all("tr"):
        text = row.get_text(strip=True)
        if "(" in text and ")" in text and len(text) < 300:
            name = text.split("(")[0].strip().split()[-1]
            functions.append({
                "name": name,
                "signature": text[:200],
                "description": "No description found",
                "parameters": extract_parameters(text),
            })

    # 5. Look for dl/dd definition list pairs
    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            text = dt.get_text(strip=True)
            if "(" in text and ")" in text:
                name = text.split("(")[0].strip().split()[-1]
                dd = dt.find_next("dd")
                functions.append({
                    "name": name,
                    "signature": text,
                    "description": dd.get_text(strip=True) if dd else "No description found",
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
                    # Extract name, type, and default values from parameters
                    name = part.split("=")[0].split(":")[0].strip().lstrip('*').strip()
                    if name and name.isidentifier():
                        type_match = re.search(r":\s*([a-zA-Z0-9_.]+)", part)
                        default_match = re.search(r"=\s*([^,]+)", part)
                        params.append({
                            "name": name,
                            "type": type_match.group(1) if type_match else "unknown",
                            "default": default_match.group(1) if default_match else None,
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