import os
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent

FETCH_RULE = """\
MAKEFILES_REF ?= v1
MAKEFILES_URL ?= https://raw.githubusercontent.com/sowwic/makefiles/$(MAKEFILES_REF)
.make/%.mk:
\t@mkdir -p $(dir $@)
\t@curl -fsSL $(MAKEFILES_URL)/$*.mk -o $@
include $(MAKEFILES_MODULES:%=.make/%.mk)
"""


@pytest.fixture
def source(tmp_path):
    """A local copy of the modules, served through file:// like the repo is through https."""
    folder = tmp_path / "source"
    for module in REPO.glob("*/*.mk"):
        (folder / module.parent.name).mkdir(parents=True, exist_ok=True)
        shutil.copy(module, folder / module.parent.name / module.name)
    return folder


@pytest.fixture
def make_project(tmp_path, source):
    """Create a project folder with a thin Makefile, return a function that runs make in it."""

    def create(modules, before="", after="", fetched=False):
        project = tmp_path / "project"
        project.mkdir(exist_ok=True)
        (project / "VERSION").write_text("1.2.3\n")
        (project / "Makefile").write_text(
            "APP_NAME = demo\nPACKAGE_NAME = demo_pkg\n"
            f"MAKEFILES_URL = file://{source}\n"
            f"MAKEFILES_MODULES = {' '.join(modules)}\n"
            f"{before}\n{FETCH_RULE}\n{after}\n"
        )
        if fetched:
            for module in modules:
                target = project / ".make" / f"{module}.mk"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source / f"{module}.mk", target)
        return project

    return create


