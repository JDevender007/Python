"""Tests for CSV_Student_Record_Manager: exact marks, strict CSV, atomic saves."""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from records import (                                     # noqa: E402
    DATA_FILE,
    DEPARTMENTS,
    HEADER,
    LEGACY_AVERAGE,
    LEGACY_DUPLICATE,
    LEGACY_FLOAT_ROW,
    LEGACY_SAVE,
    MAX_MARKS,
    RecordError,
    RowError,
    Student,
    StudentTable,
    TableError,
    check_marks,
    check_whole,
    check_year,
    format_marks,
    legacy_average,
    legacy_duplicate,
    legacy_report_text,
    legacy_row,
    load_table,
    normalise_department,
    normalise_name,
    normalise_roll,
    parse_marks,
    parse_whole,
    round_half_up,
    run_demo,
    save_atomic,
)

ROLL = "421123102001"


def a_student(**changes) -> Student:
    fields = {"roll": ROLL, "name": "Alex Mercer", "department": "CSE",
              "year": 3, "marks": 8900}
    fields.update(changes)
    return Student(**fields)


def a_table(*students) -> StudentTable:
    return StudentTable(students or (a_student(),))


def write_csv(path: Path, rows, header=HEADER) -> Path:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# round_half_up
# --------------------------------------------------------------------------- #
def test_round_half_up_rounds_a_half_up():
    assert round_half_up(8901, 2) == 4451


def test_round_half_up_keeps_an_exact_division():
    assert round_half_up(8910, 3) == 2970


def test_round_half_up_rounds_below_a_half_down():
    assert round_half_up(2, 3) == 1


def test_round_half_up_handles_a_negative_numerator():
    assert round_half_up(-8901, 2) == -4451


def test_round_half_up_refuses_a_zero_denominator():
    with pytest.raises(RecordError, match="denominator must be positive"):
        round_half_up(1, 0)


def test_the_seeded_averages_are_pinned():
    assert round_half_up(17075, 2) == 8538
    assert round_half_up(66550, 8) == 8319


# --------------------------------------------------------------------------- #
# parse_marks / format_marks
# --------------------------------------------------------------------------- #
def test_a_whole_mark_is_hundredths():
    assert parse_marks("89") == 8900


def test_one_decimal_is_padded():
    assert parse_marks("74.5") == 7450


def test_two_decimals_are_exact():
    assert parse_marks("88.25") == 8825


def test_marks_are_trimmed():
    assert parse_marks("  66  ") == 6600


def test_a_hundred_is_the_top():
    assert parse_marks("100") == MAX_MARKS


def test_zero_marks_are_allowed():
    assert parse_marks("0") == 0


def test_three_decimals_are_refused():
    with pytest.raises(RecordError, match="at most two decimals"):
        parse_marks("89.005")


def test_a_negative_mark_is_refused():
    with pytest.raises(RecordError, match="is not marks"):
        parse_marks("-1")


def test_a_mark_over_a_hundred_is_refused():
    with pytest.raises(RecordError, match="is over 100.00"):
        parse_marks("101")


def test_a_word_is_not_marks():
    with pytest.raises(RecordError, match="is not marks"):
        parse_marks("eighty")


def test_a_comma_is_not_a_decimal_point():
    with pytest.raises(RecordError, match="is not marks"):
        parse_marks("89,5")


def test_empty_marks_are_refused():
    with pytest.raises(RecordError, match="must not be empty"):
        parse_marks("   ")


def test_marks_that_are_not_text_are_refused():
    with pytest.raises(RecordError, match="marks must be text, got int"):
        parse_marks(89)


def test_format_marks_pads_the_fraction():
    assert format_marks(8905) == "89.05"


def test_format_marks_renders_a_whole_number():
    assert format_marks(8900) == "89.00"


def test_format_marks_renders_zero():
    assert format_marks(0) == "0.00"


def test_format_marks_renders_the_top():
    assert format_marks(MAX_MARKS) == "100.00"


