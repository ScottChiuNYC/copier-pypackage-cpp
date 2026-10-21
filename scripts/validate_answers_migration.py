"""Exercise a real legacy copy, Git rename, pinned update, and repeat update.

Requires Copier 9.19.1 and PyYAML; performs no builds or numerical tests.
By default uses this checkout and a disposable project. --project may instead
identify an empty experimental Git checkout. Never use a production checkout.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "f80f292ceeaa86dc1e1caa430da538ecf0f4078b"
OLD = ".copier-answers.yml"
NEW = ".copier-answers.pypackage-cpp.yml"


def run(*args, cwd=None):
    command = [str(arg) for arg in args]
    print(f"[{cwd or Path.cwd()}] {shlex.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    print(result.stdout, end="", flush=True)
    result.check_returncode()
    return result.stdout.strip()


def verify(project, before, source, commit, expected_readme, implementation, infrastructure):
    answers = yaml.safe_load((project / NEW).read_text(encoding="utf-8"))
    assert answers["_src_path"] == source, answers
    assert answers["_commit"] == commit, answers
    assert {k: v for k, v in answers.items() if k != "_commit"} == {
        k: v for k, v in before.items() if k != "_commit"}
    assert not (project / OLD).exists()
    assert list(project.glob(".copier-answers*.y*ml")) == [project / NEW]
    assert (project / "cpp/src/playground_specific.cpp").read_bytes() == implementation
    assert (project / "README.md").read_bytes() == expected_readme
    for path, content in infrastructure.items():
        assert (project / path).read_bytes() == content, path
    assert not list(project.rglob("*.rej"))
    for path in run("git", "ls-files", cwd=project).splitlines():
        if (project / path).is_file():
            content = (project / path).read_bytes()
            assert b"<<<<<<<" not in content and b">>>>>>>" not in content, path
    return answers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--source", default=str(ROOT))
    parser.add_argument("--target", default="HEAD")
    args = parser.parse_args()
    source = args.source
    target = args.target
    if target == "HEAD":
        target = run("git", "rev-parse", "HEAD", cwd=ROOT)
    copier = [sys.executable, "-m", "copier"]
    assert run(*copier, "--version").split()[-1] == "9.19.1"
    with tempfile.TemporaryDirectory(prefix="answers-migration-") as temporary:
        # Git expands Windows 8.3 TEMP paths; use the same canonical path.
        work = Path(temporary).resolve()
        if source == str(ROOT):
            # PR CI checks out a detached synthetic merge commit. Make that
            # exact commit reachable in a disposable mirror on every platform.
            mirror = work / "template.git"
            run("git", "clone", "--mirror", ROOT, mirror)
            run("git", "fetch", ROOT, f"{target}:refs/heads/migration-target", cwd=mirror)
            source = str(mirror)
        project = args.project.resolve() if args.project else work / "project"
        project.mkdir(parents=True, exist_ok=True)
        assert not any(p.name != ".git" for p in project.iterdir()), "Project must be empty"
        if not (project / ".git").exists():
            run("git", "init", "-b", "experiment/answers-file-migration", cwd=project)
        assert not run("git", "ls-files", cwd=project)
        run("git", "config", "user.name", "Copier Migration Experiment", cwd=project)
        run("git", "config", "user.email", "copier-experiment@example.com", cwd=project)
        run("git", "config", "core.autocrlf", "false", cwd=project)
        data = {"project_name": "Playground", "project_slug": "playground",
                "module_name": "playground", "description": "Copier answers migration experiment",
                "author_name": "Copier Migration Experiment",
                "author_email": "copier-experiment@example.com", "version": "0.1.0",
                "vcpkg_port_name": "playground-core", "python_version": ">=3.12",
                "cmake_min_version": "3.25", "cpp_standard": "17"}
        flags = [item for key, value in data.items() for item in ("-d", f"{key}={value}")]
        run(*copier, "copy", "--defaults", "--vcs-ref", BASELINE,
            *flags, source, project)
        # Use a fresh rendering solely as the expected README, so independently
        # added upstream documentation is retained in merge-ref CI checkouts.
        expected_project = work / "expected-target"
        run(*copier, "copy", "--defaults", "--vcs-ref", target,
            *flags, source, expected_project)
        generated_readme = (expected_project / "README.md").read_bytes()
        section = b"\n## Playground-specific work\n\nKeep this project-specific section during Copier updates.\n"
        expected_readme = generated_readme + section
        before = yaml.safe_load((project / OLD).read_text(encoding="utf-8"))
        # Copier uses git describe, rather than necessarily recording the raw SHA.
        if Path(source).is_dir():
            assert run("git", "rev-parse", before["_commit"], cwd=source) == BASELINE
        else:
            assert run("git", "rev-parse", before["_commit"], cwd=ROOT) == BASELINE
        assert before["_src_path"] == source
        assert all(before[key] == value for key, value in data.items()), before
        assert not (project / NEW).exists()
        run("git", "add", ".", cwd=project)
        run("git", "commit", "-m", "Generate old-style project from pinned template baseline", cwd=project)
        baseline = run("git", "rev-parse", "HEAD", cwd=project)
        source_file = project / "cpp/src/playground_specific.cpp"
        source_file.write_text("// Project-specific implementation retained across Copier updates.\n"
                               "int playground_answer() { return 42; }\n", encoding="utf-8", newline="\n")
        readme_file = project / "README.md"
        with readme_file.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n## Playground-specific work\n\nKeep this project-specific section during Copier updates.\n")
        run("git", "add", ".", cwd=project)
        run("git", "commit", "-m", "Add project implementation and generated README customization", cwd=project)
        implementation = source_file.read_bytes()
        readme = readme_file.read_bytes()
        # Every other generated file must be byte-for-byte unchanged, including
        # all CMake/vcpkg/Python/pybind11/Actions and docs/development exclusions.
        infrastructure = {path: (project / path).read_bytes()
                          for path in run("git", "ls-files", cwd=project).splitlines()
                          if path not in (OLD, "README.md", "cpp/src/playground_specific.cpp")}
        original_answers = (project / OLD).read_bytes()
        run("git", "mv", OLD, NEW, cwd=project)
        assert (project / NEW).read_bytes() == original_answers
        run("git", "commit", "-m", "Rename Copier answers without changing provenance", cwd=project)
        run(*copier, "update", "--defaults", "-a", NEW, "--vcs-ref", target, cwd=project)
        # A local section appended beside an upstream README edit can conflict.
        # Resolve only this known fixture conflict after checking both Git stages;
        # never accept arbitrary conflicts or silently drop either side.
        conflicts = run("git", "diff", "--name-only", "--diff-filter=U", cwd=project).splitlines()
        if conflicts:
            assert conflicts == ["README.md"], conflicts
            ours = run("git", "show", ":2:README.md", cwd=project) + "\n"
            theirs = run("git", "show", ":3:README.md", cwd=project) + "\n"
            assert ours.encode() == readme
            assert theirs.encode() == generated_readme
            print("Explicit README conflict resolution: retain updated Copier instructions AND the entire local section.", flush=True)
            readme_file.write_bytes(expected_readme)
            run("git", "add", "README.md", cwd=project)
        # Copier's recorded ref is git describe of the target, verified to SHA.
        target_record = yaml.safe_load((project / NEW).read_text(encoding="utf-8"))["_commit"]
        assert run("git", "rev-parse", target_record, cwd=ROOT) == target
        verify(project, before, source, target_record, expected_readme, implementation, infrastructure)
        run("git", "merge-base", "--is-ancestor", baseline, "HEAD", cwd=project)
        assert set(run("git", "diff", "HEAD", "--name-only", cwd=project).splitlines()) == {NEW, "README.md"}
        run("git", "add", ".", cwd=project)
        run("git", "commit", "-m", "Update renamed answers to pinned candidate template", cwd=project)
        migration = run("git", "rev-parse", "HEAD", cwd=project)
        run(*copier, "update", "--defaults", "-a", NEW, "--vcs-ref", target, cwd=project)
        verify(project, before, source, target_record, expected_readme, implementation, infrastructure)
        assert not run("git", "status", "--porcelain", "--untracked-files=all", cwd=project)
        assert run("git", "rev-parse", "HEAD", cwd=project) == migration
        print(json.dumps({"verdict": "PASS", "baseline_commit": baseline,
                          "migration_commit": migration, "template_candidate": target,
                          "old_template_record": before["_commit"], "new_template_record": target_record,
                          "source": source, "branch": run("git", "branch", "--show-current", cwd=project),
                          "preserved_other_files": len(infrastructure), "second_update_clean": True, "resolved_conflicts": conflicts}, indent=2))


if __name__ == "__main__":
    main()
