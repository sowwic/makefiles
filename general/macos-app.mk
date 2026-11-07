# macOS .app: `iconset` makes the .icns icon, `install` copies the bundle to /Applications.
# Include after general/python and general/bundle.

APP_PATH ?= $(DIST_DIR)/$(APP_NAME).app
MAC_APPLICATIONS_DIR ?= /Applications

.PHONY: iconset
iconset: ## Generate .icns icon from source PNG using sips and iconutil
	$(call banner, Generating iconset...)
	@ICONS=src/$(PACKAGE_NAME)/resources/icons; \
	SET=$$ICONS/$(APP_NAME).iconset; \
	mkdir -p $$SET; \
	for size in 16 32 128 256 512; do \
		sips -z $$size $$size $$ICONS/$(PACKAGE_NAME).png --out $$SET/icon_$${size}x$${size}.png >/dev/null; \
		sips -z $$((size*2)) $$((size*2)) $$ICONS/$(PACKAGE_NAME).png --out $$SET/icon_$${size}x$${size}@2x.png >/dev/null; \
	done; \
	iconutil -c icns $$SET -o $$ICONS/$(APP_NAME).icns; \
	rm -rf $$SET
	@printf "$(GREEN)Iconset generation complete.$(RESET)\n"

.PHONY: install
install: ## Install the bundled application into /Applications
	$(call banner, Installing $(APP_NAME) v$(VERSION) into $(MAC_APPLICATIONS_DIR)...)
	@cp -R "$(APP_PATH)" "$(MAC_APPLICATIONS_DIR)/"
	@printf "$(GREEN)Installation complete.$(RESET)\n"
