# QML projects: `qmlls` writes .qmlls.ini for the QML language server.

.PHONY: qmlls
qmlls: ## Generate .qmlls.ini for the QML language server
	@uv run python generate_qmlls_config.py
