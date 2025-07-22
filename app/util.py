import re
import logging
from pathlib import Path
import gh_md_to_html

def convert_readme_to_html() -> str:
     
    """
    Convert the README.md file to HTML and save it as README.html so that it can be rendered on the home page.
    Read README.md, convert to HTML, and return the HTML string.
    """
    
    logging.info("Converting README.md to HTML...")

    # Read and clean the markdown content
    readme_md = Path("README.md").read_text(encoding="utf-8").strip()
    cleaned_md = re.sub(r":\w+: ", "", readme_md)

    # Convert markdown to HTML
    html_output = gh_md_to_html.main(
        cleaned_md,
        enable_image_downloading=False,
        image_paths=None,
        origin_type="string",  
    ).strip()

    logging.info("README.md converted to HTML successfully.")
    return html_output
