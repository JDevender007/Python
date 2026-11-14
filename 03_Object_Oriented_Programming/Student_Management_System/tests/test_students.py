"""Tests for Student_Management_System: scales, courses, transcripts, the file."""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from students import (                                    # noqa: E402
    DATA_FILE,
    DEPARTMENTS,
    HUNDREDTHS,
    LEGACY_CGPA,
    LEGACY_CLAIMS,
    LEGACY_IMPORT,
    LEGACY_SEARCH,
    LEGACY_SORT,
    LEGACY_VALIDATOR,
    MAX_CREDITS_PER_COURSE,
    SCALES,
    Course,
    DuplicateStudent,
    FourPointScale,
    GradeScale,
    NoCourses,
    Registry,
    Student,
    StudentError,
    TenPointScale,
    Transcript,
    UnknownCourse,
    UnknownStudent,
    check_whole,
    check_year,
    format_points,
    legacy_gpa,
    legacy_record,
    legacy_rows,
    legacy_top,
    load_registry,
    normalise_department,
    normalise_email,
    normalise_phone,
    normalise_roll,
    round_half_up,
    run_demo,
    save_registry,
    scale_named,
)


def a_transcript(*courses, scale=None) -> Transcript:
    sheet = Transcript(scale)
    for code, credits, grade in courses or (("CS301", 4, "A"),):
        sheet.add(Course(code, f"Course {code}", credits, grade))
    return sheet


def a_student(roll="CS-2023-014", name="Asha Rao",
              department="Computer Science", year=3,
              email="asha.rao@example.edu", phone="9876543210",
              sheet=None) -> Student:
    return Student(roll, name, department, year, email, phone,
                   a_transcript() if sheet is None else sheet)


def a_registry(*students) -> Registry:
    registry = Registry("Test Institute")
    for student in students or (a_student(),):
        registry.add(student)
    return registry


# --------------------------------------------------------------------------- #
# check_whole
# --------------------------------------------------------------------------- #
def test_check_whole_returns_the_number():
    assert check_whole(7) == 7


def test_check_whole_allows_zero():
    assert check_whole(0) == 0


def test_check_whole_refuses_a_float():
    with pytest.raises(StudentError, match="a count must be a whole number, "
                                          "got float"):
        check_whole(1.0)


def test_check_whole_refuses_a_bool():
    with pytest.raises(StudentError, match="got bool"):
        check_whole(True)


def test_check_whole_refuses_a_string():
    with pytest.raises(StudentError, match="got str"):
        check_whole("7")


def test_check_whole_refuses_a_negative_number():
    with pytest.raises(StudentError, match="a count must not be negative"):
        check_whole(-1)


def test_check_whole_uses_its_label():
    with pytest.raises(StudentError, match="credits must not be negative"):
        check_whole(-1, "credits")


# --------------------------------------------------------------------------- #
# round_half_up
# --------------------------------------------------------------------------- #
def test_round_half_up_rounds_a_half_up():
    assert round_half_up(3, 2) == 2


def test_round_half_up_rounds_just_below_down():
    assert round_half_up(4, 3) == 1


def test_round_half_up_leaves_an_exact_division():
    assert round_half_up(4, 2) == 2


def test_round_half_up_rounds_the_seeded_cgpas():
    assert round_half_up(12500, 14) == 893
    assert round_half_up(10800, 13) == 831
    assert round_half_up(9400, 13) == 723


def test_round_half_up_handles_a_negative_numerator():
    assert round_half_up(-3, 2) == -2


def test_round_half_up_refuses_a_zero_denominator():
    with pytest.raises(StudentError, match="denominator must be positive"):
        round_half_up(1, 0)


def test_round_half_up_refuses_a_negative_denominator():
    with pytest.raises(StudentError, match="denominator must be positive"):
        round_half_up(1, -2)


# --------------------------------------------------------------------------- #
# format_points
# --------------------------------------------------------------------------- #
def test_format_points_pins_a_cgpa():
    assert format_points(893) == "8.93"


def test_format_points_renders_zero():
    assert format_points(0) == "0.00"


def test_format_points_pads_the_fraction():
    assert format_points(5) == "0.05"


def test_format_points_renders_a_whole_point():
    assert format_points(1000) == "10.00"


def test_format_points_renders_a_negative_value():
    assert format_points(-125) == "-1.25"


def test_format_points_refuses_a_float():
    with pytest.raises(StudentError, match="integer number of hundredths"):
        format_points(8.5)


def test_format_points_refuses_a_bool():
    with pytest.raises(StudentError, match="integer number of hundredths"):
        format_points(True)


# --------------------------------------------------------------------------- #
# normalise_roll
# --------------------------------------------------------------------------- #
def test_a_roll_number_is_upper_cased():
    assert normalise_roll("cs-2023-014") == "CS-2023-014"


def test_a_roll_number_is_trimmed():
    assert normalise_roll("  CS-2023-014  ") == "CS-2023-014"


def test_a_roll_number_that_is_not_text_is_refused():
    with pytest.raises(StudentError, match="must be text, got int"):
        normalise_roll(2023014)


def test_an_empty_roll_number_is_refused():
    with pytest.raises(StudentError, match="must not be empty"):
        normalise_roll("   ")


def test_a_roll_without_dashes_is_refused():
    with pytest.raises(StudentError, match="expected DEPT-YEAR-SEQ"):
        normalise_roll("CS2023014")


def test_a_roll_with_four_parts_is_refused():
    with pytest.raises(StudentError, match="is not a roll number"):
        normalise_roll("CS-2023-014-01")


def test_a_roll_with_one_letter_is_refused():
    with pytest.raises(StudentError, match="2 to 4 letters"):
        normalise_roll("C-2023-014")


def test_a_roll_with_five_letters_is_refused():
    with pytest.raises(StudentError, match="2 to 4 letters"):
        normalise_roll("ABCDE-2023-014")


def test_a_roll_with_a_short_year_is_refused():
    with pytest.raises(StudentError, match="four digits for the year"):
        normalise_roll("CS-23-014")


def test_a_roll_with_a_short_serial_is_refused():
    with pytest.raises(StudentError, match="three digits at the end"):
        normalise_roll("CS-2023-14")


def test_a_roll_with_a_letter_in_the_serial_is_refused():
    with pytest.raises(StudentError, match="three digits at the end"):
        normalise_roll("CS-2023-01A")


# --------------------------------------------------------------------------- #
# normalise_email
# --------------------------------------------------------------------------- #
def test_an_email_is_lower_cased():
    assert normalise_email("Asha.Rao@Example.EDU") == "asha.rao@example.edu"


def test_an_email_is_trimmed():
    assert normalise_email("  a@b.edu  ") == "a@b.edu"


def test_an_email_that_is_not_text_is_refused():
    with pytest.raises(StudentError, match="must be text, got int"):
        normalise_email(7)


def test_an_empty_email_is_refused():
    with pytest.raises(StudentError, match="must not be empty"):
        normalise_email("  ")


def test_an_email_needs_exactly_one_at_sign():
    with pytest.raises(StudentError, match="exactly one '@'"):
        normalise_email("a@@b.edu")


def test_an_email_needs_a_local_part():
    with pytest.raises(StudentError, match="nothing before the '@'"):
        normalise_email("@example.edu")


def test_an_email_needs_a_dotted_domain():
    with pytest.raises(StudentError, match="domain with a dot"):
        normalise_email("a@example")


def test_an_email_cannot_end_its_domain_with_a_dot():
    with pytest.raises(StudentError, match="is not an email address"):
        normalise_email("a@example.edu.")


def test_an_email_cannot_hold_a_space():
    with pytest.raises(StudentError, match="is not an email address"):
        normalise_email("a b@example.edu")


def test_an_email_cannot_hold_a_bracket_before_the_at():
    with pytest.raises(StudentError, match="before the '@'"):
        normalise_email("a(b)@example.edu")


def test_an_email_cannot_hold_an_underscore_in_the_domain():
    with pytest.raises(StudentError, match="after the '@'"):
        normalise_email("a@exam_ple.edu")


