from app.models.request import RequestModel
import pytest
from app.constants import PESUAcademyConstants



def test_requestmodel_value_error_username():
    with pytest.raises(ValueError) as exc_info:
        RequestModel.validate_username('')
        
        
    assert str(exc_info.value) == "Username cannot be empty."
    
def test_requestmodel_value_error_password():
    with pytest.raises(ValueError) as exc_info:
        RequestModel.validate_password('')
        
        
    assert str(exc_info.value) == "Password cannot be empty."

def test_requestmodel_validate_field():
    with pytest.raises(ValueError) as exc_info:
        v=['name','prn','gender','height','campus']
        RequestModel.validate_fields(v)
        
        
    assert str(exc_info.value) ==  f"Invalid fields: gender, height. Valid fields are: {', '.join(PESUAcademyConstants.DEFAULT_FIELDS)}"


