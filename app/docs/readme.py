"""Custom docs for the /readme PESUAuth endpoint."""

from app.docs.base import ApiDocs
from app.models import ResponseModel

readme_docs = ApiDocs(
    request_examples={},
    response_examples={
        308: {
            "description": "Redirect to the PESUAuth GitHub repository.",
            "content": {
                "text/html": {
                    "example": '<html><head><title>Redirecting...</title></head><body><a href="https://github.com/pesu-dev/auth">Redirect</a></body></html>'
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Internal Server Error. Please try again later.",
                    }
                }
            },
        },
    },
)