# --------------------------------------------------------------------------- #
# normalise_phone
# --------------------------------------------------------------------------- #
def test_a_phone_number_keeps_ten_digits():
    assert normalise_phone("9876543210") == "9876543210"


def test_a_phone_number_drops_spaces_and_hyphens():
    assert normalise_phone(" 98765-43210 ") == "9876543210"


def test_a_phone_number_that_is_not_text_is_refused():
    with pytest.raises(StudentError, match="must be text, got int"):
        normalise_phone(9876543210)


def test_an_empty_phone_number_is_refused():
    with pytest.raises(StudentError, match="must not be empty"):
        normalise_phone("   ")


def test_a_short_phone_number_is_refused():
    with pytest.raises(StudentError, match="has 9 digits"):
        normalise_phone("987654321")


def test_a_long_phone_number_is_refused():
    with pytest.raises(StudentError, match="has 11 digits"):
        normalise_phone("98765432100")


def test_a_phone_number_with_letters_is_refused():
    with pytest.raises(StudentError, match="nothing but spaces or hyphens"):
        normalise_phone("98765abcde")


def test_a_phone_number_with_a_country_code_is_refused():
    with pytest.raises(StudentError, match="nothing but spaces or hyphens"):
        normalise_phone("+919876543210")


# --------------------------------------------------------------------------- #
# normalise_department / check_year
# --------------------------------------------------------------------------- #
def test_a_department_is_canonicalised():
    assert normalise_department("computer science") == "Computer Science"


def test_a_department_tolerates_extra_spaces():
    assert normalise_department("  computer   science ") == \
        "Computer Science"


def test_a_department_keeps_its_casing():
    assert normalise_department("CIVIL") == "Civil"


def test_an_unknown_department_is_refused():
    with pytest.raises(StudentError, match="is not a department"):
        normalise_department("Law")


def test_a_department_that_is_not_text_is_refused():
    with pytest.raises(StudentError, match="must be text, got int"):
        normalise_department(7)


def test_the_department_list_is_pinned():
    assert DEPARTMENTS == ("Civil", "Computer Science", "Electronics",
                           "Mechanical")


def test_a_year_of_one_is_accepted():
    assert check_year(1) == 1


def test_a_year_of_four_is_accepted():
    assert check_year(4) == 4


def test_a_year_of_zero_is_refused():
    with pytest.raises(StudentError, match="must be 1, 2, 3 or 4, got 0"):
        check_year(0)


def test_a_year_of_five_is_refused():
    with pytest.raises(StudentError, match="must be 1, 2, 3 or 4, got 5"):
        check_year(5)


def test_a_year_that_is_text_is_refused():
    with pytest.raises(StudentError, match="the year must be a whole number"):
        check_year("3")


# --------------------------------------------------------------------------- #
# GradeScale: the abstract base class
# --------------------------------------------------------------------------- #
def test_the_base_class_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        GradeScale()


def test_the_base_class_names_both_abstract_members():
    with pytest.raises(TypeError) as caught:
        GradeScale()
    assert "levels" in str(caught.value) and "name" in str(caught.value)


def test_a_subclass_without_levels_cannot_be_instantiated():
    half = type("HalfScale", (GradeScale,), {"name": "half"})
    with pytest.raises(TypeError, match="levels"):
        half()


def test_a_concrete_property_for_levels_is_refused():
    with pytest.raises(TypeError, match="must be a dict, not a property"):
        type("LazyScale", (GradeScale,),
             {"name": "lazy", "levels": property(lambda self: {"A": 100})})


def test_a_redeclared_abstract_levels_leaves_the_class_abstract():
    from abc import abstractmethod
    lazy = type("LazyScale", (GradeScale,),
                {"name": "lazy",
                 "levels": property(abstractmethod(lambda self: {"A": 100}))})
    with pytest.raises(TypeError, match="levels"):
        lazy()


def test_an_empty_level_table_is_refused_at_class_creation():
    with pytest.raises(TypeError, match="non-empty dict"):
        type("EmptyScale", (GradeScale,), {"name": "empty", "levels": {}})


def test_a_non_dict_level_table_is_refused():
    with pytest.raises(TypeError, match="non-empty dict"):
        type("ListScale", (GradeScale,), {"name": "list", "levels": [("A", 1)]})


def test_a_lower_case_grade_name_is_refused():
    with pytest.raises(TypeError, match="upper-case grade name"):
        type("LowerScale", (GradeScale,),
             {"name": "lower", "levels": {"a": 100}})


def test_a_float_grade_point_is_refused():
    with pytest.raises(TypeError, match="whole number of hundredths"):
        type("FloatScale", (GradeScale,),
             {"name": "floats", "levels": {"A": 9.5}})


def test_a_bool_grade_point_is_refused():
    with pytest.raises(TypeError, match="whole number of hundredths"):
        type("BoolScale", (GradeScale,),
             {"name": "bools", "levels": {"A": True}})


def test_a_negative_grade_point_is_refused():
    with pytest.raises(TypeError, match="negative number"):
        type("NegativeScale", (GradeScale,),
             {"name": "negative", "levels": {"A": -100}})


def test_a_scale_worth_nothing_is_refused():
    with pytest.raises(TypeError, match="worth something"):
        type("ZeroScale", (GradeScale,),
             {"name": "zero", "levels": {"A": 0, "F": 0}})


# --------------------------------------------------------------------------- #
# The two concrete scales
# --------------------------------------------------------------------------- #
def test_the_ten_point_scale_is_a_grade_scale():
    assert isinstance(TenPointScale(), GradeScale)


def test_the_four_point_scale_is_a_grade_scale():
    assert isinstance(FourPointScale(), GradeScale)


def test_the_ten_point_scale_has_eight_grades():
    assert len(TenPointScale()) == 8


def test_the_four_point_scale_has_five_grades():
    assert len(FourPointScale()) == 5


def test_the_same_letter_is_worth_different_points():
    assert TenPointScale().points("B") == 700
    assert FourPointScale().points("B") == 300


def test_the_top_grade_is_ten_on_the_ten_point_scale():
    assert TenPointScale().points("A+") == 1000


def test_the_top_grade_is_four_on_the_four_point_scale():
    assert FourPointScale().points("A") == 400


def test_a_grade_is_normalised_before_the_lookup():
    assert TenPointScale().points("  b+  ") == 800


def test_an_unknown_grade_names_the_scale():
    with pytest.raises(StudentError, match="not on the ten-point scale"):
        TenPointScale().points("Z")


def test_an_unknown_grade_lists_the_allowed_grades():
    with pytest.raises(StudentError, match="A\\+, A, B\\+, B, C\\+, C, D, F"):
        TenPointScale().points("Z")


def test_a_plus_grade_is_not_on_the_four_point_scale():
    with pytest.raises(StudentError, match="not on the four-point scale"):
        FourPointScale().points("A+")


def test_a_grade_that_is_not_text_is_refused():
    with pytest.raises(StudentError, match="a grade must be text, got int"):
        TenPointScale().points(9)


def test_an_empty_grade_is_refused():
    with pytest.raises(StudentError, match="a grade must not be empty"):
        TenPointScale().points("  ")


def test_has_is_true_for_a_known_grade():
    assert TenPointScale().has("a") is True


def test_has_is_false_for_an_unknown_grade():
    assert TenPointScale().has("Z") is False


def test_has_is_false_for_a_non_string():
    assert TenPointScale().has(9) is False


def test_contains_uses_the_same_answer_as_has():
    assert "B" in TenPointScale()
    assert "Z" not in TenPointScale()


def test_ordered_grades_runs_best_first():
    assert TenPointScale().ordered_grades() == ("A+", "A", "B+", "B", "C+",
                                                "C", "D", "F")


def test_the_maximum_is_the_best_grade_point():
    assert TenPointScale().maximum == 1000
    assert FourPointScale().maximum == 400


def test_the_top_grade_is_named():
    assert TenPointScale().top_grade == "A+"
    assert FourPointScale().top_grade == "A"


def test_a_scale_repr_reports_its_size_and_top():
    assert repr(TenPointScale()) == \
        "<TenPointScale ten-point, 8 grades, top 10.00>"


