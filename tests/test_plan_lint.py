from nmg2_tools.plan_lint import lint_text, load_owners

CLEAN_TASK = """\
## T0-1: Build the thing
Repo: gearmulator
Targets: axiomantic/gearmulator
Files:
  - gearmulator: g2Lib/t0_foo.cpp
Depends: none
Check:
```
ctest --test-dir build -R t0_foo --no-tests=error -- --extra
```
"""


def _failure_names(failures):
    return {f.split(":", 1)[0] for f in failures}


def test_clean_fragment_passes():
    failures = lint_text(CLEAN_TASK)
    assert failures == []


def test_c1_untracked_r_name_fails():
    text = """\
## T1-1: Untracked test
Check:
```
ctest --test-dir build -R random_untracked_name --no-tests=error --
```
"""
    failures = lint_text(text)
    assert "PLAN-C1" in _failure_names(failures)


def test_c2_unregistered_name_against_build_tree_fails(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "CTestTestfile.cmake").write_text('add_test(t0_foo "true")\n')

    text = """\
## T0-9: Registered check
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_bar.cpp
Check:
```
ctest --test-dir build -R t0_bar --no-tests=error --
```
"""
    failures = lint_text(
        text,
        build_dirs={"gearmulator": str(build_dir)},
        complete_ids={"T0-9"},
    )
    assert "PLAN-C2" in _failure_names(failures)


def test_c2_missing_build_tree_for_complete_task_is_hard_failure():
    text = """\
## T0-9: Registered check
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_bar.cpp
Check:
```
ctest --test-dir build -R t0_bar --no-tests=error --
```
"""
    failures = lint_text(text, build_dirs={}, complete_ids={"T0-9"})
    assert "PLAN-C2" in _failure_names(failures)


def test_c3_missing_no_tests_error_fails():
    text = """\
## T0-2: Bad ctest form
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_bad.cpp
Check:
```
ctest --test-dir build -R t0_bad --
```
"""
    failures = lint_text(text)
    assert "PLAN-C3" in _failure_names(failures)


def test_c4_missing_dash_dash_forwarding_fails():
    text = """\
## T0-3: No forwarding
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_noforward.cpp
Check:
```
ctest --test-dir build -R t0_noforward --no-tests=error
```
"""
    failures = lint_text(text)
    assert "PLAN-C4" in _failure_names(failures)


def test_c5_unlisted_target_repository_fails():
    text = """\
## T0-4: Bad target
Repo: gearmulator
Targets: someorg/not-listed
Files:
  - gearmulator: g2Lib/t0_target.cpp
Check:
```
ctest --test-dir build -R t0_target --no-tests=error --
```
"""
    failures = lint_text(text)
    assert "PLAN-C5" in _failure_names(failures)


def test_c6_untracked_cmake_target_fails():
    text = """\
## T0-5: Bad build target
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_buildtarget.cpp
Check:
```
cmake --build build --target unclaimed_target
ctest --test-dir build -R t0_buildtarget --no-tests=error --
```
"""
    failures = lint_text(text)
    assert "PLAN-C6" in _failure_names(failures)


def test_c7_unowned_shared_path_fails():
    text = """\
## T0-6: First claimant
Repo: gearmulator
Files:
  - gearmulator: g2Lib/shared_file.cpp
Check:
asserts the shared file compiles

## T0-7: Second claimant
Repo: gearmulator
Files:
  - gearmulator: g2Lib/shared_file.cpp
Check:
asserts the shared file compiles again
"""
    failures = lint_text(text, owners={})
    assert "PLAN-C7" in _failure_names(failures)


def test_c7_owned_shared_path_passes():
    text = """\
## T0-6: First claimant
Repo: gearmulator
Files:
  - gearmulator: g2Lib/shared_file.cpp
Check:
asserts the shared file compiles

## T0-7: Second claimant
Repo: gearmulator
Files:
  - gearmulator: g2Lib/shared_file.cpp
Check:
asserts the shared file compiles again
"""
    failures = lint_text(
        text,
        owners={("gearmulator", "source/nord/g2/g2Lib/shared_file.cpp"): "T0-6"},
    )
    assert "PLAN-C7" not in _failure_names(failures)


def test_c8_build_only_check_fails():
    text = """\
## T0-8: No verifiable check
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_buildonly.cpp
Check:
```
cmake --build build --target t0_buildonly
```
"""
    failures = lint_text(text)
    assert "PLAN-C8" in _failure_names(failures)


def test_c9_prose_depends_fails():
    text = """\
## T0-10: Bad depends
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_depends.cpp
Depends: whatever finishes first
Check:
```
ctest --test-dir build -R t0_depends --no-tests=error --
```
"""
    failures = lint_text(text)
    assert "PLAN-C9" in _failure_names(failures)


def test_c9_valid_depends_forms_pass():
    text = """\
## T0-11: Good depends
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_gooddepends.cpp
Depends: T0-1, T0-2 to T0-5
Check:
```
ctest --test-dir build -R t0_gooddepends --no-tests=error --
```
"""
    failures = lint_text(text)
    assert "PLAN-C9" not in _failure_names(failures)


def test_reverse_created_test_never_invoked_fails():
    text = """\
## T0-12: Orphan test file
Repo: gearmulator
Files:
  - gearmulator: g2Lib/t0_orphan.cpp
Check:
asserts something unrelated
"""
    failures = lint_text(text)
    assert "PLAN-REVERSE" in _failure_names(failures)


def test_load_owners_parses_starter_file():
    owners = load_owners(
        __import__("pathlib").Path(__file__).parent.parent
        / "nmg2_tools"
        / "testdata"
        / "owners.tsv"
    )
    assert ("gearmulator", "source/nord/g2/g2Lib/g2_patch.cpp") in owners
