import re
import logging
import gh_md_to_html


def convert_readme_to_html():
    """
    Convert the README.md file to HTML and save it as README.html so that it can be rendered on the home page.
    """
    logging.info("Beginning conversion of README.md to HTML...")
    readme_content = open("README.md").read().strip()
    readme_content = re.sub(r":\w+: ", "", readme_content)
    with open("README_tmp.md", "w") as f:
        f.write(readme_content)
    html = gh_md_to_html.main("README_tmp.md").strip()
    with open("README.html", "w") as f:
        f.write(html)
    logging.info("README.md converted to HTML successfully.")