def test_scale_named_builds_a_ten_point_scale():
    assert isinstance(scale_named("ten-point"), TenPointScale)


def test_scale_named_is_case_insensitive():
    assert isinstance(scale_named("  TEN-POINT "), TenPointScale)


def test_scale_named_builds_a_four_point_scale():
    assert isinstance(scale_named("four-point"), FourPointScale)


def test_scale_named_refuses_an_unknown_scale():
    with pytest.raises(StudentError, match="is not a scale"):
        scale_named("six-point")


def test_scale_named_lists_the_choices():
    with pytest.raises(StudentError, match="four-point, ten-point"):
        scale_named("six-point")


def test_scale_named_refuses_a_non_string():
    with pytest.raises(StudentError, match="a scale name must be text"):
        scale_named(7)


def test_the_scale_table_is_pinned():
    assert sorted(SCALES) == ["four-point", "ten-point"]


# --------------------------------------------------------------------------- #
# Course
# --------------------------------------------------------------------------- #
def test_a_course_code_is_upper_cased():
    assert Course("cs301", "Algorithms", 4, "A").code == "CS301"


def test_a_course_title_is_trimmed():
    assert Course("CS301", "  Algorithms  ", 4, "A").title == "Algorithms"


def test_a_course_grade_is_upper_cased():
    assert Course("CS301", "Algorithms", 4, "a+").grade == "A+"


def test_a_course_keeps_its_credits():
    assert Course("CS301", "Algorithms", 4, "A").credits == 4


def test_a_course_code_that_is_not_text_is_refused():
    with pytest.raises(StudentError, match="course code must be text"):
        Course(301, "Algorithms", 4, "A")


def test_a_course_needs_a_code():
    with pytest.raises(StudentError, match="a course needs a code"):
        Course("  ", "Algorithms", 4, "A")


def test_a_course_code_cannot_hold_a_space():
    with pytest.raises(StudentError, match="contains whitespace"):
        Course("CS 301", "Algorithms", 4, "A")


def test_a_course_needs_a_title():
    with pytest.raises(StudentError, match="CS301 needs a title"):
        Course("CS301", "   ", 4, "A")


def test_a_course_needs_a_grade():
    with pytest.raises(StudentError, match="CS301 needs a grade"):
        Course("CS301", "Algorithms", 4, "  ")


def test_a_course_needs_at_least_one_credit():
    with pytest.raises(StudentError, match="1 to 12 credits, not 0"):
        Course("CS301", "Algorithms", 0, "A")


def test_a_course_cannot_carry_more_than_twelve_credits():
    with pytest.raises(StudentError, match="1 to 12 credits, not 13"):
        Course("CS301", "Algorithms", 13, "A")


def test_a_course_refuses_a_float_credit_count():
    with pytest.raises(StudentError, match="credits must be a whole number"):
        Course("CS301", "Algorithms", 4.0, "A")


def test_a_course_refuses_a_bool_credit_count():
    with pytest.raises(StudentError, match="credits must be a whole number"):
        Course("CS301", "Algorithms", True, "A")


def test_a_course_is_frozen():
    with pytest.raises(Exception):
        Course("CS301", "Algorithms", 4, "A").grade = "B"  # type: ignore


def test_courses_are_equal_by_value():
    assert Course("cs301", "Algorithms", 4, "A") == \
        Course("CS301", "Algorithms", 4, "A")


def test_courses_with_different_grades_differ():
    assert Course("CS301", "A", 4, "A") != Course("CS301", "A", 4, "B")


def test_a_course_is_hashable():
    assert len({Course("CS301", "A", 4, "A"),
                Course("cs301", "A", 4, "A")}) == 1


def test_a_course_str_is_one_row():
    text = str(Course("CS301", "Algorithms", 4, "A"))
    assert text.startswith("CS301") and "4cr" in text and text.endswith("A")


def test_a_course_round_trips():
    course = Course("CS301", "Algorithms", 4, "A")
    assert Course.from_dict(course.to_dict()) == course


def test_a_course_dict_names_its_credits():
    assert Course("CS301", "A", 4, "A").to_dict()["credits"] == 4


def test_course_from_dict_refuses_a_non_object():
    with pytest.raises(StudentError, match="a course must be an object"):
        Course.from_dict([])


def test_course_from_dict_refuses_an_unknown_key():
    row = Course("CS301", "A", 4, "A").to_dict()
    row["semester"] = 1
    with pytest.raises(StudentError, match="unknown course keys"):
        Course.from_dict(row)


def test_course_from_dict_requires_the_grade():
    row = Course("CS301", "A", 4, "A").to_dict()
    del row["grade"]
    with pytest.raises(StudentError, match="missing 'grade'"):
        Course.from_dict(row)


# --------------------------------------------------------------------------- #
# Transcript: the scale
# --------------------------------------------------------------------------- #
def test_a_transcript_defaults_to_the_ten_point_scale():
    assert Transcript().scale.name == "ten-point"


def test_a_transcript_takes_another_scale():
    assert Transcript(FourPointScale()).scale.name == "four-point"


def test_the_scale_setter_accepts_a_scale():
    sheet = Transcript()
    sheet.scale = FourPointScale()
    assert sheet.scale.name == "four-point"


def test_the_scale_setter_refuses_a_string():
    with pytest.raises(StudentError, match="needs a GradeScale, got str"):
        Transcript().scale = "ten-point"


def test_the_scale_setter_refuses_a_class():
    with pytest.raises(StudentError, match="needs a GradeScale, got a class, "
                                          "not an instance"):
        Transcript().scale = TenPointScale


def test_a_refused_scale_leaves_the_old_one():
    sheet = Transcript()
    with pytest.raises(StudentError):
        sheet.scale = 7
    assert sheet.scale.name == "ten-point"


# --------------------------------------------------------------------------- #
# Transcript: courses
# --------------------------------------------------------------------------- #
def test_a_new_transcript_is_empty():
    assert len(Transcript()) == 0


def test_add_returns_the_course():
    assert a_transcript().add(Course("CS302", "Databases", 3, "B")).code == \
        "CS302"


def test_add_refuses_a_non_course():
    with pytest.raises(StudentError, match="only a Course can go on a "
                                          "transcript, got str"):
        Transcript().add("CS301")


def test_add_refuses_a_grade_the_scale_does_not_have():
    with pytest.raises(StudentError, match="'A\\+' is not on the four-point "
                                          "scale"):
        Transcript(FourPointScale()).add(Course("CS301", "A", 4, "A+"))


def test_a_refused_grade_leaves_the_transcript_alone():
    sheet = Transcript(FourPointScale())
    with pytest.raises(StudentError):
        sheet.add(Course("CS301", "A", 4, "A+"))
    assert len(sheet) == 0


def test_a_retake_replaces_the_earlier_attempt():
    sheet = a_transcript(("CS301", 4, "B"))
    sheet.add(Course("CS301", "Algorithms", 4, "C"))
    assert len(sheet) == 1 and sheet["CS301"].grade == "C"


def test_a_retake_does_not_add_credits():
    sheet = a_transcript(("CS301", 4, "B"))
    sheet.add(Course("CS301", "Algorithms", 4, "C"))
    assert sheet.credits == 4


def test_retake_replaces_the_grade():
    sheet = a_transcript(("CS301", 4, "B"))
    assert sheet.retake("CS301", "C").grade == "C"


def test_retake_finds_the_course_case_insensitively():
    sheet = a_transcript(("CS301", 4, "B"))
    assert sheet.retake("cs301", "A").grade == "A"


def test_retake_keeps_the_credits_and_the_title():
    sheet = a_transcript(("CS301", 4, "B"))
    course = sheet.retake("CS301", "A")
    assert course.credits == 4 and course.title == "Course CS301"


def test_retake_refuses_a_course_that_is_not_there():
    with pytest.raises(UnknownCourse, match="no course with code CS999"):
        a_transcript().retake("CS999", "A")


def test_remove_drops_the_course():
    sheet = a_transcript(("CS301", 4, "A"), ("CS302", 3, "B"))
    assert sheet.remove("CS301").code == "CS301"
    assert len(sheet) == 1 and "CS301" not in sheet


