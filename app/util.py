import re
import logging
import gh_md_to_html

from app.models import RequestModel


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


def validate_input(data: dict) -> RequestModel:
    """
    Validate the input provided by the user

    Args:
        data (dict): The input data to validate. Should contain:
            - username: str - The user's SRN, PRN, email, or phone number
            - password: str - The user's password
            - profile: bool (optional) - Whether to fetch user profile
            - fields: List[str] (optional) - Profile fields to return

    Returns:
        RequestModel: The validated input data as a RequestModel instance.
    """
    logging.info(
        f"Validating input: {data.get('username')=}, password={'*****' if data.get('password') else None}, "
        f"profile={data.get('profile')}, fields={data.get('fields')}"
    )
    validated_data = RequestModel.model_validate(data)
    logging.info("Input validation successful. All parameters are valid.")
    return validated_data