def test_format_marks_renders_a_negative_value():
    assert format_marks(-5) == "-0.05"


def test_format_marks_refuses_a_float():
    with pytest.raises(RecordError, match="integer number of hundredths"):
        format_marks(89.0)


def test_format_marks_refuses_a_bool():
    with pytest.raises(RecordError, match="integer number of hundredths"):
        format_marks(True)


def test_marks_round_trip_through_text():
    for hundredths in (0, 5, 7450, 8825, MAX_MARKS):
        assert parse_marks(format_marks(hundredths)) == hundredths


# --------------------------------------------------------------------------- #
# check_whole / check_year / check_marks
# --------------------------------------------------------------------------- #
def test_check_whole_returns_the_number():
    assert check_whole(3, "a count") == 3


def test_check_whole_refuses_a_float():
    with pytest.raises(RecordError, match="a count must be a whole number"):
        check_whole(3.0, "a count")


def test_check_whole_refuses_a_bool():
    with pytest.raises(RecordError, match="got bool"):
        check_whole(True, "a count")


def test_a_year_between_one_and_four_is_accepted():
    assert check_year(1) == 1 and check_year(4) == 4


def test_a_year_of_zero_is_refused():
    with pytest.raises(RecordError, match="must be 1, 2, 3 or 4, got 0"):
        check_year(0)


def test_a_year_of_five_is_refused():
    with pytest.raises(RecordError, match="must be 1, 2, 3 or 4, got 5"):
        check_year(5)


def test_marks_are_bounded_at_construction():
    assert check_marks(MAX_MARKS) == MAX_MARKS


def test_marks_over_the_top_are_refused():
    with pytest.raises(RecordError, match="0 to 100.00"):
        check_marks(12000)


def test_negative_marks_are_refused():
    with pytest.raises(RecordError, match="0 to 100.00"):
        check_marks(-1)


def test_marks_must_be_a_whole_number_of_hundredths():
    with pytest.raises(RecordError, match="marks must be a whole number"):
        check_marks(88.25)


# --------------------------------------------------------------------------- #
# normalise_roll / normalise_name / normalise_department / parse_whole
# --------------------------------------------------------------------------- #
def test_a_roll_number_is_trimmed():
    assert normalise_roll("  421123102001  ") == ROLL


def test_a_short_roll_is_refused():
    with pytest.raises(RecordError, match="has 10 digits"):
        normalise_roll("4211231020")


def test_a_long_roll_is_refused():
    with pytest.raises(RecordError, match="has 13 digits"):
        normalise_roll("4211231020011")


def test_a_roll_with_letters_is_refused():
    with pytest.raises(RecordError, match="must be twelve digits"):
        normalise_roll("42112310200A")


def test_an_empty_roll_is_refused():
    with pytest.raises(RecordError, match="must not be empty"):
        normalise_roll("   ")


def test_a_roll_that_is_not_text_is_refused():
    with pytest.raises(RecordError, match="must be text, got int"):
        normalise_roll(421123102001)


def test_a_name_is_collapsed():
    assert normalise_name("  Alex   Mercer ") == "Alex Mercer"


def test_a_name_needs_letters():
    with pytest.raises(RecordError, match="needs a name"):
        normalise_name("   ")


def test_a_name_cannot_hold_a_line_break():
    with pytest.raises(RecordError, match="contains a line break"):
        normalise_name("Alex\nMercer")


def test_a_name_has_a_length_limit():
    with pytest.raises(RecordError, match="at most 40"):
        normalise_name("A" * 41)


def test_a_name_that_is_not_text_is_refused():
    with pytest.raises(RecordError, match="a name must be text, got int"):
        normalise_name(7)


def test_a_department_is_upper_cased():
    assert normalise_department("cse") == "CSE"


def test_a_department_tolerates_spaces():
    assert normalise_department("  mech  ") == "MECH"


def test_an_unknown_department_is_refused():
    with pytest.raises(RecordError, match="is not a department"):
        normalise_department("LAW")


