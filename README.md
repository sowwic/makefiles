# makefiles

Shared Makefile modules for Python projects, so the common targets (`lint`, `pytest`, `build`, `release` ...) live in
one place instead of being copied into every repository.

## Modules

Grouped in folders, a module is named by its path without `.mk` (`general/python`, `dcc/maya`).

| Module | Targets | Use it for |
| --- | --- | --- |
| `general/python` | `help clean lint lint-fix format pytest pytest-pdb mkdocs check build update-version release update-make` | every project, include it first |
| `general/qt` | `qrc` | Qt resources (`resources/resources.qrc`), also Maya tools with Qt |
| `general/qml` | `qmlls` | QML projects |
| `general/bundle` | `bundle` | PyInstaller bundles (needs `general/qt`) |
| `general/macos-app` | `iconset install` | macOS `.app` (after `general/bundle`) |
| `dcc/maya` | `venv dev dist maya-module-file install-module install uninstall dispatch-pytest` | Autodesk Maya packages |
| `dcc/blender` | `extension validate install uninstall` | Blender extensions |

Targets have `##` help text, `make help` lists the ones of all included modules.

## Use in a project

`make` cannot include a file from a URL, so the project Makefile fetches the modules it lists into `.make/`
the first time they are missing:

```make
APP_NAME = my-project
PACKAGE_NAME = my_package

MAKEFILES_REF ?= v1
MAKEFILES_URL ?= https://raw.githubusercontent.com/sowwic/makefiles/$(MAKEFILES_REF)
MAKEFILES_MODULES = general/python

.make/%.mk:
	@mkdir -p $(dir $@)
	@curl -fsSL $(MAKEFILES_URL)/$*.mk -o $@
include $(MAKEFILES_MODULES:%=.make/%.mk)
```

Commit `.make/`: CI and offline work then need no network. `make update-make` deletes it and fetches the modules
again, at the `MAKEFILES_REF` of the Makefile (a tag, or a branch or commit). Bump the ref to take a newer version.
The Copier templates [`copier-python-project`](https://github.com/sowwic/copier-python-project),
[`copier-maya-plugin`](https://github.com/sowwic/copier-maya-plugin) and
[`copier-blender-extension`](https://github.com/sowwic/copier-blender-extension) generate a Makefile like this.

## Inheritance

Set variables **before** the `include`, the modules only use `?=` defaults:

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_NAME`, `PACKAGE_NAME` | none, required | Project (distribution) name and import name |
| `RELEASE_BRANCH`, `DEVELOP_BRANCH` | `main`, `develop` | Used by `release` |
| `GH_WORKFLOWS_REF` | `v1` | Version of `sowwic/gh-workflows` whose `release.py` `release` runs |
| `LINT_PATHS` | `src tests` | Paths of `lint`, `lint-fix` and `format` |
| `PYTEST_CMD`, `PYTEST_PDB_CMD` | `uv run pytest tests`, the same with `-vvv --pdb ...` | What `pytest` and `pytest-pdb` run |
| `BUILD_PREREQS` | none | Targets `build` needs first, e.g. `qrc` |
| `DIST_DIR`, `BUILD_DIR`, `MKDOCS_SITE_DIR`, `TEST_OUTPUT_DIR` | `dist build site .test_output` | Folders `clean` removes |
| `ENV_FILE` | `maya.mk`: `MAYA_CI_ENV_FILE`, `./.env`, `~/.config/maya-ci.env`; `blender.mk`: `BLENDER_CI_ENV_FILE`, `./.env`, `~/.config/blender-ci.env` | File with `MAYAPY`/`MAYA_MODULE_PATH` or `BLENDER` |

Add steps to a shared target with a double-colon rule in the project Makefile, after the include:

```make
check::
	@echo "runs after lint and pytest"

clean::
	@rm -rf node_modules
```

Your own targets go after the include too. Defining a target that a module already defines overrides its recipe
(with a warning), so prefer the variables above.

## Adding a module

A module is a plain `.mk` file in a group folder of this repo (`general/` for what any Python project uses, `dcc/` for one application, e.g. a new `dcc/houdini.mk`; a new group is just a new folder): a comment on top saying what it needs, `?=` defaults for
its variables, `.PHONY` targets with `##` help text. Add its path (`dcc/houdini`) to `MAKEFILES_MODULES` in the projects that want
it, and a test in `tests/test_modules.py` that checks its dry-run commands (`make -n`).

## Developing

```sh
uv sync
uv run pytest      # runs `make -n` and fetches modules from a local file:// URL
```

Release by tagging: `git tag v1.1.0`, and move the major tag the projects pin: `git tag -f v1 && git push -f origin v1`.
