from schedagent.agent import SOLVER_PROMPT, SYSTEM_PROMPT
from schedagent.tools import BOOK, BOOK_FOUND
from schedagent.versions import PLAIN, SOLVER, SOLVER2, VERSIONS


def test_the_versions_can_be_chosen_by_name():
    assert VERSIONS == {"plain": PLAIN, "solver": SOLVER, "solver2": SOLVER2}


def test_the_second_solver_version_differs_only_in_how_it_books():
    assert SOLVER.tools["book"] is BOOK
    assert SOLVER2.tools["book"] is BOOK_FOUND
    assert {**SOLVER2.tools, "book": BOOK} == SOLVER.tools
    assert SOLVER2.system_prompt == SOLVER.system_prompt


def test_plain_version_reads_calendars_itself():
    assert set(PLAIN.tools) == {"get_busy", "book", "give_up"}
    assert PLAIN.system_prompt == SYSTEM_PROMPT


def test_solver_version_uses_find_slots():
    assert set(SOLVER.tools) == {"find_slots", "book", "give_up"}
    assert SOLVER.system_prompt == SOLVER_PROMPT


def test_each_prompt_names_only_tools_that_version_has():
    for version in VERSIONS.values():
        other_tools = {"get_busy", "find_slots"} - set(version.tools)
        for tool in other_tools:
            assert tool not in version.system_prompt
        assert "book" in version.system_prompt
        assert "give_up" in version.system_prompt