def test_the_department_list_is_pinned():
    assert DEPARTMENTS == ("CSE", "ECE", "IT", "MECH")


def test_parse_whole_reads_a_number():
    assert parse_whole(" 3 ", "year") == 3


def test_parse_whole_refuses_a_word():
    with pytest.raises(RecordError, match="is not year"):
        parse_whole("three", "year")


# --------------------------------------------------------------------------- #
# Student
# --------------------------------------------------------------------------- #
def test_a_student_normalises_its_text():
    student = Student(" 421123102001 ", " alex  mercer ", "cse", 3, 8900)
    assert (student.roll, student.name, student.department) == \
        (ROLL, "alex mercer", "CSE")


def test_a_student_shows_its_marks_with_two_decimals():
    assert a_student().marks_text == "89.00"


def test_a_student_str_is_one_row():
    text = str(a_student())
    assert text.startswith(ROLL) and text.endswith("89.00")


def test_a_student_to_row_writes_text_cells():
    assert a_student().to_row() == [ROLL, "Alex Mercer", "CSE", "3", "89.00"]


def test_a_student_is_frozen():
    with pytest.raises(Exception):
        a_student().marks = 9000                     # type: ignore[misc]


def test_students_are_equal_by_value():
    assert a_student() == a_student()


def test_students_with_different_marks_differ():
    assert a_student() != a_student(marks=9100)


def test_a_student_is_hashable():
    assert len({a_student(), a_student()}) == 1


def test_a_student_refuses_a_bad_roll():
    with pytest.raises(RecordError, match="has 10 digits"):
        a_student(roll="4211231020")


def test_a_student_refuses_bad_marks():
    with pytest.raises(RecordError, match="0 to 100.00"):
        a_student(marks=10100)


def test_student_from_row_reads_five_cells():
    assert Student.from_row(a_student().to_row()) == a_student()


def test_student_from_row_names_its_line():
    with pytest.raises(RowError, match="line 7"):
        Student.from_row([ROLL, "Alex", "CSE", "9", "89"], 7)


def test_student_from_row_refuses_a_short_row():
    with pytest.raises(RowError, match="has 5 cells, not 2"):
        Student.from_row([ROLL, "Alex"], 2)


def test_student_from_row_refuses_a_non_list():
    with pytest.raises(RowError, match="must be a list"):
        Student.from_row("421123102001", 2)


def test_row_error_carries_its_line():
    try:
        Student.from_row([ROLL, "Alex", "LAW", "1", "89"], 3)
    except RowError as exc:
        assert exc.line == 3 and exc.reason.startswith("'LAW' is not")
        assert str(exc) == f"line 3: {exc.reason}"


def test_student_dict_round_trip():
    student = a_student()
    assert Student.from_dict(student.to_dict()) == student


def test_student_from_dict_reads_a_text_year_and_marks():
    student = Student.from_dict({"roll": ROLL, "name": "Alex",
                                 "department": "CSE", "year": "3",
                                 "marks": "88.25"})
    assert (student.year, student.marks) == (3, 8825)


def test_student_from_dict_refuses_an_unknown_key():
    row = a_student().to_dict()
    row["hostel"] = "A"
    with pytest.raises(RowError, match="unknown student keys"):
        Student.from_dict(row)


def test_student_from_dict_requires_marks():
    row = a_student().to_dict()
    del row["marks"]
    with pytest.raises(RowError, match="missing 'marks'"):
        Student.from_dict(row)


def test_student_from_dict_refuses_a_non_object():
    with pytest.raises(RowError, match="must be an object"):
        Student.from_dict([])


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #
def test_a_new_table_is_empty():
    assert len(StudentTable()) == 0


def test_the_table_counts_its_rows():
    assert len(a_table()) == 1


def test_iteration_is_in_roll_order():
    table = a_table(a_student(roll="421123102002"),
                    a_student(roll="421123102001"))
    assert [student.roll for student in table] == ["421123102001",
                                                   "421123102002"]