def run(project, *args, env=None, check=True):
    result = subprocess.run(
        ["make", *args],
        cwd=project,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=False,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def dry(project, target, *args, **kwargs):
    return run(project, "-n", target, *args, **kwargs).stdout


def listed_targets(project):
    lines = run(project, "help").stdout.splitlines()
    return {line.split()[0] for line in lines if line.startswith("  ")}


def test_a_missing_module_is_fetched_and_help_is_the_default_goal(make_project):
    project = make_project(["general/python"])
    assert not (project / ".make").exists()

    result = run(project)

    assert (project / ".make" / "general" / "python.mk").is_file()
    assert "Available make targets" in result.stdout


def test_python_module_has_the_common_targets(make_project):
    project = make_project(["general/python"])

    assert listed_targets(project) >= {
        "help",
        "clean",
        "lint",
        "lint-fix",
        "format",
        "pytest",
        "pytest-pdb",
        "mkdocs",
        "check",
        "build",
        "update-version",
        "release",
        "update-make",
    }


def test_help_lists_only_the_included_modules(make_project):
    python_only = listed_targets(make_project(["general/python"]))
    with_qt = listed_targets(
        make_project(["general/python", "general/qt"], fetched=True)
    )

    assert "qrc" not in python_only
    assert "qrc" in with_qt


def test_lint_paths_can_be_overridden(make_project):
    project = make_project(
        ["general/python"], before="LINT_PATHS = src tests extension scripts"
    )

    assert "uv run ruff check src tests extension scripts" in dry(project, "lint")
    assert "uv run ruff format src tests extension scripts" in dry(project, "format")
    assert "uv run ruff check --fix src tests extension scripts" in dry(
        project, "lint-fix"
    )


def test_default_lint_paths(make_project):
    assert "uv run ruff check src tests\n" in dry(
        make_project(["general/python"]), "lint"
    )


def test_pytest_commands_can_be_overridden(make_project):
    project = make_project(
        ["general/python"],
        before="PYTEST_CMD = ./mayapy_test.sh\nPYTEST_PDB_CMD = ./mayapy_test.sh --pdb",
    )

    assert "./mayapy_test.sh\n" in dry(project, "pytest")
    assert "./mayapy_test.sh --pdb" in dry(project, "pytest-pdb")


def test_default_pytest_commands(make_project):
    project = make_project(["general/python"])

    assert "uv run pytest tests\n" in dry(project, "pytest")
    assert "uv run pytest -vvv --pdb --log-cli-level=DEBUG tests" in dry(
        project, "pytest-pdb"
    )


def test_build_runs_its_prerequisites_first(make_project):
    project = make_project(
        ["general/python", "general/qt"], before="BUILD_PREREQS = qrc"
    )

    output = dry(project, "build")

    assert output.index("pyside6-rcc") < output.index("uv build")


def test_check_is_lint_then_pytest_and_can_be_extended(make_project):
    project = make_project(["general/python"], after="check::\n\t@echo extra-check-step")

    output = dry(project, "check")

    assert (
        output.index("ruff check")
        < output.index("uv run pytest")
        < output.index("extra-check-step")
    )


def test_clean_can_be_extended(make_project):
    project = make_project(["general/python"], after="clean::\n\t@rm -rf node_modules")

    output = dry(project, "clean")

    assert "rm -rf dist" in output and "rm -rf node_modules" in output


def test_update_version_and_release_use_the_version_file(make_project):
    project = make_project(["general/python"])

    assert "uv version 1.2.3" in dry(project, "update-version")
    release = dry(project, "release")
    assert "gh-workflows/v1/scripts/release.py" in release
    assert (
        "release.py" in release
        and "1.2.3 --release-branch main --develop-branch develop"
        in release.replace("python3 - ", "")
    )


def test_release_branch_names_are_variables(make_project):
    project = make_project(
        ["general/python"], before="RELEASE_BRANCH = stable\nDEVELOP_BRANCH = dev"
    )

    assert "--release-branch stable --develop-branch dev" in dry(project, "release")


def test_update_make_fetches_the_modules_again(make_project, source):
    project = make_project(["general/python"], fetched=True)
    (source / "general" / "python.mk").write_text(
        (source / "general" / "python.mk").read_text() + "\n# newer version\n"
    )

    run(project, "update-make")

    assert "# newer version" in (project / ".make" / "general" / "python.mk").read_text()


def test_the_ref_chooses_where_modules_come_from(make_project):
    project = make_project(
        ["general/python"], before="MAKEFILES_URL = file:///nowhere\nMAKEFILES_REF = v9"
    )

    result = run(project, check=False)

    assert result.returncode != 0
    assert not (project / ".make" / "general" / "python.mk").exists()


def test_qml_bundle_and_macos_modules(make_project):
    project = make_project(
        [
            "general/python",
            "general/qt",
            "general/qml",
            "general/bundle",
            "general/macos-app",
        ]
    )

    assert listed_targets(project) >= {
        "qrc",
        "qmlls",
        "bundle",
        "iconset",
        "install",
    }
    assert "generate_qmlls_config.py" in dry(project, "qmlls")
    assert "pyinstaller --noconfirm demo.spec" in dry(project, "bundle")
    assert "dist/demo.app" in dry(project, "install")


def test_qrc_compiles_the_package_resources(make_project):
    output = dry(make_project(["general/python", "general/qt"]), "qrc")

    assert "src/demo_pkg/resources/resources.qrc" in output
    assert "src/demo_pkg/resources/resources_rc.py" in output


def test_maya_dist_installs_from_the_project_folder_not_from_a_wheel(make_project):
    project = make_project(["general/python", "dcc/maya"])

    output = dry(project, "dist")

    assert "uv pip install --target dist/demo_pkg_module/python .\n" in output
    assert "uv build" not in output and "*.whl" not in output


def test_maya_dist_runs_the_build_prerequisites_first(make_project):
    project = make_project(
        ["general/python", "general/qt", "dcc/maya"], before="BUILD_PREREQS = qrc"
    )

    output = dry(project, "dist")

    assert output.index("pyside6-rcc") < output.index("uv pip install")


def maya_env(tmp_path):
    env_file = tmp_path / "maya.env"
    env_file.write_text("MAYAPY=/maya/bin/mayapy\nMAYA_MODULE_PATH=/maya/modules\n")
    return {"MAYA_CI_ENV_FILE": str(env_file)}


def test_maya_module_targets(make_project, tmp_path):
    project = make_project(
        ["general/python", "dcc/maya"], before="PYTEST_CMD = ./mayapy_test.sh"
    )
    env = maya_env(tmp_path)

    assert listed_targets(project) >= {
        "venv",
        "dev",
        "dist",
        "maya-module-file",
        "install-module",
        "install",
        "uninstall",
        "dispatch-pytest",
    }
    assert "demo_pkg.mod" in dry(project, "maya-module-file")
    install = dry(project, "install-module", env=env)
    assert 'cp "dist/demo_pkg.mod"' in install and "MAYA_MODULE_PATH" in install
    assert "dist/demo_pkg_module" in dry(project, "dist")
    assert "gh workflow run unit_tests.yml" in dry(project, "dispatch-pytest")


def test_maya_env_file_is_the_one_in_the_variable(make_project, tmp_path):
    project = make_project(["general/python", "dcc/maya"])
    env = maya_env(tmp_path)

    output = dry(project, "uninstall", env=env)

    assert str(tmp_path / "maya.env") in output


def test_maya_install_really_writes_the_mod_file(make_project, tmp_path):
    project = make_project(["general/python", "dcc/maya"], fetched=True)
    (project / "templates").mkdir()
    (project / "templates" / "demo_pkg.mod").write_text(
        "+ demo_pkg @VERSION@ @MODULE_ROOT@\n"
    )
    modules = tmp_path / "modules"
    env_file = tmp_path / "maya.env"
    env_file.write_text(f"MAYA_MODULE_PATH={modules}\n")
    env = {"MAYA_CI_ENV_FILE": str(env_file)}

    run(project, "maya-module-file")
    run(project, "install-module", env=env)

    installed = (modules / "demo_pkg.mod").read_text()
    assert "demo_pkg 1.2.3" in installed
    run(project, "uninstall", env=env)
    assert not (modules / "demo_pkg.mod").exists()


def test_blender_extension_targets(make_project, tmp_path):
    project = make_project(["general/python", "dcc/blender"])
    env_file = tmp_path / "blender.env"
    env_file.write_text("BLENDER=/blender/Blender\n")
    env = {"BLENDER_CI_ENV_FILE": str(env_file)}

    assert listed_targets(project) >= {"extension", "validate", "install", "uninstall"}
    assert "scripts/build_extension.py" in dry(project, "extension", env=env)
    assert "--command extension validate extension" in dry(project, "validate", env=env)
    install = dry(project, "install", env=env)
    assert "install-file -r user_default --enable" in install
    assert "dist/demo_pkg-1.2.3.zip" in install
    assert "--command extension remove demo_pkg" in dry(project, "uninstall", env=env)


def test_blender_extension_id_can_differ_from_the_package(make_project, tmp_path):
    project = make_project(
        ["general/python", "dcc/blender"], before="EXTENSION_ID = other_id"
    )
    env_file = tmp_path / "blender.env"
    env_file.write_text("BLENDER=/blender/Blender\n")

    install = dry(project, "install", env={"BLENDER_CI_ENV_FILE": str(env_file)})

    assert "dist/other_id-1.2.3.zip" in install


def test_a_missing_env_file_is_a_clear_error(make_project, tmp_path):
    project = make_project(["general/python", "dcc/blender"], fetched=True)
    env = {"BLENDER_CI_ENV_FILE": str(tmp_path / "missing.env")}

    result = run(project, "validate", env={**env, "HOME": str(tmp_path)}, check=False)

    assert result.returncode != 0
