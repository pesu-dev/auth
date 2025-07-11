from app.constants import PESUAcademyConstants


def test_default_fields_is_list():
    assert isinstance(PESUAcademyConstants.DEFAULT_FIELDS, list)
    assert "prn" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "name" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "srn" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "program" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "branch_short_code" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "branch" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "semester" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "section" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "email" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "phone" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "campus_code" in PESUAcademyConstants.DEFAULT_FIELDS
    assert "campus" in PESUAcademyConstants.DEFAULT_FIELDS


def test_branch_short_code_map_contains_all_branches():
    expected_map = {
        "Computer Science and Engineering": "CSE",
        "Computer Science and Engineering (AI&ML)": "CSE (AI&ML)",
        "Electronics and Communication Engineering": "ECE",
        "Mechanical Engineering": "ME",
        "Electrical and Electronics Engineering": "EEE",
        "Civil Engineering": "CE",
        "Biotechnology": "BT",
        "Bachelor of Computer Applications": "BCA",
        "BA LLB": "BA LLB",
        "Psychology": "Psychology",
        "Bachelor of Business Administration": "BBA",
        "BBA LLB": "BBA LLB",
    }

    for branch, code in expected_map.items():
        assert branch in PESUAcademyConstants.BRANCH_SHORT_CODES, (
            f"Branch '{branch}' missing from constants."
        )
        assert PESUAcademyConstants.BRANCH_SHORT_CODES[branch] == code, (
            f"Branch '{branch}' short code mismatch."
        )

    unexpected_branches = set(PESUAcademyConstants.BRANCH_SHORT_CODES) - set(expected_map)
    assert not unexpected_branches, (
        f"Unexpected branches found in constants: {unexpected_branches}. Please update the test or constants."
    )