def test_contains_normalises_the_roll():
    assert " 421123102001 " in a_table()


def test_contains_is_false_for_a_bad_roll():
    assert "nope" not in a_table()


def test_contains_is_false_for_a_non_string():
    assert 7 not in a_table()


def test_getitem_returns_the_student():
    assert a_table()[ROLL].name == "Alex Mercer"


def test_a_table_repr_reports_its_size():
    assert repr(a_table()) == "<StudentTable with 1 students>"


def test_students_is_a_tuple():
    assert isinstance(a_table().students, tuple)


def test_a_duplicate_roll_is_refused():
    with pytest.raises(RecordError, match="already in the table"):
        a_table().add(a_student(name="Someone Else"))


def test_add_refuses_a_non_student():
    with pytest.raises(RecordError, match="only a Student can be added"):
        StudentTable().add("421123102001")


def test_student_looks_a_roll_up():
    assert a_table().student(" 421123102001 ").roll == ROLL


def test_student_refuses_an_unknown_roll():
    with pytest.raises(RecordError, match="no student with roll number"):
        a_table().student("421123102999")


def test_remove_drops_a_row():
    table = a_table()
    assert table.remove(ROLL).roll == ROLL
    assert len(table) == 0


def test_remove_refuses_an_unknown_roll():
    with pytest.raises(RecordError):
        a_table().remove("421123102999")


def test_update_replaces_a_field():
    table = a_table()
    assert table.update(ROLL, marks=9100).marks == 9100


def test_update_keeps_the_other_fields():
    table = a_table()
    table.update(ROLL, name="Alex M Mercer")
    assert table[ROLL].marks == 8900 and table[ROLL].year == 3


def test_update_validates_the_new_value():
    with pytest.raises(RecordError, match="0 to 100.00"):
        a_table().update(ROLL, marks=12000)


def test_update_refuses_an_unknown_field():
    with pytest.raises(RecordError, match="a student has no 'hostel'"):
        a_table().update(ROLL, hostel="A")


def test_search_matches_the_roll():
    assert len(a_table().search("102001")) == 1


def test_search_matches_the_name():
    assert len(a_table().search("mercer")) == 1


def test_search_matches_the_department():
    assert len(a_table().search("cse")) == 1


def test_search_is_case_insensitive():
    assert len(a_table().search("ALEX")) == 1


def test_search_returns_nothing_for_no_match():
    assert a_table().search("nothing") == []


def test_search_needs_text():
    with pytest.raises(RecordError, match="a search needs text"):
        a_table().search(7)


def test_search_needs_something_to_look_for():
    with pytest.raises(RecordError, match="something to look for"):
        a_table().search("  ")


def test_by_department_groups_and_sorts():
    table = a_table(a_student(roll="421123102002", department="IT"),
                    a_student())
    assert list(table.by_department()) == ["CSE", "IT"]


def test_total_marks_sums_the_column():
    table = a_table(a_student(marks=8900),
                    a_student(roll="421123102002", marks=9100))
    assert table.total_marks == 18000


def test_the_average_is_half_up():
    table = a_table(a_student(marks=8900),
                    a_student(roll="421123102002", marks=8901))
    assert table.average_marks() == 8901


def test_an_empty_table_has_no_average():
    assert StudentTable().average_marks() == 0


def test_top_puts_the_best_marks_first():
    table = a_table(a_student(marks=8900),
                    a_student(roll="421123102002", marks=9500))
    assert [student.roll for student in table.top(2)] == ["421123102002",
                                                          ROLL]


def test_top_breaks_a_tie_by_roll():
    table = a_table(a_student(marks=8900),
                    a_student(roll="421123102002", marks=8900))
    assert [student.roll for student in table.top(2)] == ["421123102001",
                                                          "421123102002"]


def test_top_refuses_zero():
    with pytest.raises(RecordError, match="must be at least one"):
        a_table().top(0)


