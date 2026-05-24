# 01 — Engineering Standards

**Status:** Authored
**Source guardrails:** [`AGENTS.md`](../../AGENTS.md) sections *Technical Philosophy*, *Engineering Standards*
**Related tickets:** T00-07 (this handbook), T01-02 (linter enforcement), T01-12 (developer tooling)

---

## 1. The Non-Negotiable Rules

From `AGENTS.md`:

1. **All code functions MUST remain under 60 lines.** Counted in the body of the function, excluding the signature, decorators, and the closing brace. Comments and blank lines count. If your function is 61 lines, it is too long.
2. **Readability over cleverness.** A junior engineer who joined last week should be able to read a function and explain what it does in one sentence.
3. **Explicit logic over hidden magic.** Behavior must be visible at the call site or one click away.
4. **Maintainability over premature optimization.** You may write the boring version. You may not write the clever version until the boring version is measurably slow.

These rules are enforced by linting (T01-02) once that ticket ships. Until then, enforce them in code review.

## 2. Priorities, in Order

From `AGENTS.md` *Technical Philosophy*:

1. Maintainability
2. Explainability
3. Traceability
4. Scalability
5. Automation
6. UI polish

When two priorities conflict, the higher-numbered one yields. A clever automated refactor that hurts traceability is wrong. A scalable design that is unmaintainable is wrong.

## 3. The 60-Line Rule, in Practice

### Why 60?

Sixty lines is roughly one screen of code at a normal editor zoom. A function you cannot see in one screen is a function whose control flow you are reconstructing from memory. iPermit's core promise — *deterministic, explainable permit evaluation* — depends on every engineer being able to read the rule engine top to bottom without scrolling.

### What counts toward the 60 lines?

Every line in the function body: code, comments, blank lines, closing brackets that are alone on a line. The signature and decorators do not count.

```python
@audit_logged                          # decorator — does not count
def evaluate_rule(rule, project):      # signature — does not count
    # everything below this line counts toward 60
    ...
```

### What to do when a function approaches 60 lines

Treat 50 lines as your yellow line and 55 as your red. When you cross 50:

1. **Stop and re-read the function.** Most over-long functions are doing two things. Name the two things.
2. **Extract the inner thing into a helper** with a verb-noun name (`normalize_jurisdiction_id`, `pick_effective_version`). The helper should be testable in isolation.
3. **If you can't name the helper cleanly, the split is wrong.** Refactor the data structure instead. Frequently, a too-long function is a symptom of a missing model or a dict that should be a dataclass.
4. **Do not extract a one-line helper just to satisfy the limit.** A 61-line function with one line shoved into `_helper()` is worse than a 61-line function. Fix the structure or refactor the data.

### Anti-patterns to avoid

- **`utils.py` dumping ground.** A helper that doesn't belong to a named domain probably needs its own module or shouldn't exist.
- **Boolean parameters that switch behavior.** `do_thing(project, deep=True)` becomes `do_thing_shallow` and `do_thing_deep`. Two short functions beat one long branching one.
- **Multi-purpose helpers that take an enum to pick what to do.** Same fix: split.

## 4. Function Naming

Functions complete one clear task. Their names should reflect that:

- **Verb-first for actions:** `evaluate_rule`, `load_benchmark`, `resolve_jurisdiction_conflict`.
- **`is_`/`has_`/`should_` for predicates:** `is_effective_on`, `has_known_unknowns`, `should_short_circuit`.
- **Noun for accessors that return a value with no side effects:** `effective_version`, `parent_jurisdiction`.
- **No vague verbs.** Ban `process`, `handle`, `do`, `manage`, `run` as the only verb. `process_project` is unfalsifiable; `evaluate_project_against_rules` says what happens.

A name should let an engineer guess the function's signature and return type before opening it.

## 5. "Explicit Logic Over Hidden Magic" — What This Means

iPermit's rules engine must remain *explainable*. That extends to the engineering practices around it.

Concretely:

- **No metaclass tricks.** No dynamic attribute lookup that defeats grep. If a field name appears in a rule object, you should be able to grep that field name and find every place it is read.
- **No reflection-based dispatch in the rules engine.** Trigger operators are a closed set (`=`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `intersects`, `exists`, `in`, `not_in` — see [`docs/specs/rule-object.md`](../specs/rule-object.md) §7). Implementing them is a `match` statement, not a registry.
- **No string-built code paths.** `eval`, `exec`, and templated SQL are out. Parameterize.
- **Configuration is data, not code.** A YAML file is configuration. A Python file with `if env == 'prod'` is code masquerading as configuration. Prefer the former.
- **Decorators are fine if they add cross-cutting concerns (logging, audit) without changing the function's contract.** A decorator that silently retries, swallows exceptions, or rewrites arguments is hidden magic and is not fine.

The test: a new engineer should be able to set a breakpoint, step through one permit evaluation, and see every decision the engine made. If a decision happens via a registered handler, a dispatched method, or a string-keyed dict whose keys come from a config file three modules away, the engine has failed the explainability bar.

## 6. Where Abstraction Is Allowed

The 60-line rule is not a license to inline everything. The rule is: extract when the extraction earns its keep.

An extraction earns its keep when:

- The extracted helper is called from more than one place, **or**
- The extracted helper has a name that is more descriptive than its body, **or**
- The extracted helper is independently testable (and you will write the test).

If none of those are true, the inline version is better.

## 7. Reading Order for a New Engineer

When you clone the repo, read in this order:

1. [`/AGENTS.md`](../../AGENTS.md) — the whole thing.
2. [`/docs/roadmap.md`](../roadmap.md) — skim to see what exists and what doesn't.
3. This handbook section.
4. [`docs/engineering-handbook/02-repository-strategy.md`](./02-repository-strategy.md).
5. [`docs/specs/rule-object.md`](../specs/rule-object.md) — the most stable spec.

After that, follow your ticket's "Related tickets" links.

## 8. Code Review Checklist

For any PR touching `services/rules-engine/`, `packages/shared-schemas/`, or `rules/`:

- [ ] Every changed function is under 60 lines (body).
- [ ] No new use of `eval`, `exec`, or dynamic attribute dispatch.
- [ ] Every new public function has a name that telegraphs its signature.
- [ ] No new boolean switching parameters; split into two functions instead.
- [ ] No new "manager" / "handler" / "processor" classes without a justification in the PR description.
- [ ] If the change touches rule evaluation logic, a benchmark project (T00-06) covers the change.
- [ ] If the change touches a published or effective rule, the analyst review workflow (T00-09 / T08-04) was followed — engineering-only PRs do not move rules between `published/` and `effective/`.

The benchmark and workflow items become enforceable as the owning tickets ship; until then they are reviewer expectations.
