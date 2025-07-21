import re
import logging
import gh_md_to_html
from pathlib import Path

def convert_readme_to_html() -> str:
    """
    Read README.md, convert to HTML, and return the HTML string.
    """
    logging.info("Beginning conversion of README.md to HTML in memory...")

    # Read and preprocess README.md content
    readme_content = Path("README.md").read_text(encoding="utf-8").strip()
    readme_content = re.sub(r":\w+: ", "", readme_content)

    # Write a temporary markdown file for the converter
    temp_md = Path("README_tmp.md")
    temp_md.write_text(readme_content, encoding="utf-8")

    # Convert markdown to HTML
    html = gh_md_to_html.main(
        str(temp_md),
        enable_image_downloading=False,
        image_paths=None,
    ).strip()

    logging.info("README.md converted to HTML successfully in memory.")

    return html