def test_top_refuses_a_float_count():
    with pytest.raises(RecordError, match="whole number"):
        a_table().top(1.0)


def test_the_report_aggregates_by_department():
    table = a_table(a_student(),
                    a_student(roll="421123102002", department="IT",
                              marks=9100))
    rows = table.report()
    assert [row["department"] for row in rows] == ["CSE", "IT"]
    assert rows[0]["average"] == "89.00" and rows[0]["students"] == 1


def test_the_report_names_the_best_row():
    table = a_table(a_student(),
                    a_student(roll="421123102003", marks=9500))
    assert table.report()[0]["best"] == "421123102003"


def test_the_report_averages_half_up():
    table = a_table(a_student(marks=8900),
                    a_student(roll="421123102002", marks=8901))
    assert table.report()[0]["average"] == "89.01"


# --------------------------------------------------------------------------- #
# Invariants
# --------------------------------------------------------------------------- #
def test_a_clean_table_passes_every_check():
    assert len(a_table().audit()) == 5
    assert a_table().problems() == []


def test_audit_names_its_checks():
    names = [name for name, _ in a_table().audit()]
    assert names == ["every student is filed under its roll number",
                     "no two students share a roll number",
                     "every roll number is twelve digits",
                     "every mark is between 0 and 100",
                     "every department is one of the four"]


def test_audit_catches_a_misfiled_row():
    table = a_table()
    table._students["421123102999"] = table._students.pop(ROLL)
    assert table.problems() == ["every student is filed under its roll "
                                "number"]


def test_audit_catches_a_mark_out_of_range():
    table = a_table()
    object.__setattr__(table[ROLL], "marks", 12000)
    assert table.problems() == ["every mark is between 0 and 100"]


def test_audit_catches_a_foreign_department():
    table = a_table()
    object.__setattr__(table[ROLL], "department", "LAW")
    assert table.problems() == ["every department is one of the four"]


def test_audit_catches_a_short_roll():
    table = a_table()
    object.__setattr__(table[ROLL], "roll", "12345")
    assert table.problems() == ["every student is filed under its roll "
                                "number", "every roll number is twelve "
                                "digits"]


def test_audit_is_repeatable():
    table = a_table()
    assert table.audit() == table.audit()


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #
def test_a_table_saves_and_loads(tmp_path):
    target = tmp_path / "students.csv"
    a_table().save(target)
    assert load_table(target)[ROLL].marks == 8900


def test_a_save_writes_the_header_first(tmp_path):
    target = tmp_path / "students.csv"
    a_table().save(target)
    assert target.read_text(encoding="utf-8").splitlines()[0] == \
        ",".join(HEADER)


def test_a_save_ends_with_a_newline(tmp_path):
    target = tmp_path / "students.csv"
    a_table().save(target)
    assert target.read_bytes().endswith(b"\n")


def test_a_save_is_byte_identical_the_second_time(tmp_path):
    target = tmp_path / "students.csv"
    a_table(a_student(marks=7450)).save(target)
    first = target.read_bytes()
    load_table(target).save(target)
    assert target.read_bytes() == first


def test_a_save_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "students.csv"
    a_table().save(target)
    assert [entry.name for entry in tmp_path.iterdir()] == ["students.csv"]


def test_a_save_creates_directories(tmp_path):
    target = tmp_path / "a" / "b" / "students.csv"
    a_table().save(target)
    assert target.is_file()


def test_a_save_returns_the_path(tmp_path):
    target = tmp_path / "students.csv"
    assert a_table().save(target) == target


def test_a_failed_save_leaves_the_destination_alone(tmp_path):
    target = tmp_path / "students.csv"
    target.write_text("original\n", encoding="utf-8")

    def chunks():
        yield ",".join(HEADER) + "\n"
        raise OSError("the disk filled up")

    with pytest.raises(OSError, match="disk filled up"):
        save_atomic(target, chunks())
    assert target.read_text(encoding="utf-8") == "original\n"


