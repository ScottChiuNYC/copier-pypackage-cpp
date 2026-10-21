# Copier Python Package with C++ Component

Poetry packaging, a C++17 static core and a pybind11 extension. This repository is migrated in place from Cookiecutter; it now uses the `copier-` repository name.

## Generate and update a project

```bash
pip install copier==9.19.1
copier copy gh:ScottChiuNYC/copier-pypackage-cpp my-project
cd my-project
git init
git add .
git commit -m "Generate project"
# After committing your project changes, update to the latest template revision:
copier update
```

Copier records answers and the template version in `.copier-answers.yml`; commit it. Release versions are Git tags. The template lives under `template/`, so template metadata and its Git history are not copied into generated projects. Existing Cookiecutter-generated projects need deliberate adoption and review before using Copier updates; this migration does not rewrite those projects.

## Fresh Work / Codex / developer setup

Prerequisites: Python 3.12+, Git, and a C++17 compiler. Linux needs GCC or Clang plus curl, zip, unzip and tar. Windows needs Visual Studio 2022 with Desktop development with C++ and a Windows SDK (the `windows-2022` Actions image supplies them). Native compilers are platform prerequisites, not installed by pip.

From a fresh clone, on either Windows or Linux:

```bash
python scripts/bootstrap.py
python scripts/validate_template.py
```

Bootstrap installs the exact tool versions in `template/scripts/tool-requirements.txt` into `.dev-tools/venv`, checks out the vcpkg baseline declared in `template/vcpkg-configuration.json`, and bootstraps it. Validation needs no activation, manual PATH changes, or exported variables. Both platforms supply the installed Ninja path to nested vcpkg processes; Linux also pins the parent configure path. Compiler tracking stays enabled, and Windows retains the Visual Studio preset.

To reuse an already pinned vcpkg checkout:

```bash
python scripts/bootstrap.py --vcpkg-root /absolute/path/to/vcpkg
```

That checkout must already match the declared baseline and is not checked out to another version. Re-running bootstrap reuses installed tools and downloads. Use `--work-dir .validation` on validation to keep generated artifacts; that directory must be empty. The two repositories maintain their own scripts and their independent project architectures.

## Validation and CI

The validation script exercises default/custom Copier copy, real `v1.0.0` → `v1.1.0` updates in an isolated fixture, preservation of local README edits, answer/version persistence, identifier rejection and GitHub expression rendering. It then bootstraps the generated sample's own tool environment (reusing the pinned vcpkg checkout) and runs validation with the original runner Python and PATH, matching an unactivated generated-project workflow. This catches Windows executable lookup failures that an inherited template tool PATH would hide. Tool launches resolve executable paths before starting subprocesses, since Windows does not use the child's PATH for that lookup. Validation configures/builds the sample, runs its original tests, builds an sdist, rebuilds a platform wheel from that sdist, installs the wheel in a clean virtual environment, and imports its native extension outside the source checkout.

`.github/workflows/template-acceptance.yml` runs these same two commands on Linux and Windows. Generated projects include their own bootstrap/validation scripts and a Windows/Linux workflow using those scripts. The vcpkg GoogleTest overlay remains local and validation checks that `pkgconf` was not installed or acquired.

Generated projects run build CI automatically on push and pull request **unless all changed files are under `docs/development/`**. A mixed change that touches code, tests, build files or anything outside that directory still triggers CI. Manual `workflow_dispatch` remains available. Keep `docs/development/` for non-executable specifications, audit records and evidence; build/test/code-generation inputs belong outside it. If the project later makes development documents executable inputs, revisit the path exclusion. `template/.github/workflows/build-and-test.yml.jinja` renders the project's selected Python version and preserves GitHub Actions expressions. Bootstrap and validation scripts are ordinary Python files under `scripts/`; `.jinja` is used only for project-specific substitution. Template validation checks both workflows' triggers, platform matrix and script entry points before executing the sample build/tests.

No Docker, services, shell activation, personal vcpkg registry or custom infrastructure is needed. The first run downloads tools and compiles dependencies; later runs reuse local caches. Template acceptance on push allows Windows/Linux checks to finish before opening the migration PR.

## Generated C++ packages

Generated projects now install public headers, compiled libraries, and relocatable CMake config/version/target files. With default answers, the port is `my-project-core`, the CMake package is `my_project_core`, and the consumer target is `my_project_core::core`. `vcpkg_port_name` is a separate lowercase/hyphenated Copier answer; it does not rename the CMake API or the root dependency manifest. `version` retains the Poetry/port version; its numeric release component supplies the CMake package version (for example, `1.2.3rc1` → `1.2.3`). The custom sample validates this prerelease path.

The generated README contains exact Linux/PowerShell commands for installing the local port and consuming it in an independent project. The port remains inside the generated source checkout; it builds that working tree, with no registry, upload, release workflow, Python tooling, or test dependency required by the C++ consumer. Run `python scripts/validate_vcpkg.py` after bootstrap to exercise just packaging; the normal generated validation invokes it automatically.

Packaging acceptance installs into a fresh consumer manifest, disables binary caching for mutable local sources, relocates the installed prefix, hides source headers, checks imported include/library/config paths, and compiles/links/runs both Release and Debug consumers. The core remains static (including dynamic triplets), and its port disables pybind11, Python discovery, examples and tests. Poetry/CTest/pytest, sdist-to-wheel rebuilding and clean wheel import remain part of full acceptance. PR #10's executable resolution and unactivated-runner regression are retained.

The existing tagged `v1.0.0` → `v1.1.0` fixture remains. A separate fixture generates from the pre-packaging master commit, updates through isolated `v2.0.0` → `v2.1.0` tags, retains user source edits/files and existing answers, then runs the installed consumer. Acceptance checkouts include Git history for this fixture. No real downstream repository is updated.
