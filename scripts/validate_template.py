"""Validate Copier copy, tagged update with local edits, and the resulting build."""
from pathlib import Path
import argparse
import json
import io
import subprocess
import tarfile
import os
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template/scripts"))
from bootstrap import run, tool_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, help="Keep generated projects and build results in this empty directory.")
    args = parser.parse_args()
    tools = ROOT / ".dev-tools"
    selected = tools / "vcpkg-root.txt"
    if selected.exists():
        os.environ["VCPKG_ROOT"] = selected.read_text(encoding="utf-8")
    py, env, _ = tool_environment(ROOT / "template", tools)
    if Path(sys.prefix).resolve() != (tools / "venv").resolve():
        # Preserve the unactivated runner used by generated-project workflows.
        env["TEMPLATE_RUNNER_PYTHON"] = sys.executable
        env["TEMPLATE_RUNNER_PATH"] = os.environ["PATH"]
        run([py, __file__, *sys.argv[1:]], env=env)
        return
    temporary = tempfile.TemporaryDirectory(prefix="template-validation-") if args.work_dir is None else None
    work = (Path(temporary.name) if temporary else args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if any(work.iterdir()):
        raise SystemExit("--work-dir must be empty; validation will not overwrite existing projects.")
    copier = [py, "-m", "copier"]
    run([py, ROOT / "scripts/validate_answers_migration.py"], env=env)
    import yaml
    answers_file = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))["_answers_file"]
    # Exercise real Git tags without publishing test tags or changing the source repo.
    fixture = work / "template"
    fixture.mkdir()
    for name in ("copier.yml", "template"):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, fixture / name, ignore=shutil.ignore_patterns(".dev-tools", "__pycache__", "build", "dist"))
        else:
            shutil.copy2(source, fixture / name)
    run(["git", "init"], cwd=fixture)
    for key, value in (("user.name", "Template Validation"), ("user.email", "template@example.com"), ("core.autocrlf", "false")):
        run(["git", "config", key, value], cwd=fixture)
    run(["git", "add", "."], cwd=fixture)
    run(["git", "commit", "-m", "Template v1"], cwd=fixture)
    run(["git", "tag", "v1.0.0"], cwd=fixture)
    default = work / "defaults"
    run([*copier, "copy", "--defaults", "--vcs-ref", "v1.0.0", fixture, default], env=env)
    python_package = (default / "pyproject.toml").exists()
    project = work / "sample"
    data = ["-d", "project_name=CI Sample", "-d", "project_slug=ci_sample"]
    if python_package:
        data += ["-d", "module_name=ci_sample"]
    custom_data = [*data, "-d", "vcpkg_port_name=ci-packaged-library", "-d", "version=1.2.3rc1"]
    run([*copier, "copy", "--defaults", "--vcs-ref", "v1.0.0", *custom_data, fixture, project], env=env)
    import yaml
    answers = yaml.safe_load((project / answers_file).read_text(encoding="utf-8"))
    assert answers["_commit"] == "v1.0.0"
    assert answers["vcpkg_port_name"] == "ci-packaged-library"
    assert (project / "vcpkg-ports/ci-packaged-library/portfile.cmake").exists()
    workflow = (project / ".github/workflows/build-and-test.yml").read_text(encoding="utf-8")
    assert "${{ matrix.os }}" in workflow and "{%" not in workflow and "cookiecutter." not in workflow
    acceptance = (ROOT / ".github/workflows/template-acceptance.yml").read_text(encoding="utf-8")
    for content, command in ((acceptance, "python scripts/validate_template.py"), (workflow, "python scripts/validate.py" + (" --wheel" if python_package else ""))):
        ci = yaml.load(content, Loader=yaml.BaseLoader)
        assert {"push", "pull_request", "workflow_dispatch"} <= set(ci["on"])
        job = ci["jobs"]["validate"]
        assert set(job["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-2022"}
        assert [step["run"] for step in job["steps"] if "run" in step] == ["python scripts/bootstrap.py", command]
    # Generated build CI must ignore docs/development-only changes, not mixed/code changes.
    # Template acceptance itself remains a normal push/PR/manual validation workflow.
    generated_ci = yaml.load(workflow, Loader=yaml.BaseLoader)
    assert generated_ci["on"]["push"]["paths-ignore"] == ["docs/development/**"]
    assert generated_ci["on"]["pull_request"]["paths-ignore"] == ["docs/development/**"]
    assert not generated_ci["on"]["workflow_dispatch"]
    template_ci = yaml.load(acceptance, Loader=yaml.BaseLoader)
    assert not template_ci["on"]["push"] and not template_ci["on"]["pull_request"]
    assert "paths-ignore" not in template_ci["on"]
    assert "docs/development/" in (project / "README.md").read_text(encoding="utf-8")

    config = json.loads((project / "vcpkg-configuration.json").read_text(encoding="utf-8"))
    assert config["default-registry"]["repository"] == "https://github.com/microsoft/vcpkg"
    assert config["overlay-ports"] == ["vcpkg-ports"]
    assert "vcpkg_fixup_pkgconfig(SKIP_CHECK)" in (project / "vcpkg-ports/gtest/portfile.cmake").read_text(encoding="utf-8")
    assert not (project / ".git").exists() and not (project / "copier.yml").exists()
    readme = project / "README.md"
    documented = readme.read_text(encoding="utf-8")
    assert "-DVCPKG_TARGET_TRIPLET=x64-linux" in documented
    assert "-DVCPKG_TARGET_TRIPLET=x64-windows" in documented
    readme.write_text(readme.read_text(encoding="utf-8") + "\nLocal project note.\n", encoding="utf-8", newline="\n")
    run(["git", "init"], cwd=project)
    for key, value in (("user.name", "Template Validation"), ("user.email", "template@example.com"), ("core.autocrlf", "false")):
        run(["git", "config", key, value], cwd=project)
    run(["git", "add", "."], cwd=project)
    run(["git", "commit", "-m", "Generated project with local edits"], cwd=project)
    template_readme = next((fixture / "template").glob("README.md*"))
    template_readme.write_text("Template update marker.\n\n" + template_readme.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (fixture / "template/update-marker.txt").write_text("Tagged update passed.\n", encoding="utf-8", newline="\n")
    run(["git", "add", "."], cwd=fixture)
    run(["git", "commit", "-m", "Template v2"], cwd=fixture)
    run(["git", "tag", "v1.1.0"], cwd=fixture)
    run([*copier, "update", "--defaults", "-a", answers_file, "--vcs-ref", "v1.1.0"], cwd=project, env=env)
    updated = yaml.safe_load((project / answers_file).read_text(encoding="utf-8"))
    assert updated["_commit"] == "v1.1.0"
    assert "Local project note." in readme.read_text(encoding="utf-8")
    assert "Template update marker." in readme.read_text(encoding="utf-8")
    assert (project / "update-marker.txt").read_text(encoding="utf-8") == "Tagged update passed.\n"
    assert not list(project.rglob("*.rej"))
    # Invalid identifiers must fail at question validation, before writing a project.
    bad = ["-d", "module_name=not-valid"] if python_package else ["-d", "project_slug=not-valid"]
    result = subprocess.run([str(x) for x in [*copier, "copy", "--defaults", *bad, fixture, work / "invalid"]], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode != 0 and "Use a valid identifier." in result.stdout, result.stdout
    print(f"Identifier rejection passed (expected exit {result.returncode}).", flush=True)
    # Use the generated project's own tools and the workflow's original Python/PATH.
    # Inheriting the template tool PATH would hide Windows executable lookup failures.
    runner = os.environ.get("TEMPLATE_RUNNER_PYTHON", sys.executable)
    project_env = os.environ.copy()
    project_env["PATH"] = os.environ.get("TEMPLATE_RUNNER_PATH", os.environ["PATH"])
    project_env.pop("PROJECT_DEV_TOOLS", None)
    run([runner, project / "scripts/bootstrap.py", "--vcpkg-root", env["VCPKG_ROOT"]], cwd=project, env=project_env)
    run([runner, project / "scripts/validate.py", *(["--wheel"] if python_package else [])], cwd=project, env=project_env)
    # Upgrade a real pre-packaging master revision using isolated Git tags.
    old = work / "previous-template"
    old.mkdir()
    archive = subprocess.check_output(["git", "archive", "4eec4ac0ffb8796d7e710a91b81e04dac79def60", "copier.yml", "template"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:
        files.extractall(old, filter="data")
    run(["git", "init"], cwd=old)
    for key, value in (("user.name", "Template Validation"), ("user.email", "template@example.com"), ("core.autocrlf", "false")):
        run(["git", "config", key, value], cwd=old)
    run(["git", "add", "."], cwd=old)
    run(["git", "commit", "-m", "Previous master without packaging"], cwd=old)
    run(["git", "tag", "v2.0.0"], cwd=old)
    upgraded = work / "upgraded"
    run([*copier, "copy", "--defaults", "--vcs-ref", "v2.0.0", *data, old, upgraded], env=env)
    assert not (upgraded / "cmake/LibraryConfig.cmake.in").exists()
    user_file = upgraded / "user-notes.txt"
    user_file.write_text("Keep unrelated user work.\n", encoding="utf-8")
    source = upgraded / ("cpp/src/hello.cpp" if python_package else "src/example.cpp")
    source.write_text(source.read_text(encoding="utf-8") + "\n// Retain this user source edit.\n", encoding="utf-8")
    before = yaml.safe_load((upgraded / ".copier-answers.yml").read_text(encoding="utf-8"))
    run(["git", "init"], cwd=upgraded)
    for key, value in (("user.name", "Template Validation"), ("user.email", "template@example.com"), ("core.autocrlf", "false")):
        run(["git", "config", key, value], cwd=upgraded)
    run(["git", "add", "."], cwd=upgraded)
    run(["git", "commit", "-m", "Previous project with unrelated user edits"], cwd=upgraded)
    run(["git", "mv", ".copier-answers.yml", answers_file], cwd=upgraded)
    run(["git", "commit", "-m", "Migrate template answers filename"], cwd=upgraded)
    shutil.rmtree(old / "template")
    shutil.copytree(ROOT / "template", old / "template", ignore=shutil.ignore_patterns(".dev-tools", "__pycache__", "build", "dist"))
    shutil.copy2(ROOT / "copier.yml", old / "copier.yml")
    run(["git", "add", "."], cwd=old)
    run(["git", "commit", "-m", "Add packaging infrastructure"], cwd=old)
    run(["git", "tag", "v2.1.0"], cwd=old)
    run([*copier, "update", "--defaults", "-a", answers_file, "--vcs-ref", "v2.1.0"], cwd=upgraded, env=env)
    after = yaml.safe_load((upgraded / answers_file).read_text(encoding="utf-8"))
    assert after["_commit"] == "v2.1.0"
    assert all(after[key] == value for key, value in before.items() if key != "_commit")
    assert user_file.read_text(encoding="utf-8") == "Keep unrelated user work.\n"
    assert "// Retain this user source edit." in source.read_text(encoding="utf-8")
    assert (upgraded / "cmake/LibraryConfig.cmake.in").exists()
    assert (upgraded / "vcpkg-ports" / after["vcpkg_port_name"] / "portfile.cmake").exists()
    assert not list(upgraded.rglob("*.rej"))
    run([py, upgraded / "scripts/validate_vcpkg.py"], cwd=upgraded, env=env)
    print("Previous-master Copier packaging update passed: answers, user file/source edits, and independent consumer.", flush=True)
    print("Template validation passed: defaults, custom answers, tagged update, retained local edits, identifier validation, and actual build/tests.")
    if temporary:
        temporary.cleanup()


if __name__ == "__main__":
    main()
