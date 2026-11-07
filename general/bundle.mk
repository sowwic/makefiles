# PyInstaller bundling: `bundle` packages the application from <APP_NAME>.spec.
# Needs the `qrc` target (include general/qt).

.PHONY: bundle
bundle: qrc ## Package the application with PyInstaller
	$(call banner, Bundling $(APP_NAME)...)
	@uv run pyinstaller --noconfirm $(APP_NAME).spec