def test_a_failed_save_removes_its_temporary_file(tmp_path):
    target = tmp_path / "students.csv"

    def chunks():
        yield "half a line"
        raise OSError("no space")

    with pytest.raises(OSError):
        save_atomic(target, chunks())
    assert list(tmp_path.iterdir()) == []


def test_to_text_holds_every_row(tmp_path):
    assert len(a_table().to_text().splitlines()) == 2


def test_load_reads_a_bom_from_a_spreadsheet(tmp_path):
    target = tmp_path / "students.csv"
    target.write_text(",".join(HEADER) + "\n" +
                      f"{ROLL},Alex Mercer,CSE,3,89\n",
                      encoding="utf-8-sig")
    assert load_table(target)[ROLL].marks == 8900


def test_load_refuses_a_missing_file(tmp_path):
    with pytest.raises(TableError, match="not found"):
        load_table(tmp_path / "nope.csv")


def test_load_refuses_an_empty_file(tmp_path):
    target = tmp_path / "students.csv"
    target.write_text("", encoding="utf-8")
    with pytest.raises(TableError, match="is empty"):
        load_table(target)


def test_load_names_a_missing_column(tmp_path):
    target = write_csv(tmp_path / "students.csv",
                       [[ROLL, "Alex", "CSE", "3", "89"]],
                       header=("Roll No", "Name", "Department", "Year",
                               "Mark"))
    with pytest.raises(TableError, match="missing Marks"):
        load_table(target)


def test_load_names_an_unexpected_column(tmp_path):
    target = write_csv(tmp_path / "students.csv",
                       [[ROLL, "Alex", "CSE", "3", "89", "x"]],
                       header=HEADER + ("Hostel",))
    with pytest.raises(TableError, match="unexpected Hostel"):
        load_table(target)


def test_load_refuses_columns_out_of_order(tmp_path):
    target = write_csv(tmp_path / "students.csv",
                       [["Alex", ROLL, "CSE", "3", "89"]],
                       header=("Name", "Roll No", "Department", "Year",
                               "Marks"))
    with pytest.raises(TableError, match="columns out of order"):
        load_table(target)


def test_load_names_the_line_of_a_bad_row(tmp_path):
    target = write_csv(tmp_path / "students.csv",
                       [[ROLL, "Alex", "CSE", "3", "89"],
                        ["421123102002", "John", "LAW", "3", "91"]])
    with pytest.raises(RowError, match="line 3"):
        load_table(target)


def test_load_skips_a_blank_line(tmp_path):
    target = tmp_path / "students.csv"
    target.write_text(",".join(HEADER) + "\n" +
                      f"{ROLL},Alex Mercer,CSE,3,89\n\n",
                      encoding="utf-8")
    assert len(load_table(target)) == 1


def test_load_refuses_non_utf8_bytes(tmp_path):
    target = tmp_path / "students.csv"
    target.write_bytes(b"Roll No,Name\n\xff\xfe\n")
    with pytest.raises(TableError, match="not UTF-8"):
        load_table(target)


def test_table_json_round_trip():
    table = a_table()
    assert StudentTable.from_dict(table.to_json()).to_json() == table.to_json()


def test_table_from_dict_refuses_a_non_list():
    with pytest.raises(RecordError, match="must be a list of students"):
        StudentTable.from_dict({})


def test_table_from_dict_names_a_bad_row():
    with pytest.raises(RowError, match="line 2"):
        StudentTable.from_dict([a_student().to_dict(),
                                {**a_student().to_dict(), "year": 9}])


def test_from_rows_numbers_the_rows():
    rows = [a_student().to_row(),
            a_student(roll="421123102002").to_row(),
            [ROLL, "Alex", "CSE", "9", "89"]]
    with pytest.raises(RowError, match="line 4"):
        StudentTable.from_rows(rows)


# --------------------------------------------------------------------------- #
# The seeded file
# --------------------------------------------------------------------------- #
def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "students.csv"
    assert DATA_FILE.parent.name == "data"


