from app.pesu import PESUAcademy


def test_default_fields_is_list():
    assert isinstance(PESUAcademy.DEFAULT_FIELDS, list)
    assert "prn" in PESUAcademy.DEFAULT_FIELDS
    assert "name" in PESUAcademy.DEFAULT_FIELDS
    assert "srn" in PESUAcademy.DEFAULT_FIELDS
    assert "program" in PESUAcademy.DEFAULT_FIELDS
    assert "branch" in PESUAcademy.DEFAULT_FIELDS
    assert "semester" in PESUAcademy.DEFAULT_FIELDS
    assert "section" in PESUAcademy.DEFAULT_FIELDS
    assert "email" in PESUAcademy.DEFAULT_FIELDS
    assert "phone" in PESUAcademy.DEFAULT_FIELDS
    assert "campus_code" in PESUAcademy.DEFAULT_FIELDS
    assert "campus" in PESUAcademy.DEFAULT_FIELDS