def test_remove_refuses_an_unknown_course():
    with pytest.raises(UnknownCourse):
        a_transcript().remove("CS999")


def test_contains_accepts_a_code():
    assert "CS301" in a_transcript()


def test_contains_normalises_the_code():
    assert "cs301" in a_transcript()


def test_contains_is_false_for_another_code():
    assert "CS999" not in a_transcript()


def test_contains_is_false_for_a_non_string():
    assert 301 not in a_transcript()


def test_getitem_returns_the_course():
    assert a_transcript()["CS301"].credits == 4


def test_getitem_refuses_an_unknown_code():
    with pytest.raises(UnknownCourse, match="no course with code CS999 on "
                                          "this transcript"):
        a_transcript()["CS999"]


def test_getitem_refuses_a_non_string():
    with pytest.raises(UnknownCourse, match="no course with code 7"):
        a_transcript()[7]


def test_iteration_is_in_code_order():
    sheet = a_transcript(("CS302", 3, "B"), ("CS301", 4, "A"),
                         ("MA201", 3, "C"))
    assert [course.code for course in sheet] == ["CS301", "CS302", "MA201"]


def test_iteration_is_repeatable():
    sheet = a_transcript()
    assert list(sheet) == list(sheet)


def test_courses_is_a_tuple():
    assert isinstance(a_transcript().courses, tuple)


def test_a_transcript_repr_reports_its_credits():
    assert repr(a_transcript()) == \
        "<Transcript 1 course(s), 4 credits on the ten-point scale>"


# --------------------------------------------------------------------------- #
# Transcript: the numbers
# --------------------------------------------------------------------------- #
def test_an_empty_transcript_has_no_credits():
    assert Transcript().credits == 0


def test_an_empty_transcript_has_no_grade_points():
    assert Transcript().credit_points == 0


def test_credits_are_summed():
    assert a_transcript(("CS301", 4, "A"), ("CS302", 3, "B")).credits == 7


def test_grade_points_are_weighted_by_credits():
    sheet = a_transcript(("CS301", 4, "A"), ("CS302", 3, "B"))
    assert sheet.credit_points == 4 * 900 + 3 * 700


def test_a_retake_changes_the_grade_points():
    sheet = a_transcript(("CS301", 4, "B"))
    sheet.retake("CS301", "A")
    assert sheet.credit_points == 3600


def test_the_score_is_a_fraction():
    assert a_transcript().score == Fraction(900)


def test_the_score_keeps_the_exact_remainder():
    sheet = a_transcript(("CS301", 4, "A"), ("CS302", 3, "B+"))
    assert sheet.score == Fraction(3600 + 2400, 7)


def test_the_seeded_scores_are_pinned():
    assert a_transcript(("CE301", 4, "A+"), ("CE302", 3, "A"),
                        ("CE303", 3, "B+"), ("HS102", 2, "A")).score == \
        Fraction(10900, 12)


def test_an_empty_transcript_refuses_a_score():
    with pytest.raises(NoCourses, match="no credits"):
        Transcript().score


def test_an_empty_transcript_refuses_a_cgpa():
    with pytest.raises(NoCourses, match="no CGPA to report"):
        Transcript().gpa()


def test_an_empty_transcript_refuses_gpa_hundredths():
    with pytest.raises(NoCourses):
        Transcript().gpa_hundredths()


def test_a_single_grade_is_its_own_cgpa():
    assert a_transcript(("CS301", 4, "A")).gpa() == "9.00"


def test_the_cgpa_is_rounded_half_up():
    assert a_transcript(("CS301", 4, "A"), ("CS302", 3, "B+"),
                        ("CS303", 3, "B")).gpa() == "8.10"


def test_gpa_hundredths_is_the_rounded_integer():
    sheet = a_transcript(("CS301", 4, "A"), ("CS302", 3, "B+"),
                         ("CS303", 3, "B"))
    assert sheet.gpa_hundredths() == 810


def test_the_four_point_scale_changes_the_answer():
    sheet = a_transcript(("CS301", 3, "B"), scale=FourPointScale())
    assert sheet.gpa() == "3.00"


def test_grade_counts_is_best_first():
    sheet = a_transcript(("CS301", 4, "B"), ("CS302", 3, "A"),
                         ("CS303", 3, "A+"))
    assert list(sheet.grade_counts()) == ["A+", "A", "B"]


def test_grade_counts_counts_each_grade():
    sheet = a_transcript(("CS301", 4, "B"), ("CS302", 3, "B"),
                         ("CS303", 3, "A"))
    assert sheet.grade_counts() == {"A": 1, "B": 2}


def test_grade_counts_leaves_out_unused_grades():
    assert "F" not in a_transcript().grade_counts()


def test_a_failed_course_pulls_the_cgpa_down():
    assert a_transcript(("CS301", 4, "A"), ("CS302", 4, "F")).gpa() == "4.50"


# --------------------------------------------------------------------------- #
# Transcript: the file shape
# --------------------------------------------------------------------------- #
def test_a_transcript_round_trips():
    sheet = a_transcript(("CS301", 4, "A"), ("CS302", 3, "B"))
    assert Transcript.from_dict(sheet.to_dict()).to_dict() == sheet.to_dict()


def test_a_transcript_dict_is_sorted_by_code():
    sheet = a_transcript(("CS302", 3, "B"), ("CS301", 4, "A"))
    assert [row["code"] for row in sheet.to_dict()] == ["CS301", "CS302"]


def test_transcript_from_dict_refuses_a_non_list():
    with pytest.raises(StudentError, match="must be a list of courses"):
        Transcript.from_dict({"code": "CS301"})


def test_transcript_from_dict_refuses_a_bad_grade():
    with pytest.raises(StudentError, match="not on the ten-point scale"):
        Transcript.from_dict([{"code": "CS301", "title": "A", "credits": 4,
                               "grade": "Z"}])


def test_transcript_from_dict_takes_a_scale():
    with pytest.raises(StudentError, match="not on the four-point scale"):
        Transcript.from_dict(
            [{"code": "CS301", "title": "A", "credits": 4, "grade": "A+"}],
            FourPointScale())


def test_transcript_from_dict_can_be_given_a_four_point_scale():
    sheet = Transcript.from_dict(
        [{"code": "CS301", "title": "A", "credits": 4, "grade": "B"}],
        FourPointScale())
    assert sheet.gpa() == "3.00"


# --------------------------------------------------------------------------- #
# Student
# --------------------------------------------------------------------------- #
def test_a_student_keeps_its_roll_number():
    assert a_student("cs-2023-014").roll == "CS-2023-014"


def test_a_student_collapses_spaces_in_the_name():
    assert a_student(name="  Asha   Rao ").name == "Asha Rao"


def test_a_student_canonicalises_the_department():
    assert a_student(department="computer science").department == \
        "Computer Science"


def test_a_student_keeps_the_year():
    assert a_student(year=4).year == 4


def test_a_student_lower_cases_the_email():
    assert a_student(email="Asha.Rao@Example.edu").email == \
        "asha.rao@example.edu"


def test_a_student_keeps_ten_digits():
    assert a_student(phone="98765-43210").phone == "9876543210"


def test_a_student_needs_a_name():
    with pytest.raises(StudentError, match="a student needs a name"):
        a_student(name="   ")


def test_a_student_needs_a_text_name():
    with pytest.raises(StudentError, match="a student needs a name"):
        a_student(name=7)


def test_a_student_refuses_a_bad_roll_number():
    with pytest.raises(StudentError, match="is not a roll number"):
        a_student(roll="NOPE")


def test_a_student_refuses_an_unknown_department():
    with pytest.raises(StudentError, match="is not a department"):
        a_student(department="Law")


def test_a_student_refuses_a_bad_year():
    with pytest.raises(StudentError, match="must be 1, 2, 3 or 4"):
        a_student(year=5)


def test_a_student_refuses_a_bad_email():
    with pytest.raises(StudentError, match="needs a domain with a dot"):
        a_student(email="asha@example")


def test_a_student_refuses_a_bad_phone():
    with pytest.raises(StudentError, match="has 9 digits"):
        a_student(phone="987654321")