def test_the_seeded_table_has_eight_rows():
    assert len(load_table()) == 8


def test_the_seeded_rolls_are_in_order():
    assert [student.roll for student in load_table()] == [
        "421123102001", "421123102002", "421123102003", "421123102004",
        "421123102005", "421123102006", "421123102007", "421123102008"]


def test_the_seeded_total_is_pinned():
    assert load_table().total_marks == 66550


def test_the_seeded_average_is_pinned():
    assert load_table().average_marks() == 8319


def test_the_seeded_department_means_are_pinned():
    assert [row["average"] for row in load_table().report()] == [
        "90.75", "74.00", "85.38", "74.50"]


def test_the_seeded_ranking_is_pinned():
    assert [student.roll for student in load_table().top(3)] == [
        "421123102003", "421123102002", "421123102001"]


def test_the_seeded_file_is_clean():
    assert load_table().problems() == []


def test_the_seeded_file_holds_short_marks():
    assert ",89\n" in DATA_FILE.read_text(encoding="utf-8")


def test_the_seeded_marks_are_exact_after_one_save(tmp_path):
    target = tmp_path / "students.csv"
    load_table().save(target)
    assert ",89.00\n" in target.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# The legacy project
# --------------------------------------------------------------------------- #
def test_the_legacy_constants_are_the_column_and_the_calls():
    assert LEGACY_FLOAT_ROW == "marks: float"
    assert LEGACY_SAVE == 'open(CSV_FILE, "w")'
    assert LEGACY_DUPLICATE == "any(s.roll_no == roll for s in students)"
    assert LEGACY_AVERAGE.startswith("sum(student.marks")


def test_legacy_average_is_a_float_division():
    assert legacy_average([89.1, 89.1, 89.1]) == 89.09999999999998


def test_legacy_average_drifts_from_the_exact_mean():
    assert repr(legacy_average([89.1, 89.1, 89.1])) != "89.1"


def test_legacy_average_refuses_an_empty_list():
    with pytest.raises(RecordError, match="no marks to average"):
        legacy_average([])


def test_legacy_row_writes_a_float_mark():
    assert legacy_row(a_student())[4] == 89.0


def test_legacy_row_keeps_the_year_as_an_int():
    assert legacy_row(a_student())[3] == 3


def test_legacy_duplicate_compares_raw_text():
    assert legacy_duplicate([ROLL], " 421123102001") is False


def test_the_normalised_check_catches_what_the_legacy_one_misses():
    assert " 421123102001" in a_table()


def test_the_legacy_report_is_the_same_table():
    text = legacy_report_text(a_table())
    assert text.splitlines()[0] == ",".join(HEADER)
    assert len(text.splitlines()) == 2


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


def test_demo_shows_the_float_hundredth_loss(capsys):
    run_demo()
    assert "int(float('0.29') * 100) is 28" in capsys.readouterr().out


def test_demo_shows_the_float_mean(capsys):
    run_demo()
    assert "89.09999999999998" in capsys.readouterr().out


def test_demo_shows_half_up_against_round(capsys):
    run_demo()
    assert "round() gives 8900, half up gives 8901" in capsys.readouterr().out


def test_demo_shows_one_normalisation(capsys):
    run_demo()
    assert "byte-identical" in capsys.readouterr().out


def test_demo_shows_the_header_check(capsys):
    run_demo()
    assert "a column renamed to 'Mark' is refused" in capsys.readouterr().out


def test_demo_shows_the_line_number(capsys):
    run_demo()
    assert "a year of 7 on the fourth line is a RowError naming line 4" in \
        capsys.readouterr().out


def test_demo_shows_the_atomic_save(capsys):
    run_demo()
    assert "no .tmp behind" in capsys.readouterr().out


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


