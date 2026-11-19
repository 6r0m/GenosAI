.DEFAULT_GOAL := help
PYTHON ?= python3
PROVIDER ?= shared
PLATFORM ?= host
.PHONY: help init check test install uninstall export public-check
help:
	@echo 'make init; make check; make install PROVIDER=shared|claude|codex|pi PLATFORM=host|windows|both; make test'
	@echo 'make export DEST=<outside-source-path> MANIFEST=<receipt.json>; make public-check'
	@echo 'Pi runtime acquisition: make install PROVIDER=pi RUNTIME=1; Claude approved plan: make install PROVIDER=claude APPROVE=<plan-id>'
init:
	@$(PYTHON) tools/setup.py init
check:
	@$(PYTHON) tools/setup.py check
public-check:
	@$(PYTHON) tools/release.py check
test:
	@$(PYTHON) tools/setup.py test
install:
	@bash agents/scripts/install.sh --provider '$(PROVIDER)' --platform '$(PLATFORM)' $(if $(APPROVE),--approve '$(APPROVE)') $(if $(RUNTIME),--runtime)
uninstall:
	@bash agents/scripts/uninstall.sh --provider '$(PROVIDER)' --platform '$(PLATFORM)' $(if $(RUNTIME),--runtime)
export:
	@$(PYTHON) tools/release.py export '$(DEST)' $(if $(MANIFEST),--manifest '$(MANIFEST)')