def test_a_student_needs_a_transcript():
    with pytest.raises(StudentError, match="needs a Transcript, got dict"):
        a_student(sheet={})


def test_a_new_student_has_no_courses():
    student = a_student(sheet=Transcript())
    assert student.credits == 0 and student.courses == ()


def test_a_new_student_has_no_cgpa():
    with pytest.raises(NoCourses):
        a_student(sheet=Transcript()).cgpa


def test_a_new_student_shows_a_dash_instead():
    assert a_student(sheet=Transcript()).cgpa_text == "-"


def test_the_cgpa_is_computed_from_the_transcript():
    assert a_student().cgpa == "9.00"


def test_the_cgpa_follows_a_new_course():
    student = a_student()
    student.add_course(Course("CS302", "Databases", 4, "F"))
    assert student.cgpa == "4.50"


def test_a_student_retake_delegates_to_the_transcript():
    student = a_student()
    student.retake("CS301", "F")
    assert student.cgpa == "0.00"


def test_a_student_score_is_a_fraction():
    assert a_student().score == Fraction(900)


def test_a_student_repr_names_the_cgpa():
    assert repr(a_student()) == "<Student CS-2023-014 'Asha Rao' 9.00>"


def test_a_student_str_is_one_row():
    text = str(a_student())
    assert text.startswith("CS-2023-014") and text.endswith("9.00")


def test_an_empty_student_str_ends_with_a_dash():
    assert str(a_student(sheet=Transcript())).rstrip().endswith("-")


def test_a_student_dict_has_no_cgpa():
    assert "cgpa" not in a_student().to_dict()


def test_a_student_dict_keeps_the_courses():
    assert a_student().to_dict()["courses"][0]["code"] == "CS301"


def test_a_student_round_trips():
    student = a_student()
    copy = Student.from_dict(student.to_dict())
    assert copy.to_dict() == student.to_dict()
    assert copy.cgpa == student.cgpa


def test_student_from_dict_refuses_a_stored_cgpa():
    row = a_student().to_dict()
    row["cgpa"] = 9.0
    with pytest.raises(StudentError, match="no stored cgpa"):
        Student.from_dict(row)


def test_student_from_dict_refuses_a_non_object():
    with pytest.raises(StudentError, match="a student must be an object"):
        Student.from_dict([])


def test_student_from_dict_refuses_an_unknown_key():
    row = a_student().to_dict()
    row["hostel"] = "A"
    with pytest.raises(StudentError, match="unknown student keys"):
        Student.from_dict(row)


def test_student_from_dict_requires_the_phone():
    row = a_student().to_dict()
    del row["phone"]
    with pytest.raises(StudentError, match="missing 'phone'"):
        Student.from_dict(row)


def test_student_from_dict_takes_a_scale():
    row = a_student().to_dict()
    row["courses"] = [{"code": "CS301", "title": "A", "credits": 4,
                       "grade": "B"}]
    student = Student.from_dict(row, FourPointScale())
    assert student.cgpa == "3.00"


# --------------------------------------------------------------------------- #
# Registry: construction and the collection protocol
# --------------------------------------------------------------------------- #
def test_a_registry_has_a_default_name():
    assert Registry().name == "Northgate Institute"


def test_a_registry_trims_its_name():
    assert Registry("  Test  ").name == "Test"


def test_a_registry_needs_a_name():
    with pytest.raises(StudentError, match="needs a name"):
        Registry("   ")


def test_a_registry_needs_a_text_name():
    with pytest.raises(StudentError, match="needs a name"):
        Registry(7)


def test_a_registry_defaults_to_the_ten_point_scale():
    assert Registry().scale.name == "ten-point"


def test_a_registry_takes_another_scale():
    assert Registry("R", FourPointScale()).scale.name == "four-point"


def test_the_registry_scale_setter_refuses_a_string():
    with pytest.raises(StudentError, match="needs a GradeScale, got str"):
        Registry().scale = "four-point"


def test_a_new_registry_is_empty():
    assert len(Registry()) == 0


def test_len_counts_the_students():
    assert len(a_registry(a_student(), a_student(
        roll="CS-2023-007", email="b@example.edu", phone="9000000001"))) == 2


def test_iteration_is_in_roll_order():
    registry = a_registry(
        a_student(roll="CS-2023-014"),
        a_student(roll="CE-2023-019", email="c@example.edu",
                  phone="9000000002"))
    assert [student.roll for student in registry] == ["CE-2023-019",
                                                      "CS-2023-014"]


def test_contains_accepts_a_roll_number():
    assert "CS-2023-014" in a_registry()


def test_contains_normalises_the_roll():
    assert "cs-2023-014" in a_registry()


def test_contains_is_false_for_another_roll():
    assert "CS-2023-999" not in a_registry()


def test_contains_is_false_for_a_malformed_roll():
    assert "nope" not in a_registry()


def test_contains_is_false_for_a_non_string():
    assert 7 not in a_registry()


def test_getitem_returns_the_student():
    assert a_registry()["CS-2023-014"].name == "Asha Rao"


def test_a_registry_repr_reports_its_totals():
    assert repr(a_registry()) == ("<Registry 'Test Institute' with 1 "
                                  "students, 4 credits on the ten-point "
                                  "scale>")


def test_students_is_a_tuple():
    assert isinstance(a_registry().students, tuple)


def test_total_credits_sums_the_transcripts():
    registry = a_registry(
        a_student(roll="CS-2023-014"),
        a_student(roll="CS-2023-007", email="b@example.edu",
                  phone="9000000001", sheet=a_transcript(("CS302", 3, "B"))))
    assert registry.total_credits == 7


# --------------------------------------------------------------------------- #
# Registry: adding, looking up, removing
# --------------------------------------------------------------------------- #
def test_add_returns_the_student():
    registry = Registry("R")
    assert registry.add(a_student()).roll == "CS-2023-014"


def test_add_refuses_a_non_student():
    with pytest.raises(StudentError, match="only a Student can be registered"):
        Registry("R").add("CS-2023-014")


def test_add_refuses_a_duplicate_roll():
    with pytest.raises(DuplicateStudent, match="already registered as"):
        a_registry().add(a_student(email="other@example.edu",
                                   phone="9000000001"))


def test_add_refuses_a_duplicate_email_across_case():
    with pytest.raises(DuplicateStudent, match="already registered to "
                                             "CS-2023-014"):
        a_registry().add(a_student(roll="CS-2023-007",
                                   email="ASHA.RAO@example.edu",
                                   phone="9000000001"))


def test_add_refuses_a_duplicate_phone():
    with pytest.raises(DuplicateStudent, match="already registered to "
                                             "CS-2023-014"):
        a_registry().add(a_student(roll="CS-2023-007",
                                   email="other@example.edu"))


def test_add_refuses_a_transcript_on_another_scale():
    with pytest.raises(StudentError, match="four-point scale and this "
                                          "registry uses the ten-point "
                                          "scale"):
        a_registry().add(a_student(
            roll="CS-2023-007", email="other@example.edu",
            phone="9000000001", sheet=a_transcript(scale=FourPointScale())))


def test_a_refused_student_leaves_the_registry_alone():
    registry = a_registry()
    with pytest.raises(DuplicateStudent):
        registry.add(a_student())
    assert len(registry) == 1


def test_a_four_point_registry_takes_a_four_point_student():
    registry = Registry("R", FourPointScale())
    student = a_student(sheet=a_transcript(("CS301", 4, "B"),
                                           scale=FourPointScale()))
    assert registry.add(student).cgpa == "3.00"


def test_student_looks_a_roll_number_up():
    assert a_registry().student("cs-2023-014").name == "Asha Rao"


def test_student_refuses_an_unknown_roll():
    with pytest.raises(UnknownStudent, match="no student with roll number"):
        a_registry().student("CS-2023-999")


def test_student_refuses_a_malformed_roll():
    with pytest.raises(StudentError, match="is not a roll number"):
        a_registry().student("nope")


def test_remove_drops_the_student():
    registry = a_registry()
    assert registry.remove("cs-2023-014").roll == "CS-2023-014"
    assert len(registry) == 0


