# Interactive Shell Configuration Guard

## Problem

Dotbins-generated Bash and Zsh scripts serve two purposes: they add the
platform-specific binary directory to `PATH`, and they run each tool's custom
shell initialization. The generator currently performs both operations whenever
the script is sourced.

Non-interactive scripts may source the generated file only to make Dotbins
binaries available. In that context, interactive initializers can emit warnings
or fail. For example, Atuin invokes Bash's `bind` builtin even though Readline is
not active, producing `bind: warning: line editing not enabled`.

## Design

The generated Bash and Zsh scripts will continue to update `PATH`
unconditionally. When tool-specific shell code exists, the generator will wrap
the complete tool-configuration section in a single interactive-shell guard:

```bash
export PATH="$HOME/.dotbins/$_os/$_arch/bin:$PATH"

if [[ $- == *i* ]]; then
    # Tool-specific configurations
    # ...
fi
```

The existing per-tool `command -v` guards remain inside this outer guard. Fish,
Nushell, and PowerShell generation is unchanged because the reported bug and the
shared Bash/Zsh generator branch do not apply to them.

This avoids tool-specific exceptions, preserves a single integration script per
shell, and keeps non-interactive `PATH` use supported without running prompt,
completion, alias, or Readline setup.

## Testing

Regression tests will generate a Bash integration script containing observable
tool-specific shell code and source it from non-interactive Bash. They will
verify that:

- the Dotbins binary directory is added to `PATH`;
- tool-specific shell code is not executed; and
- the generated Bash and Zsh scripts contain the outer interactive guard while
  shell code remains nested within it.

Existing shell-generation tests must continue to pass. The full suite will also
be run where its external release fixtures are available; missing fixture data
will be reported separately from product failures.

## Compatibility

Interactive users retain the current behavior. Non-interactive users still gain
the required `PATH` entry but will no longer receive aliases, completions,
prompt hooks, or other interactive-only shell configuration. This is the
intended contract of the generated tool-specific section.
