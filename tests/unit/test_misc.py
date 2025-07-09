from app.pesu import PESUAcademy


def test_branch_to_short_code_known():
    short = PESUAcademy.map_branch_to_short_code("Computer Science and Engineering")
    assert short == "CSE"


def test_branch_to_short_code_unknown():
    short = PESUAcademy.map_branch_to_short_code("Astrophysics")
    assert short is None