def test_remove_refuses_an_unknown_roll():
    with pytest.raises(UnknownStudent):
        a_registry().remove("CS-2023-999")


# --------------------------------------------------------------------------- #
# Registry: search
# --------------------------------------------------------------------------- #
def test_search_matches_the_roll_number():
    assert [student.roll for student in a_registry().search("2023-014")] == \
        ["CS-2023-014"]


def test_search_matches_the_name():
    assert len(a_registry().search("asha")) == 1


def test_search_matches_the_department():
    registry = a_registry(
        a_student(roll="CE-2023-019", department="Civil",
                  email="c@example.edu", phone="9000000002"),
        a_student(roll="CS-2023-014"))
    assert [student.roll for student in registry.search("civil")] == \
        ["CE-2023-019"]


def test_search_matches_the_email():
    assert len(a_registry().search("example.edu")) == 1


def test_search_returns_every_match():
    registry = a_registry(
        a_student(roll="CS-2023-014", name="Asha Rao"),
        a_student(roll="CS-2023-007", name="Bilal Khan",
                  email="b@example.edu", phone="9000000001"))
    assert len(registry.search("a")) == 2


def test_search_is_case_insensitive():
    assert len(a_registry().search("ASHA")) == 1


def test_search_returns_nothing_for_no_match():
    assert a_registry().search("nothing") == []


def test_search_needs_text():
    with pytest.raises(StudentError, match="a search needs text"):
        a_registry().search(7)


def test_search_needs_something_to_look_for():
    with pytest.raises(StudentError, match="something to look for"):
        a_registry().search("   ")


# --------------------------------------------------------------------------- #
# Registry: ranking and reports
# --------------------------------------------------------------------------- #
def test_top_puts_the_best_first():
    registry = a_registry(
        a_student(roll="CS-2023-014", sheet=a_transcript(("CS301", 4, "B"))),
        a_student(roll="CS-2023-007", email="b@example.edu",
                  phone="9000000001", sheet=a_transcript(("CS301", 4, "A"))))
    assert [student.roll for student in registry.top(2)] == ["CS-2023-007",
                                                            "CS-2023-014"]


def test_top_defaults_to_three():
    registry = Registry("R")
    for index, grade in enumerate("ABC"):
        student = a_student(roll=f"CS-2023-00{index}",
                            email=f"s{index}@example.edu",
                            phone=f"900000000{index}",
                            sheet=a_transcript(("CS301", 4, grade)))
        registry.add(student)
    assert len(registry.top()) == 3


def test_top_breaks_a_tie_by_roll_number():
    registry = Registry("R")
    for index, roll in enumerate(("CS-2024-002", "CS-2024-001")):
        registry.add(a_student(roll=roll, email=f"s{index}@example.edu",
                               phone=f"900000000{index}"))
    assert [student.roll for student in registry.top(2)] == \
        ["CS-2024-001", "CS-2024-002"]


def test_top_orders_by_the_exact_score():
    registry = Registry("R")
    for index, (roll, grade) in enumerate((("CS-2024-002", "A"),
                                           ("CS-2024-001", "A+"))):
        registry.add(a_student(roll=roll, email=f"s{index}@example.edu",
                               phone=f"900000000{index}",
                               sheet=a_transcript(("CS301", 3, grade))))
    assert registry.top(1)[0].roll == "CS-2024-001"


def test_top_can_ask_for_more_than_there_is():
    assert len(a_registry().top(9)) == 1


def test_top_refuses_zero():
    with pytest.raises(StudentError, match="must be at least one"):
        a_registry().top(0)


def test_top_refuses_a_negative_count():
    with pytest.raises(StudentError, match="must not be negative"):
        a_registry().top(-1)


def test_top_refuses_a_float_count():
    with pytest.raises(StudentError, match="whole number"):
        a_registry().top(1.0)


def test_top_refuses_a_student_without_courses():
    registry = a_registry()
    registry.add(a_student(roll="CS-2023-007", email="b@example.edu",
                           phone="9000000001", sheet=Transcript()))
    with pytest.raises(NoCourses):
        registry.top(2)


def test_by_department_groups_the_students():
    registry = a_registry(
        a_student(roll="CE-2023-019", department="Civil",
                  email="c@example.edu", phone="9000000002"),
        a_student(roll="CS-2023-014"))
    assert [student.roll for student in
            registry.by_department()["Civil"]] == ["CE-2023-019"]


def test_by_department_is_sorted():
    registry = a_registry(
        a_student(roll="CE-2023-019", department="Civil",
                  email="c@example.edu", phone="9000000002"),
        a_student(roll="CS-2023-014"))
    assert list(registry.by_department()) == ["Civil", "Computer Science"]


def test_by_department_is_empty_for_an_empty_registry():
    assert Registry("R").by_department() == {}


def test_mean_credits_is_zero_for_an_empty_registry():
    assert Registry("R").mean_credits() == 0


def test_mean_credits_rounds_half_up():
    registry = a_registry(
        a_student(roll="CS-2023-014", sheet=a_transcript(("CS301", 4, "A"))),
        a_student(roll="CS-2023-007", email="b@example.edu",
                  phone="9000000001", sheet=a_transcript(("CS302", 3, "A"))))
    assert registry.mean_credits() == 4


# --------------------------------------------------------------------------- #
# Registry: the five invariants
# --------------------------------------------------------------------------- #
def test_a_clean_registry_passes_every_check():
    registry = a_registry()
    assert len(registry.audit()) == 5
    assert all(passed for _, passed in registry.audit())
    assert registry.problems() == []


def test_audit_names_its_checks():
    names = [name for name, _ in a_registry().audit()]
    assert "every student is filed under its roll number" in names
    assert "no two students share an email address" in names
    assert "no two students share a phone number" in names
    assert "every student has at least one course" in names
    assert "every course grade is on the ten-point scale" in names


def test_audit_catches_a_misfiled_student():
    registry = a_registry()
    registry._students["CS-2024-999"] = registry._students.pop("CS-2023-014")
    assert registry.problems() == ["every student is filed under its roll "
                                   "number"]


def test_audit_catches_a_shared_email():
    registry = a_registry()
    registry._students["CS-2023-007"] = a_student(
        roll="CS-2023-007", phone="9000000001")
    assert registry.problems() == ["no two students share an email address"]


def test_audit_catches_a_shared_phone():
    registry = a_registry()
    registry._students["CS-2023-007"] = a_student(
        roll="CS-2023-007", email="b@example.edu")
    assert registry.problems() == ["no two students share a phone number"]


def test_audit_catches_a_student_without_courses():
    registry = a_registry()
    registry.add(a_student(roll="CS-2023-007", email="b@example.edu",
                           phone="9000000001", sheet=Transcript()))
    assert registry.problems() == ["every student has at least one course"]


def test_audit_catches_a_foreign_grade():
    registry = a_registry()
    registry.student("CS-2023-014").transcript._courses["CS301"] = \
        Course("CS301", "Algorithms", 4, "Z")
    assert registry.problems() == ["every course grade is on the ten-point "
                                   "scale"]


def test_audit_names_the_four_point_scale():
    registry = Registry("R", FourPointScale())
    registry.add(a_student(sheet=a_transcript(("CS301", 4, "B"),
                                              scale=FourPointScale())))
    assert registry.problems() == []
    assert "every course grade is on the four-point scale" in \
        [name for name, _ in registry.audit()]


def test_audit_is_repeatable():
    registry = a_registry()
    assert registry.audit() == registry.audit()


# --------------------------------------------------------------------------- #
# Registry: persistence
# --------------------------------------------------------------------------- #
def test_a_registry_round_trips():
    registry = a_registry()
    assert Registry.from_dict(registry.to_dict()).to_dict() == \
        registry.to_dict()


def test_a_registry_dict_names_its_scale():
    assert a_registry().to_dict()["scale"] == "ten-point"


def test_a_registry_dict_lists_the_students():
    assert a_registry().to_dict()["students"][0]["roll"] == "CS-2023-014"


def test_registry_from_dict_refuses_a_non_object():
    with pytest.raises(StudentError, match="a registry document must be an "
                                          "object"):
        Registry.from_dict([])


