from app.constants import PESUAcademyConstants


def test_default_fields_is_list():
    assert isinstance(PESUAcademyConstants.DEFAULT_FIELDS, list)
    assert "prn" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "name" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "srn" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "program" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "branch" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "semester" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "section" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "email" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "phone" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "campus_code" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "campus" in PESUAcademyConstants.DEFAULT_FIELDS
