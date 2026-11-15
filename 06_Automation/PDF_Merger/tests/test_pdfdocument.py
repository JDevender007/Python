"""Tests for PDF_Merger: a bool is not an explanation, a list is not a file,
and a prefix is not a page."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
import pdfdocument as module                                  # noqa: E402
from pdfdocument import (                                     # noqa: E402
    BUNDLE_FILE,
    EOF_MARKER,
    FIXED_OBJECTS,
    MAGIC,
    VERSIONS,
    Document,
    Index,
    Lab,
    Object,
    Page,
    PdfError,
    Problem,
    Reading,
    Report,
    audit,
    build_document,
    build_documents,
    build_lab,
    check,
    check_files,
    check_index,
    check_title,
    count_pages,
    count_pages_naive,
    damage,
    describe,
    inspect,
    inspect_path,
    merge,
    merge_bytes,
    objects_of,
    page_objects,
    parse_document,
    problems,
    read_bundle,
    read_bytes,
    render,
    run_demo,
)


def alpha() -> Document:
    return build_document(["Cover", "Introduction", "Methods"])


def beta() -> Document:
    return build_document(["Results", "Discussion"])


def gamma() -> Document:
    return build_document(["Appendix"])


def a_lab() -> Lab:
    return build_lab((alpha(), beta(), gamma()),
                     ("alpha.pdf", "beta.pdf", "gamma.pdf"))


def with_written(lab: Lab, index: int, data: bytes) -> Lab:
    written = tuple(data if position == index else blob
                    for position, blob in enumerate(lab.written))
    return replace(lab, written=written)


# --------------------------------------------------------------------------- #
# Bytes, described
# --------------------------------------------------------------------------- #
def test_ascii_bytes_are_quoted_as_themselves():
    assert describe(b"%PDF-1.7") == "'%PDF-1.7'"


def test_a_trailing_newline_is_escaped():
    assert describe(b"%%EOF\n") == "'%%EOF\\x0a'"


def test_a_binary_header_is_escaped():
    assert describe(b"\x89PNG") == "'\\x89PNG'"


def test_nothing_is_described_as_nothing():
    assert describe(b"") == "''"


def test_only_the_first_eight_bytes_are_shown():
    assert describe(b"0123456789") == "'01234567'"


def test_describe_refuses_text():
    with pytest.raises(PdfError, match="describe reads bytes"):
        describe("not bytes")


# --------------------------------------------------------------------------- #
# A title
# --------------------------------------------------------------------------- #
def test_a_plain_title_is_accepted():
    assert check_title("Cover") == "Cover"


def test_a_title_with_a_space_is_accepted():
    assert check_title("Appendix A") == "Appendix A"


def test_a_title_with_a_slash_is_accepted():
    assert check_title("/Type /Page") == "/Type /Page"


def test_a_blank_title_is_refused():
    with pytest.raises(PdfError, match="cannot be blank"):
        check_title("   ")


def test_a_left_bracket_is_refused():
    with pytest.raises(PdfError, match="cannot hold"):
        check_title("a(b")


def test_a_right_bracket_is_refused():
    with pytest.raises(PdfError, match="cannot hold"):
        check_title("a)b")


def test_a_backslash_is_refused():
    with pytest.raises(PdfError, match="cannot hold"):
        check_title("a\\b")


def test_a_non_ascii_title_is_refused():
    with pytest.raises(PdfError, match="printable ASCII"):
        check_title("Caf\u00e9")


def test_a_title_that_is_not_text_is_refused():
    with pytest.raises(PdfError, match="title is text"):
        check_title(7)


# --------------------------------------------------------------------------- #
# A document
# --------------------------------------------------------------------------- #
def test_a_document_counts_its_pages():
    assert len(alpha()) == 3


def test_a_document_lists_its_titles():
    assert alpha().titles() == ("Cover", "Introduction", "Methods")


def test_a_document_numbers_a_page_from_one():
    assert alpha().number("Cover") == 1 and alpha().number("Methods") == 3


def test_a_document_refuses_an_unknown_title():
    with pytest.raises(PdfError, match="no page called 'Ghost'"):
        alpha().number("Ghost")


def test_a_document_prints_one_line_per_page():
    assert alpha().lines() == ("page 1: Cover", "page 2: Introduction",
                               "page 3: Methods")


def test_a_document_prints_its_size():
    assert alpha().size() == "3 page(s)"


def test_a_document_defaults_to_version_17():
    assert alpha().version == "1.7"


def test_a_document_can_be_built_from_titles():
    assert build_document(["a", "b"]) == Document((Page("a"), Page("b")))


# --------------------------------------------------------------------------- #
# Merging the values
# --------------------------------------------------------------------------- #
def test_a_merge_keeps_every_page_in_order():
    assert merge((alpha(), beta(), gamma())).titles() == (
        "Cover", "Introduction", "Methods", "Results", "Discussion",
        "Appendix")


def test_a_merge_of_one_document_is_that_document():
    assert merge((alpha(),)).titles() == alpha().titles()


def test_a_merge_needs_a_document():
    with pytest.raises(PdfError, match="nothing to merge"):
        merge(())


def test_a_merge_refuses_something_that_is_not_a_document():
    with pytest.raises(PdfError, match="document 1 is not a document"):
        merge(("alpha",))


def test_a_merge_refuses_a_document_with_no_pages():
    with pytest.raises(PdfError, match="document 2 holds no pages"):
        merge((alpha(), Document(())))


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def test_a_written_file_starts_with_the_header():
    assert render(alpha()).startswith(MAGIC + b"1.7")


def test_a_written_file_ends_with_the_marker():
    assert render(alpha()).rstrip().endswith(EOF_MARKER)


def test_a_written_file_holds_a_catalog_and_a_page_tree():
    data = render(alpha())
    types = [entry.type_name() for entry in objects_of(data)]
    assert types.count("Catalog") == 1 and types.count("Pages") == 1


def test_a_written_file_holds_one_page_object_per_page():
    assert count_pages(render(alpha())) == 3


def test_a_written_file_numbers_its_objects_from_one():
    data = render(beta())
    numbers = [entry.number for entry in objects_of(data)]
    assert numbers == list(range(1, FIXED_OBJECTS + 2 * 2 + 1))


def test_the_first_written_object_starts_after_the_header():
    data = render(gamma())
    assert objects_of(data)[0].offset == \
        len(b"%PDF-1.7\n% written by the PDF lab\n")


def test_writing_refuses_a_document_with_no_pages():
    with pytest.raises(PdfError, match="needs at least one page"):
        render(Document(()))


def test_writing_refuses_an_unknown_version():
    with pytest.raises(PdfError, match="the version is one of"):
        render(build_document(["a"], "2.0"))


def test_writing_refuses_a_title_it_cannot_escape():
    with pytest.raises(PdfError, match="cannot hold"):
        render(build_document(["a(b"]))


def test_writing_refuses_something_that_is_not_a_document():
    with pytest.raises(PdfError, match="render writes a document"):
        render("alpha")


def test_the_eight_versions_are_the_ones_listed():
    assert VERSIONS == ("1.4", "1.5", "1.6", "1.7")


# --------------------------------------------------------------------------- #
# Objects
# --------------------------------------------------------------------------- #
def test_objects_are_read_in_order():
    assert [entry.number for entry in objects_of(render(gamma()))] == [1, 2,
                                                                      3, 4]


def test_an_object_knows_where_it_starts():
    data = render(alpha())
    for entry in objects_of(data):
        assert data[entry.offset:].startswith(
            f"{entry.number} 0 obj".encode())


def test_the_page_tree_is_not_a_page():
    """The whole lesson: `/Type /Pages` starts with `/Type /Page`."""
    types = [entry.type_name() for entry in objects_of(render(alpha()))]
    assert types == ["Catalog", "Pages", "Page", "", "Page", "", "Page", ""]


def test_a_type_name_is_read_whole():
    entry = Object(1, 0, b"<< /Type /Pages /Kids [] >>")
    assert entry.type_name() == "Pages"


def test_an_object_without_a_type_names_nothing():
    assert Object(1, 0, b"<< /Length 20 >>").type_name() == ""


def test_a_type_that_is_not_a_name_names_nothing():
    assert Object(1, 0, b"<< /Type 7 >>").type_name() == ""


def test_a_file_with_no_objects_is_refused():
    with pytest.raises(PdfError, match="holds no objects"):
        objects_of(b"%PDF-1.7\nnothing here\n")


def test_an_object_that_never_closes_is_refused():
    with pytest.raises(PdfError, match="object 1 never closes"):
        objects_of(b"%PDF-1.7\n1 0 obj\n<< >>\n")


def test_two_objects_with_one_number_are_refused():
    with pytest.raises(PdfError, match="share a number"):
        objects_of(b"%PDF-1.7\n1 0 obj\n<< >>\nendobj\n1 0 obj\n<< >>\nendobj\n")


def test_page_objects_are_only_the_pages():
    assert len(page_objects(render(alpha()))) == 3


# --------------------------------------------------------------------------- #
# Counting pages
# --------------------------------------------------------------------------- #
def test_the_real_count_is_the_page_objects():
    assert count_pages(render(alpha())) == 3


def test_the_naive_count_is_one_too_many():
    """The defect, executable."""
    data = render(alpha())
    assert count_pages_naive(data) == 4
    assert count_pages(data) == 3


def test_the_naive_count_is_one_too_many_at_every_size():
    for document in (gamma(), beta(), alpha(), merge((alpha(), beta()))):
        data = render(document)
        assert count_pages_naive(data) == count_pages(data) + 1


def test_the_naive_count_is_right_when_there_is_no_tree():
    data = b"%PDF-1.7\n3 0 obj\n<< /Type /Page >>\nendobj\n"
    assert count_pages_naive(data) == count_pages(data) == 1


def test_a_title_that_says_type_page_fools_the_naive_count():
    data = render(build_document(["/Type /Page"]))
    assert count_pages(data) == 1 and count_pages_naive(data) == 3


# --------------------------------------------------------------------------- #
# The index
# --------------------------------------------------------------------------- #
def test_the_index_starts_after_the_last_object():
    data = render(alpha())
    index = check_index(data)
    assert data[index.offset:].startswith(b"xref")


def test_the_index_holds_one_entry_per_object():
    index = check_index(render(alpha()))
    assert index.count == FIXED_OBJECTS + 2 * 3 and index.first == 0


def test_the_trailer_size_matches_the_index():
    index = check_index(render(alpha()))
    assert index.size == index.first + index.count == 8


def test_the_trailer_root_is_the_catalog():
    assert check_index(render(alpha())).root == 1


def test_a_missing_startxref_is_refused():
    with pytest.raises(PdfError, match="no startxref"):
        check_index(b"%PDF-1.7\n1 0 obj\n<< >>\nendobj\n")


def test_a_startxref_that_is_not_a_number_is_refused():
    with pytest.raises(PdfError, match="which is not an offset"):
        check_index(b"startxref\nhere\n%%EOF\n")


def test_an_index_offset_past_the_end_is_refused():
    with pytest.raises(PdfError, match="past the end"):
        check_index(b"startxref\n9999\n%%EOF\n")


def test_an_index_offset_that_points_at_the_header_is_refused():
    with pytest.raises(PdfError, match="but the file holds '%PDF-1.7' there"):
        check_index(b"%PDF-1.7\nstartxref\n0\n%%EOF\n")


def test_an_entry_that_points_at_the_wrong_object_is_refused():
    data = damage(render(alpha()), "index")
    assert b"startxref" in data


def test_a_trailer_that_disagrees_with_the_index_is_refused():
    with pytest.raises(PdfError, match="and the trailer says /Size 999"):
        check_index(damage(render(alpha()), "trailer"))


def test_a_trailer_without_a_root_is_refused():
    data = render(gamma()).replace(b"/Root 1 0 R", b"/Root 1 0 Rr")
    with pytest.raises(PdfError, match="declares no /Root"):
        check_index(data)


def test_a_trailer_without_a_size_is_refused():
    data = render(gamma()).replace(b"/Size", b"/Sizes")
    with pytest.raises(PdfError, match="declares no /Size"):
        check_index(data)


def test_an_index_entry_that_is_not_nineteen_bytes_is_refused():
    data = render(gamma())
    index = check_index(data)
    broken = data[:index.offset] + data[index.offset:].replace(
        b"0000000000 65535 f \n", b"0000000000 65535 f\n", 1)
    with pytest.raises(PdfError, match="and every entry is exactly 19"):
        check_index(broken)


def test_the_index_of_the_bundled_first_document_is_pinned():
    index = check_index(render(alpha()))
    assert (index.offset, index.count, index.size) == (680, 8, 8)


# --------------------------------------------------------------------------- #
# Reading a document
# --------------------------------------------------------------------------- #
def test_a_written_document_reads_back_the_same():
    assert parse_document(render(alpha())).titles() == alpha().titles()


def test_every_bundled_shape_reads_back():
    for document in (gamma(), beta(), alpha(), merge((alpha(), beta()))):
        assert parse_document(render(document)).titles() == document.titles()


def test_an_empty_file_is_refused_with_a_reason():
    with pytest.raises(PdfError, match="the file is empty"):
        parse_document(b"")


def test_text_that_is_not_a_pdf_is_refused():
    with pytest.raises(PdfError, match="no %PDF- header: the file starts with "
                                       "'this is '"):
        parse_document(b"this is a text file")


def test_an_unknown_version_is_refused():
    with pytest.raises(PdfError, match="the header says version '2.0'"):
        parse_document(b"%PDF-2.0\n%%EOF\n")


def test_a_file_with_no_eof_marker_is_truncated():
    with pytest.raises(PdfError, match="has no %%EOF marker"):
        parse_document(b"%PDF-1.7\n1 0 obj\n<< >>\nendobj\n")


def test_bytes_appended_after_the_marker_are_refused():
    with pytest.raises(PdfError, match="not the last thing in the file"):
        parse_document(render(gamma()) + b"trailing junk")


def test_an_encrypted_file_is_refused_with_a_reason():
    with pytest.raises(PdfError, match="encrypted: the file declares /Encrypt"):
        parse_document(damage(render(alpha()), "encrypted"))


def test_a_file_cut_short_is_refused():
    with pytest.raises(PdfError, match="has no %%EOF marker"):
        parse_document(damage(render(alpha()), "truncated"))


def test_a_page_tree_that_lies_about_its_count_is_refused():
    with pytest.raises(PdfError, match="says /Count 9 and the file holds 3"):
        parse_document(damage(render(alpha()), "count"))


def test_a_file_whose_index_lies_is_refused():
    with pytest.raises(PdfError, match="the index is said to start at byte 0"):
        parse_document(damage(render(alpha()), "index"))


def test_a_file_with_no_page_object_is_refused():
    data = render(gamma()).replace(b"/Type /Page ", b"/Type /Pagz ")
    with pytest.raises(PdfError, match="none of them is a /Type /Page"):
        parse_document(data)


def test_a_file_with_no_page_tree_is_refused():
    data = render(gamma()).replace(b"/Type /Pages ", b"/Type /Pagez ")
    with pytest.raises(PdfError, match="no page tree"):
        parse_document(data)


def test_a_page_whose_contents_are_missing_from_the_file_is_refused():
    data = render(gamma()).replace(b"/Contents 4 0 R", b"/Contents 7 0 R")
    with pytest.raises(PdfError, match="the file holds no such object"):
        parse_document(data)


def test_a_page_with_no_contents_is_refused():
    data = render(gamma()).replace(b"/Contents 4 0 R", b"/Contentz 4 0 R")
    with pytest.raises(PdfError, match="declares no /Contents"):
        parse_document(data)


def test_a_content_stream_with_no_text_is_refused():
    data = render(gamma()).replace(b"(Appendix) Tj", b"(Appendix)   ")
    with pytest.raises(PdfError, match="holds no '\\(text\\) Tj'"):
        parse_document(data)


def test_reading_refuses_something_that_is_not_bytes():
    with pytest.raises(PdfError, match="read from bytes"):
        parse_document("a document")


def test_every_damage_has_its_own_reason():
    data = render(alpha())
    reasons = {damage(data, kind) for kind in
               ("empty", "text", "truncated", "index", "encrypted", "count")}
    shown = {inspect("x", raw).reason for raw in reasons}
    assert len(shown) == 6


def test_damage_refuses_an_unknown_kind():
    with pytest.raises(PdfError, match="no such damage"):
        damage(render(alpha()), "soggy")


# --------------------------------------------------------------------------- #
# A bundle of documents
# --------------------------------------------------------------------------- #
def test_a_bundle_is_read_from_two_columns():
    documents = build_documents("a\tone\na\ttwo\nb\tthree\n")
    assert [document.titles() for document in documents.values()] == \
        [("one", "two"), ("three",)]


def test_a_bundle_skips_comments_and_blanks():
    assert len(build_documents("; note\n# note\na\tone\n\n")) == 1


def test_a_bundle_line_without_a_tab_is_refused():
    with pytest.raises(PdfError, match="line 1: expected a document name"):
        build_documents("a one\n")


def test_a_bundle_with_a_blank_name_is_refused():
    with pytest.raises(PdfError, match="line 1: the document name is blank"):
        build_documents("\tone\n")


def test_a_bundle_with_no_pages_is_refused():
    with pytest.raises(PdfError, match="bundle holds no pages"):
        build_documents("; nothing\n")


def test_the_bundled_bundle_holds_three_documents():
    bundle = read_bundle()
    assert list(bundle) == ["alpha", "beta", "gamma"]


def test_the_bundled_page_counts_are_pinned():
    bundle = read_bundle()
    assert [len(document) for document in bundle.values()] == [3, 2, 1]


def test_the_bundled_titles_are_pinned():
    assert [document.titles() for document in read_bundle().values()] == [
        ("Cover", "Introduction", "Methods"), ("Results", "Discussion"),
        ("Appendix",)]


def test_a_missing_bundle_is_refused(tmp_path):
    with pytest.raises(PdfError, match="file not found"):
        read_bundle(tmp_path / "nope.txt")


def test_the_bundled_file_is_pinned_on_disk():
    assert BUNDLE_FILE.read_text(encoding="utf-8").count("\t") == 6


# --------------------------------------------------------------------------- #
# A reading, a problem, a report
# --------------------------------------------------------------------------- #
def test_a_reading_with_a_document_is_ok():
    assert Reading("a.pdf", alpha()).ok() is True


def test_a_reading_with_a_reason_is_not_ok():
    assert Reading("a.pdf", None, "the file is empty").ok() is False


def test_a_reading_prints_its_size():
    assert Reading("a.pdf", alpha()).line() == "a.pdf              3 page(s)"


def test_a_reading_prints_its_reason():
    assert Reading("a.pdf", None, "the file is empty").line() == \
        "a.pdf              the file is empty"


def test_a_problem_prints_its_file_and_reason():
    assert Problem("a.pdf", "the file is empty").line() == \
        "a.pdf              the file is empty"


def test_a_report_with_no_problems_is_ok():
    report = Report((Reading("a.pdf", alpha()),), (), "merged.pdf")
    assert report.ok() is True


def test_a_report_prints_a_comfortable_line_when_it_is_clean():
    report = Report((Reading("a.pdf", alpha()),), (), "merged.pdf")
    assert report.lines() == ("no problem: every input is a document this lab "
                              "can read",)


def test_a_report_summarises_itself():
    report = Report((Reading("a.pdf", alpha()),
                     Reading("b.pdf", None, "empty")),
                    (Problem("b.pdf", "empty"),), "merged.pdf")
    assert report.summary() == "2 input(s), 1 readable, 1 problem(s)"


def test_a_report_reads_only_the_documents_it_has():
    report = Report((Reading("a.pdf", alpha()),
                     Reading("b.pdf", None, "empty")), (), "merged.pdf")
    assert report.read() == (alpha(),)


def test_a_report_lists_its_reasons():
    report = Report((), (Problem("a.pdf", "empty"),), "merged.pdf")
    assert report.reasons() == ("empty",)


# --------------------------------------------------------------------------- #
# Inspecting a path
# --------------------------------------------------------------------------- #
def test_a_missing_file_says_it_is_missing():
    reading = inspect("gone.pdf")
    assert reading.ok() is False
    assert reading.reason == "there is no such file: gone.pdf"


def test_an_empty_file_says_it_is_empty():
    assert inspect("a.pdf", b"").reason == \
        "the file is empty: there is not one byte in it"


def test_a_good_file_reads():
    assert inspect("a.pdf", render(alpha())).document == alpha()


def test_reading_a_path_that_is_not_there_keeps_the_reason(tmp_path):
    assert inspect_path(tmp_path / "gone.pdf").reason.startswith(
        "there is no such file")


def test_reading_a_path_that_is_text_keeps_the_reason(tmp_path):
    path = tmp_path / "renamed.pdf"
    path.write_bytes(b"not a pdf at all\n")
    assert "no %PDF- header" in inspect_path(path).reason


def test_read_bytes_refuses_a_missing_file(tmp_path):
    with pytest.raises(PdfError, match="there is no such file"):
        read_bytes(tmp_path / "gone.pdf")


def test_read_bytes_returns_the_file(tmp_path):
    path = tmp_path / "a.pdf"
    path.write_bytes(render(gamma()))
    assert read_bytes(path) == render(gamma())


# --------------------------------------------------------------------------- #
# Checking a list
# --------------------------------------------------------------------------- #
def test_a_list_of_two_good_files_is_ok():
    report = check((("a.pdf", render(alpha())), ("b.pdf", render(beta()))))
    assert report.ok() is True and len(report.read()) == 2


def test_one_file_is_not_enough():
    report = check((("a.pdf", render(alpha())),))
    assert report.reasons() == ("at least two documents are needed to merge, "
                                "and the list holds 1",)


def test_an_empty_list_says_it_is_empty():
    report = check(())
    assert report.ok() is False and "the list holds 0" in report.reasons()[0]


def test_a_bad_file_is_named_and_explained():
    report = check((("a.pdf", render(alpha())), ("b.pdf", b"")))
    assert report.reasons() == ("the file is empty: there is not one byte in "
                                "it",)
    assert report.problems[0].name == "b.pdf"


def test_a_duplicate_is_named():
    report = check((("a.pdf", render(alpha())), ("a.pdf", render(alpha()))))
    assert report.reasons() == ("duplicate: this file is already in the list "
                                "at position 1",)


def test_a_duplicate_is_compared_without_case():
    report = check((("A.pdf", render(alpha())), ("a.pdf", render(alpha()))))
    assert "duplicate" in report.reasons()[0]


def test_an_output_that_is_one_of_the_inputs_is_refused():
    report = check((("a.pdf", render(alpha())), ("b.pdf", render(beta()))),
                   "b.pdf")
    assert report.reasons() == ("the output path is one of the inputs, so "
                                "writing it would overwrite a source",)


def test_a_blank_output_is_refused():
    report = check((("a.pdf", render(alpha())), ("b.pdf", render(beta()))), " ")
    assert "the output path is blank" in report.reasons()


def test_every_input_gets_a_reading_in_order():
    report = check((("a.pdf", render(alpha())), ("b.pdf", b""), ("c.pdf", b"")))
    assert [reading.name for reading in report.readings] == ["a.pdf", "b.pdf",
                                                             "c.pdf"]


def test_a_missing_path_becomes_a_reason_not_an_exception(tmp_path):
    report = check_files([tmp_path / "gone.pdf", tmp_path / "also.pdf"],
                         "out.pdf")
    assert len(report.problems) == 2
    assert all("there is no such file" in problem.reason
               for problem in report.problems)


def test_check_files_reads_a_real_file(tmp_path):
    path = tmp_path / "a.pdf"
    path.write_bytes(render(gamma()))
    report = check_files([path, path], "out.pdf")
    assert report.ok() is False and "duplicate" in report.reasons()[0]


def test_a_blank_input_path_is_named():
    report = check((("", render(alpha())), ("b.pdf", render(beta()))))
    assert "(input)" in [problem.name for problem in report.problems]


# --------------------------------------------------------------------------- #
# Merging the bytes
# --------------------------------------------------------------------------- #
def test_merging_bytes_returns_a_file_and_a_report():
    data, report = merge_bytes((("a.pdf", render(alpha())),
                                ("b.pdf", render(beta()))))
    assert report.ok() is True and parse_document(data).titles() == (
        "Cover", "Introduction", "Methods", "Results", "Discussion")


def test_merging_bytes_returns_nothing_when_the_report_fails():
    data, report = merge_bytes((("a.pdf", render(alpha())), ("b.pdf", b"")))
    assert data == b"" and report.ok() is False


def test_the_merged_file_is_not_the_first_file():
    data, _ = merge_bytes((("a.pdf", render(alpha())), ("b.pdf", render(beta()))))
    assert data != render(alpha()) and count_pages(data) == 5


# --------------------------------------------------------------------------- #
# The lab
# --------------------------------------------------------------------------- #
def test_a_lab_writes_every_part():
    assert len(a_lab().written) == 3


def test_a_lab_merges_every_part():
    assert len(a_lab().merged) == 6


def test_a_lab_names_the_parts_when_none_are_given():
    lab = build_lab((alpha(), beta()))
    assert [reading.name for reading in lab.report.readings] == [
        "part-1.pdf", "part-2.pdf"]


def test_a_lab_refuses_more_names_than_parts():
    with pytest.raises(PdfError, match="every part needs a name"):
        build_lab((alpha(), beta()), ("only-one.pdf",))


def test_the_lab_report_is_clean():
    assert a_lab().report.ok() is True


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every part writes bytes that begin with %PDF- and end with %%EOF",
    "every written file parses back to the part it was written from",
    "every index entry points at its own object header",
    "the page tree's /Count equals the number of page objects",
    "the naive /Type /Page count is exactly one too many per document",
    "the merged document holds every page of its parts, in order",
    "every reading holds a document or a reason, never both, never neither",
    "every failed reading is named by a problem that names a file",
    "every page title is printable ASCII with no bracket or backslash",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_lab())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_lab():
    assert problems(audit(a_lab())) == []


def test_the_audit_is_repeatable():
    assert audit(a_lab()) == audit(a_lab())


def test_the_audit_catches_a_title_it_cannot_write():
    lab = replace(a_lab(), parts=(build_document(["a(b"]),))
    assert CHECK_NAMES[0] in problems(audit(lab))


def test_the_audit_catches_a_written_file_that_is_not_its_part():
    lab = a_lab()
    assert CHECK_NAMES[1] in problems(audit(with_written(lab, 0, lab.written[1])))


def test_the_audit_catches_an_index_that_points_at_nothing():
    lab = a_lab()
    broken = with_written(lab, 0, damage(lab.written[0], "index"))
    assert CHECK_NAMES[2] in problems(audit(broken))


def test_the_audit_does_not_raise_on_a_broken_index():
    lab = a_lab()
    broken = with_written(lab, 0, damage(lab.written[0], "index"))
    assert len(audit(broken)) == 9


def test_the_audit_catches_a_page_tree_that_lies():
    lab = a_lab()
    broken = with_written(lab, 0, damage(lab.written[0], "count"))
    assert CHECK_NAMES[3] in problems(audit(broken))


def test_the_audit_catches_a_title_that_says_type_page():
    lab = build_lab((build_document(["/Type /Page"]),))
    assert CHECK_NAMES[4] in problems(audit(lab))


def test_the_audit_catches_a_merge_that_lost_a_page():
    lab = replace(a_lab(), merged=build_document(["Cover"]))
    assert CHECK_NAMES[5] in problems(audit(lab))


def test_the_audit_catches_a_reading_that_says_nothing():
    lab = a_lab()
    broken = replace(lab, report=replace(lab.report,
                                         readings=(Reading("a.pdf", None, ""),)))
    assert CHECK_NAMES[6] in problems(audit(broken))


def test_the_audit_catches_a_problem_with_no_file():
    lab = a_lab()
    broken = replace(lab, report=replace(lab.report,
                                        problems=(Problem("", "empty"),)))
    assert CHECK_NAMES[7] in problems(audit(broken))


def test_the_audit_catches_a_title_with_a_bracket():
    lab = replace(a_lab(), merged=build_document(["a(b"]))
    assert CHECK_NAMES[8] in problems(audit(lab))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_lines(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "except Exception:" in out
    assert "return len(pdf_files) >= 2" in out


def test_demo_shows_the_validator_passing_unusable_names(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "it answers True -- the count is the whole check" in out
    assert "there is no such file: missing.pdf" in out
    assert "no %PDF- header: the file starts with '; three '" in out


def test_demo_shows_the_two_page_counts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "alpha.pdf holds 3 page object(s) with /Type /Page" in out
    assert "answers 4 -- one too many" in out


def test_demo_shows_the_index(capsys):
    run_demo()
    assert "the index starts at byte 680 and holds 8 entr(ies), /Size 8, " \
           "/Root 1" in capsys.readouterr().out


def test_demo_shows_six_reasons(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "truncated: the file has no %%EOF marker" in out
    assert "encrypted: the file declares /Encrypt" in out
    assert "the page tree says /Count 9 and the file holds 3 page object(s)" \
           in out


def test_demo_shows_the_duplicate_and_the_output_clash(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "duplicate: this file is already in the list at position 1" in out
    assert "writing it would overwrite a source" in out


def test_demo_shows_all_nine_checks(capsys):
    run_demo()
    assert "9/9 checks pass" in capsys.readouterr().out


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


def test_cli_merges_the_bundle(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--pages"]) == 0
    out = capsys.readouterr().out
    assert "  3 input(s), 3 readable, 0 problem(s), output merged.pdf" in out
    assert "  merged: 6 page(s) -> 1583 bytes" in out
    assert "page 6: Appendix" in out
    assert "holds 6 page object(s) where the substring count says 7" in out
    assert (tmp_path / "merged.pdf").read_bytes() == render(
        merge((alpha(), beta(), gamma())))


def test_cli_writes_the_bundle_out(tmp_path, capsys):
    assert cli.main(["--write", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "wrote 3 page(s)" in out
    assert (tmp_path / "alpha.pdf").read_bytes() == render(alpha())


def test_cli_merges_files_from_disk(tmp_path, capsys):
    first = tmp_path / "alpha.pdf"
    first.write_bytes(render(alpha()))
    second = tmp_path / "beta.pdf"
    second.write_bytes(render(beta()))
    target = tmp_path / "out.pdf"
    assert cli.main(["--file", str(first), str(second),
                     "--output", str(target), "--pages"]) == 0
    out = capsys.readouterr().out
    assert "page 5: Discussion" in out
    assert "holds 5 page object(s)" in out
    assert count_pages(target.read_bytes()) == 5


def test_cli_names_a_missing_file_and_exits_one(tmp_path, capsys):
    first = tmp_path / "alpha.pdf"
    first.write_bytes(render(alpha()))
    assert cli.main(["--file", str(first), str(tmp_path / "gone.pdf"),
                     "--output", str(tmp_path / "out.pdf")]) == 1
    out = capsys.readouterr().out
    assert "there is no such file" in out
    assert "nothing was merged and nothing was written" in out
    assert not (tmp_path / "out.pdf").exists()


def test_cli_audit_prints_every_verdict(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert [item["name"] for item in payload["inputs"]] == ["alpha", "beta",
                                                           "gamma"]
    assert payload["merged_pages"][0] == "Cover"
    assert payload["merged_bytes"] == 1583


def test_cli_quiet_prints_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_bundle_exits_two(tmp_path, capsys):
    assert cli.main(["--bundle", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_bundle_exits_two(tmp_path, capsys):
    path = tmp_path / "pages.txt"
    path.write_bytes(b"no tab here\n")
    assert cli.main(["--bundle", str(path)]) == 2
    assert "expected a document name" in capsys.readouterr().err