def test_registry_from_dict_refuses_an_unknown_key():
    with pytest.raises(StudentError, match="unknown registry keys"):
        Registry.from_dict({"name": "x", "scale": "ten-point",
                            "students": [], "campus": "north"})


def test_registry_from_dict_requires_the_scale():
    with pytest.raises(StudentError, match="missing 'scale'"):
        Registry.from_dict({"name": "x", "students": []})


def test_registry_from_dict_requires_a_list_of_students():
    with pytest.raises(StudentError, match="'students' must be a list"):
        Registry.from_dict({"name": "x", "scale": "ten-point",
                            "students": {}})


def test_registry_from_dict_refuses_an_unknown_scale():
    with pytest.raises(StudentError, match="is not a scale"):
        Registry.from_dict({"name": "x", "scale": "six-point",
                            "students": []})


def test_registry_from_dict_refuses_a_duplicate_roll():
    payload = a_registry().to_dict()
    payload["students"].append(dict(payload["students"][0]))
    with pytest.raises(DuplicateStudent):
        Registry.from_dict(payload)


def test_registry_from_dict_reads_a_four_point_document():
    payload = {"name": "Four", "scale": "four-point", "students": [
        {"roll": "CS-2023-014", "name": "Asha Rao",
         "department": "Computer Science", "year": 3,
         "email": "asha.rao@example.edu", "phone": "9876543210",
         "courses": [{"code": "CS301", "title": "A", "credits": 3,
                      "grade": "A"},
                     {"code": "CS302", "title": "B", "credits": 3,
                      "grade": "B"}]}]}
    registry = Registry.from_dict(payload)
    assert registry.scale.name == "four-point"
    assert registry.student("CS-2023-014").cgpa == "3.50"


# --------------------------------------------------------------------------- #
# The data file
# --------------------------------------------------------------------------- #
def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "students.json"
    assert DATA_FILE.parent.name == "data"


def test_the_seeded_registry_loads():
    assert load_registry().name == "Northgate Institute"


def test_the_seeded_scale_is_ten_point():
    assert load_registry().scale.name == "ten-point"


def test_the_seeded_counts_are_pinned():
    seeded = load_registry()
    assert len(seeded) == 6 and seeded.total_credits == 80


def test_the_seeded_rolls_are_in_order():
    assert [student.roll for student in load_registry()] == [
        "CE-2023-019", "CS-2023-007", "CS-2023-014", "CS-2024-055",
        "EC-2022-031", "ME-2024-102"]


def test_the_seeded_cgpas_are_pinned():
    assert {student.roll: student.cgpa for student in load_registry()} == {
        "CE-2023-019": "9.08",
        "CS-2023-007": "7.50",
        "CS-2023-014": "8.93",
        "CS-2024-055": "8.31",
        "EC-2022-031": "9.00",
        "ME-2024-102": "7.23",
    }


def test_the_seeded_ranking_is_pinned():
    assert [student.roll for student in load_registry().top(3)] == [
        "CE-2023-019", "EC-2022-031", "CS-2023-014"]


def test_the_seeded_mean_credits_are_pinned():
    assert load_registry().mean_credits() == 13


def test_the_seeded_registry_is_clean():
    assert load_registry().problems() == []


def test_the_seeded_departments_are_pinned():
    assert list(load_registry().by_department()) == [
        "Civil", "Computer Science", "Electronics", "Mechanical"]


def test_the_seeded_search_finds_three():
    assert [student.roll for student in load_registry().search("an")] == [
        "CS-2023-007", "CS-2024-055", "ME-2024-102"]


def test_the_data_file_stores_no_cgpa():
    assert "cgpa" not in DATA_FILE.read_text(encoding="utf-8")


def test_load_registry_refuses_a_missing_file(tmp_path):
    with pytest.raises(StudentError, match="not found"):
        load_registry(tmp_path / "nope.json")


def test_load_registry_refuses_invalid_json(tmp_path):
    path = tmp_path / "students.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StudentError, match="not valid JSON"):
        load_registry(path)


def test_save_registry_writes_a_readable_file(tmp_path):
    seeded = load_registry()
    target = tmp_path / "out.json"
    save_registry(target, seeded)
    assert load_registry(target).to_dict() == seeded.to_dict()


def test_save_registry_returns_the_path(tmp_path):
    target = tmp_path / "out.json"
    assert save_registry(target, Registry("R")) == target


def test_save_registry_creates_directories(tmp_path):
    target = tmp_path / "a" / "b" / "students.json"
    save_registry(target, Registry("R"))
    assert target.is_file()


def test_save_registry_ends_with_a_newline(tmp_path):
    target = tmp_path / "out.json"
    save_registry(target, Registry("R"))
    assert target.read_text(encoding="utf-8").endswith("}\n")


def test_save_registry_is_byte_identical_on_a_second_save(tmp_path):
    target = tmp_path / "out.json"
    seeded = load_registry()
    save_registry(target, seeded)
    first = target.read_bytes()
    save_registry(target, load_registry(target))
    assert target.read_bytes() == first


# --------------------------------------------------------------------------- #
# The legacy project
# --------------------------------------------------------------------------- #
def test_the_legacy_cgpa_constant_is_the_column():
    assert LEGACY_CGPA == "cgpa = Column(Float, nullable=False)"


def test_the_legacy_search_constant_is_first():
    assert LEGACY_SEARCH == "query.first()"


def test_the_legacy_sort_constant_is_the_column_order():
    assert LEGACY_SORT == "order_by(desc(Student.cgpa))"


def test_the_legacy_validator_constant_is_a_class():
    assert LEGACY_VALIDATOR == "class Validator:"


def test_the_legacy_import_constant_is_a_session():
    assert LEGACY_IMPORT == "service = StudentService()"


def test_legacy_gpa_is_the_float_mean():
    assert legacy_gpa([(3, 8.7), (4, 9.1), (2, 7.6)]) == \
        77.69999999999999 / 9


def test_legacy_gpa_drifts_at_seventeen_digits():
    assert format(legacy_gpa([(3, 8.7), (4, 9.1), (2, 7.6)]),
                  ".17g") == "8.6333333333333329"


def test_legacy_gpa_refuses_no_credits():
    with pytest.raises(StudentError, match="no credits to average"):
        legacy_gpa([])


def test_a_legacy_record_is_a_number_and_a_count():
    assert legacy_record(8.7) == {"cgpa": 8.7, "courses": 0}


def test_a_legacy_record_holds_a_cgpa_with_no_courses():
    assert legacy_record(9.2, 0)["cgpa"] == 9.2


def test_legacy_rows_use_the_claims():
    rows = legacy_rows(load_registry())
    assert len(rows) == 6
    assert {"roll": "CS-2024-055", "cgpa": 9.20} in rows


def test_the_claims_cover_every_seeded_student():
    assert set(LEGACY_CLAIMS) == {student.roll for student in
                                  load_registry()}


def test_legacy_top_ranks_the_claim():
    assert legacy_top(legacy_rows(load_registry()))["roll"] == "CS-2024-055"


def test_legacy_top_disagrees_with_the_transcripts():
    seeded = load_registry()
    assert legacy_top(legacy_rows(seeded))["roll"] != seeded.top(1)[0].roll


def test_legacy_top_takes_the_first_maximum():
    rows = [{"roll": "A", "cgpa": 9.0}, {"roll": "B", "cgpa": 9.0}]
    assert legacy_top(rows)["roll"] == "A"


def test_legacy_top_refuses_an_empty_list():
    with pytest.raises(StudentError, match="no students to rank"):
        legacy_top([])


def test_the_seventeen_gigabyte_constant_is_the_hundredths_base():
    assert HUNDREDTHS == 100


def test_the_credit_cap_is_pinned():
    assert MAX_CREDITS_PER_COURSE == 12


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_shows_the_abstract_base_class(capsys):
    run_demo()
    assert "refused (2 TypeErrors)" in capsys.readouterr().out


def test_demo_shows_the_same_letter_on_two_scales(capsys):
    run_demo()
    assert "'B' is 700 hundredths" in capsys.readouterr().out


def test_demo_shows_the_weighted_mean(capsys):
    run_demo()
    assert "weighted 8.10" in capsys.readouterr().out


