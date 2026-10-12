from schedagent.agent import SOLVER_PROMPT, SYSTEM_PROMPT
from schedagent.versions import PLAIN, SOLVER, VERSIONS


def test_there_are_two_versions_to_compare():
    assert VERSIONS == {"plain": PLAIN, "solver": SOLVER}


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
