# Interactive Shell Configuration Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Dotbins binaries available to non-interactive Bash and Zsh scripts without running interactive-only tool initialization.

**Architecture:** Preserve the existing unconditional platform and architecture detection and `PATH` export. Generate the existing tool-configuration section once, then indent it beneath a single `[[ $- == *i* ]]` guard for Bash and Zsh only; other shell generators remain unchanged.

**Tech Stack:** Python 3.10+, pytest, generated Bash/Zsh shell scripts

---

### Task 1: Reproduce non-interactive tool initialization

**Files:**
- Modify: `tests/test_utils.py`

- [ ] **Step 1: Add imports for subprocess execution and shell generation**

Import `subprocess`, `ToolConfig`, and `_format_shell_instructions` in
`tests/test_utils.py`.

- [ ] **Step 2: Write a failing runtime regression test**

Add a test that constructs a `ToolConfig` for a command guaranteed to exist,
with Bash shell code that creates a marker file. Generate and write `bash.sh`,
source it using `bash -c` (non-interactive), and assert that the marker was not
created while the generated Dotbins binary path appears in the subprocess
`PATH` output. Assert the complete expected
`tools_dir/<platform>/<architecture>/bin` path, not merely the tools directory.

```python
def test_noninteractive_bash_only_updates_path(tmp_path: Path) -> None:
    marker = tmp_path / "configured"
    tools_dir = tmp_path / "tools"
    tool = ToolConfig(
        tool_name="sh",
        repo="owner/repo",
        shell_code={"bash": f"touch {marker}"},
    )
    script = tmp_path / "bash.sh"
    script.write_text(_format_shell_instructions(tools_dir, "bash", {"sh": tool}))

    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s" "$PATH"', "bash", str(script)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert not marker.exists()
    assert str(tools_dir / "linux" / "amd64" / "bin") in result.stdout
```

- [ ] **Step 3: Write a failing generated-structure test**

Parameterize Bash and Zsh and assert their tool-specific section begins below
`if [[ $- == *i* ]]; then` and is indented inside it. Add an interactive Bash
runtime assertion using `bash --noprofile --norc -i` to verify that the marker
file is created when Readline is active.

- [ ] **Step 4: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_utils.py -k 'noninteractive_bash or interactive_shell' -v
```

Expected: the runtime test fails because the marker file is created, and the
structure test fails because no outer interactive guard exists.

### Task 2: Guard Bash and Zsh tool configuration

**Files:**
- Modify: `dotbins/utils.py:210-228`

- [ ] **Step 1: Generate the tool section separately**

Store the return value of `_add_shell_code_to_script(...)` instead of appending
it directly to `base_script`.

- [ ] **Step 2: Wrap nonempty tool configuration in one interactive guard**

Use `textwrap.indent` to nest the stripped tool section beneath the guard:

```python
shell_code = _add_shell_code_to_script(tools, shell, if_start, if_end)
if shell_code:
    base_script += "\nif [[ $- == *i* ]]; then\n"
    base_script += textwrap.indent(shell_code.strip(), "    ")
    base_script += "\nfi\n"
```

- [ ] **Step 3: Run the focused tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_utils.py -k 'noninteractive_bash or interactive_shell' -v
```

Expected: all selected tests pass.

- [ ] **Step 4: Run shell-generation and unit regression tests**

Run:

```bash
uv run pytest tests/test_utils.py tests/test_e2e.py::test_tool_shell_code_in_shell_scripts -v
```

Expected: all tests pass.

### Task 3: Validate and publish

**Files:**
- Modify if generated documentation changes are required by repository checks.

- [ ] **Step 1: Run formatting, lint, and available tests**

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest --ignore=tests/test_release_patterns.py
```

Expected: all commands pass. The excluded release-pattern file requires fixture
JSON data absent from a fresh worktree; document this known baseline limitation.

- [ ] **Step 2: Review the final diff**

Run `git diff --check`, `git status --short`, and inspect the complete diff for
scope and accidental generated files.

- [ ] **Step 3: Commit the implementation**

Stage only `dotbins/utils.py`, `tests/test_utils.py`, and any intentionally
updated plan/spec files, then commit with a terse fix description.

- [ ] **Step 4: Push and open a draft PR**

Push `agent/guard-interactive-shell-config` to `origin` and create a draft PR
against the repository's default branch. The PR body must explain the root
cause, behavior change, user impact, validation, and absent fixture limitation.