def test_demo_shows_the_float_drift(capsys):
    run_demo()
    assert "8.6333333333333329" in capsys.readouterr().out


def test_demo_shows_the_retake(capsys):
    run_demo()
    assert "retake CS301 moved the CGPA 7.00 -> 5.00" in \
        capsys.readouterr().out


def test_demo_shows_the_empty_transcript(capsys):
    run_demo()
    assert "a new student has no CGPA" in capsys.readouterr().out


def test_demo_shows_the_search_count(capsys):
    run_demo()
    assert "search('an') returns 3" in capsys.readouterr().out


def test_demo_shows_the_two_winners(capsys):
    run_demo()
    assert "ranks CS-2024-055 first on a typed 9.20" in \
        capsys.readouterr().out


def test_demo_shows_the_exact_ordering(capsys):
    run_demo()
    assert "both print 8.33" in capsys.readouterr().out


def test_demo_shows_the_seeded_counts(capsys):
    run_demo()
    assert "seeded: 6 students, 80 credits" in capsys.readouterr().out


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert all(ord(character) < 128 for character in out)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_students(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "6 students, 80 credits, mean 13 credits" in out
    assert "CE-2023-019" in out


def test_cli_students_flag_does_the_same(capsys):
    assert cli.main(["--students"]) == 0
    assert "6 students" in capsys.readouterr().out


def test_cli_search(capsys):
    assert cli.main(["--search", "khan"]) == 0
    out = capsys.readouterr().out
    assert "1 student(s) match 'khan'" in out
    assert "CS-2023-007" in out


def test_cli_search_with_several_matches(capsys):
    assert cli.main(["--search", "an"]) == 0
    assert "3 student(s) match 'an'" in capsys.readouterr().out


def test_cli_student_shows_the_transcript(capsys):
    assert cli.main(["--student", "CS-2023-014"]) == 0
    out = capsys.readouterr().out
    assert "4 course(s), 14 credits, CGPA 8.93" in out
    assert "CS301" in out and "9.00" not in out.split("CGPA")[0][-4:]


def test_cli_student_refuses_an_unknown_roll(capsys):
    assert cli.main(["--student", "CS-1999-001"]) == 2
    assert "no student with roll number" in capsys.readouterr().err


def test_cli_top(capsys):
    assert cli.main(["--top", "2"]) == 0
    out = capsys.readouterr().out
    assert "1. CE-2023-019" in out and "2. EC-2022-031" in out


def test_cli_top_refuses_text(capsys):
    assert cli.main(["--top", "many"]) == 2
    assert "not a whole number" in capsys.readouterr().err


def test_cli_department(capsys):
    assert cli.main(["--department", "computer science"]) == 0
    out = capsys.readouterr().out
    assert "3 student(s) in Computer Science" in out


def test_cli_department_refuses_an_unknown_name(capsys):
    assert cli.main(["--department", "Law"]) == 2
    assert "is not a department" in capsys.readouterr().err


def test_cli_report(capsys):
    assert cli.main(["--report"]) == 0
    out = capsys.readouterr().out
    assert "Computer Science    3 student(s)   41 credits" in out
    assert "mean 13 credits per student" in out


def test_cli_add(capsys):
    assert cli.main(["--add", "CS-2024-090:Nadia Iqbal:Computer Science:1:"
                              "nadia.iqbal@example.edu:9000000000"]) == 0
    out = capsys.readouterr().out
    assert "added CS-2024-090  Nadia Iqbal" in out
    assert "no CGPA yet" in out


def test_cli_add_refuses_a_duplicate_email(capsys):
    assert cli.main(["--add", "CS-2024-090:Twin:Computer Science:1:"
                              "ASHA.RAO@example.edu:9000000000"]) == 2
    assert "already registered to CS-2023-014" in capsys.readouterr().err


def test_cli_add_refuses_a_bad_year(capsys):
    assert cli.main(["--add", "CS-2024-090:Nadia:I:9:a@b.edu:9000000000"]) == 2
    assert "must be 1, 2, 3 or 4" in capsys.readouterr().err


def test_cli_add_refuses_a_non_numeric_year(capsys):
    assert cli.main(["--add", "CS-2024-090:Nadia:I:one:a@b.edu:9000000001"]) \
        == 2
    assert "not a whole number" in capsys.readouterr().err


def test_cli_add_refuses_a_malformed_spec(capsys):
    assert cli.main(["--add", "CS-2024-090:Nadia"]) == 2
    assert "expected ROLL:NAME:DEPARTMENT:YEAR:EMAIL:PHONE" in \
        capsys.readouterr().err


def test_cli_course(capsys):
    assert cli.main(["--course", "CS-2023-014:CS304:Compilers:4:A"]) == 0
    out = capsys.readouterr().out
    assert "recorded CS304 for CS-2023-014" in out
    assert "CGPA 8.94 over 18 credits" in out


def test_cli_course_replaces_an_existing_grade(capsys):
    assert cli.main(["--course", "CS-2023-014:CS301:Algorithms:4:B"]) == 0
    assert "replaced CS301" in capsys.readouterr().out


def test_cli_course_refuses_a_foreign_grade(capsys):
    assert cli.main(["--course", "CS-2023-014:CS305:Networks:4:Z"]) == 2
    assert "not on the ten-point scale" in capsys.readouterr().err


def test_cli_course_refuses_a_bad_credit_count(capsys):
    assert cli.main(["--course", "CS-2023-014:CS305:Networks:many:A"]) == 2
    assert "not a whole number" in capsys.readouterr().err


def test_cli_retake(capsys):
    assert cli.main(["--retake", "CS-2023-007:CS301:B"]) == 0
    out = capsys.readouterr().out
    assert "CS301 on CS-2023-007: B+ -> B" in out
    assert "the attempt was replaced, not added" in out


def test_cli_retake_refuses_an_unknown_course(capsys):
    assert cli.main(["--retake", "CS-2023-014:CS999:A"]) == 2
    assert "no course with code CS999" in capsys.readouterr().err


def test_cli_audit(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert "5/5 checks passed" in out
    assert "every course grade is on the ten-point scale" in out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "cgpa = Column(Float, nullable=False)" in out
    assert "query.first()" in out
    assert "class Validator:" in out
    assert "ranks CS-2024-055 first on a typed 9.20" in out


def test_cli_json_students(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "students" and payload["count"] == 6
    assert payload["credits"] == 80 and len(payload["students"]) == 6


def test_cli_json_top(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--top", "2", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["ranked"][0]["roll"] == "CE-2023-019"
    assert payload["ranked"][0]["cgpa"] == "9.08"


def test_cli_json_student(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--student", "ME-2024-102", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["cgpa"] == "7.23" and len(payload["courses"]) == 4


def test_cli_json_audit(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--audit", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["clean"] is True and len(payload["checks"]) == 5


def test_cli_json_legacy(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--legacy", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["claimed_top"] == "CS-2024-055"
    assert payload["computed_top"] == "CE-2023-019"


def test_cli_write_saves_a_retake(tmp_path, capsys):
    target = tmp_path / "saved.json"
    assert cli.main(["--retake", "CS-2023-007:CS301:C", "--write",
                     str(target)]) == 0
    capsys.readouterr()
    saved = load_registry(target)
    assert saved.student("CS-2023-007").transcript["CS301"].grade == "C"


def test_cli_write_saves_a_new_course(tmp_path, capsys):
    target = tmp_path / "saved.json"
    assert cli.main(["--course", "CS-2023-014:CS304:Compilers:4:A",
                     "--write", str(target)]) == 0
    capsys.readouterr()
    assert load_registry(target).total_credits == 84


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--audit", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_split_rejects_a_missing_part():
    with pytest.raises(StudentError, match="expected A:B"):
        cli._split("A", 2, "A:B")


def test_cli_split_strips_the_parts():
    assert cli._split(" a : b ", 2, "A:B") == ["a", "b"]


def test_cli_count_reads_a_whole_number():
    assert cli._count("12") == 12


def test_cli_count_refuses_text():
    with pytest.raises(StudentError, match="not a whole number"):
        cli._count("twelve")