def test_cli_lists_every_row(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "8 rows, average 83.19" in out and ROLL in out


def test_cli_search(capsys):
    assert cli.main(["--search", "cse"]) == 0
    assert "3 row(s) match 'cse'" in capsys.readouterr().out


def test_cli_student(capsys):
    assert cli.main(["--student", " 421123102003 "]) == 0
    assert "Priya Nair" in capsys.readouterr().out


def test_cli_student_refuses_an_unknown_roll(capsys):
    assert cli.main(["--student", "421123102999"]) == 2
    assert "no student with roll number" in capsys.readouterr().err


def test_cli_sort_by_marks(capsys):
    assert cli.main(["--sort", "marks"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines()
             if line.startswith("  4211")]
    assert lines[0].startswith("  421123102003")


def test_cli_sort_by_name(capsys):
    assert cli.main(["--sort", "name"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines()
             if line.startswith("  4211")]
    assert lines[0].startswith("  421123102001")


def test_cli_average(capsys):
    assert cli.main(["--average"]) == 0
    out = capsys.readouterr().out
    assert "average 83.19" in out and "665.50 marks in total" in out


def test_cli_report(capsys):
    assert cli.main(["--report"]) == 0
    out = capsys.readouterr().out
    assert "CSE    3 student(s)  average  90.75" in out
    assert "IT     2 student(s)  average  85.38" in out


def test_cli_add(capsys):
    assert cli.main(["--add", "421123102009:Nadia Iqbal:CSE:1:90.5"]) == 0
    out = capsys.readouterr().out
    assert "added 421123102009  Nadia Iqbal" in out and "90.50" in out


def test_cli_add_refuses_a_duplicate(capsys):
    assert cli.main(["--add", "421123102001:Nadia:CSE:1:90"]) == 2
    assert "already in the table" in capsys.readouterr().err


def test_cli_add_refuses_three_decimals(capsys):
    assert cli.main(["--add", "421123102009:Nadia:CSE:1:90.555"]) == 2
    assert "at most two decimals" in capsys.readouterr().err


def test_cli_add_refuses_a_malformed_spec(capsys):
    assert cli.main(["--add", "421123102009:Nadia"]) == 2
    assert "expected ROLL:NAME:DEPARTMENT:YEAR:MARKS" in \
        capsys.readouterr().err


def test_cli_update(capsys):
    assert cli.main(["--update", "421123102001:marks=91.25"]) == 0
    assert "marks is now 91.25" in capsys.readouterr().out


def test_cli_update_refuses_an_unknown_field(capsys):
    assert cli.main(["--update", "421123102001:hostel=A"]) == 2
    assert "a student has no 'hostel'" in capsys.readouterr().err


def test_cli_update_needs_an_equals_sign(capsys):
    assert cli.main(["--update", "421123102001:marks"]) == 2
    assert "expected FIELD=VALUE" in capsys.readouterr().err


def test_cli_remove(capsys):
    assert cli.main(["--remove", "421123102008"]) == 0
    out = capsys.readouterr().out
    assert "removed 421123102008" in out and "7 rows" in out


def test_cli_audit(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert "5/5 checks passed" in out


def test_cli_legacy(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "marks: float" in out and 'open(CSV_FILE, "w")' in out
    assert "a second student to the legacy test" in out


def test_cli_json_listing(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["count"] == 8 and payload["average"] == "83.19"


def test_cli_json_report(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--report", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["departments"][2]["average"] == "85.38"
    assert payload["top"]["roll"] == "421123102003"


def test_cli_write_saves_the_change(tmp_path, capsys):
    target = tmp_path / "saved.csv"
    assert cli.main(["--update", "421123102001:marks=91.25",
                     "--write", str(target)]) == 0
    capsys.readouterr()
    assert load_table(target)[ROLL].marks == 9125


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--audit", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_split_rejects_a_missing_part():
    with pytest.raises(RecordError, match="expected A:B"):
        cli._split("A", 2, "A:B")


def test_cli_split_strips_the_parts():
    assert cli._split(" a : b ", 2, "A:B") == ["a", "b"]
