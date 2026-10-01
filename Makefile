# sql-megasamples. Every target is a one-line shim over `python3 -m megasamples <command>`, so
# `make -n <target>` shows exactly what runs and nothing here is logic. ARCHITECTURE.md explains the
# pipeline; `make help` lists the commands.
PY  ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
MS   = PYTHONPATH=. $(PY) -m megasamples
DATASETS := $(shell PYTHONPATH=. $(PY) -m megasamples list --names 2>/dev/null)
ifdef SF                       # scale factor for the generated benchmarks: make tpch SF=0.01
export SF                      # (unset: megasamples.yaml build.scale_factor, default 1)
endif

.PHONY: help configure list list-core list-quick fetch build image test-image run up down status clean clean-all \
        compose console-page catalogue provenance check okf-check audit-assets prepub-check \
        test-console screenshots build-server build-server-stop restore loader-image \
        wwi-export verify-oracle load-citibike load-divvy load-tpcc bench $(DATASETS)

help:
	@echo "The stack (reads megasamples.yaml; \`make configure\` writes it):"
	@echo "  make configure        choose engines x datasets and consoles, interactively"
	@echo "  make run              the whole job: fetch, build, image, for every engine configured"
	@echo "  make up | down        start the stack (regenerating compose.yaml and the index page) | stop it"
	@echo "  make status | clean   what is running | remove the transient containers (clean-all: the stack too)"
	@echo "  make list             every engine, dataset (tier, download size, shape) and console"
	@echo ""
	@echo "The pipeline, one step at a time:"
	@echo "  make fetch D=\"sakila chinook\"   download and verify (once) the named datasets' artifacts"
	@echo "  make <dataset>        fetch, stage, load and verify one dataset on MySQL, e.g. make sakila"
	@echo "  make build [ENGINE=mysql] [D=...]   the same for the configured datasets of an engine"
	@echo "  make image [ENGINE=mysql]           bake the configured datasets into the engine's image"
	@echo "                        (FROM_DUMPS=1: from the dumps already built, without the build server)"
	@echo "  make test-image [ENGINE=mysql]      the image-level tests"
	@echo "  make test-console     the consoles are up and the accounts behave"
	@echo "  make screenshots      retake the README's pictures from the running stack (docs/screenshots/)"
	@echo "  make restore [D=...]  reload datasets into the MySQL build server from their dumps"
	@echo ""
	@echo "Documents and checks:"
	@echo "  make check            the local gate: bundle validation + generated files up to date"
	@echo "  make catalogue | provenance         regenerate CATALOGUE.md | LICENSE, PROVENANCE, NOTICE files"
	@echo "  make audit-assets | prepub-check    nothing unredistributable is shipped | the pre-publication checklist"
	@echo ""
	@echo "Source-side tools (each prints its licence gate and refuses until you accept):"
	@echo "  make wwi-export       re-derive WideWorldImporters from Microsoft's .bak (SQL Server EULA)"
	@echo "  make verify-oracle    cross-check the Oracle datasets against Oracle Free (Free Use Terms)"
	@echo "  make load-citibike | load-divvy     one month of bike-share trips, never redistributed"
	@echo "  make load-tpcc W=1    TPC-C through sysbench in the loader image (make loader-image first)"
	@echo ""
	@echo "  python3 -m megasamples --help       every command, with its own --help"

configure:      ; @$(MS) configure
list:           ; @$(MS) list
list-core:      ; @$(MS) list --names --select core | tr '\n' ' '
list-quick:     ; @$(MS) list --names --select quick | tr '\n' ' '
fetch:          ; @$(MS) fetch $(D)
build:          ; @$(MS) build $(if $(ENGINE),--engine $(ENGINE),) $(D)
image:          ; @$(MS) image $(if $(ENGINE),--engine $(ENGINE),) $(if $(KEEP_BUILD_RESOURCES),--keep,) $(if $(FROM_DUMPS),--from-dumps,) $(D)
test-image:     ; @$(MS) test-image $(if $(ENGINE),--engine $(ENGINE),) $(D)
run:            ; @$(MS) run
up:             ; @$(MS) up
down:           ; @$(MS) down
status:         ; @$(MS) status
clean:          ; @$(MS) clean
clean-all:      ; @$(MS) clean --all
compose:        ; @$(MS) compose
console-page:   ; @$(MS) console-page
catalogue:      ; @$(MS) catalogue
provenance:     ; @$(MS) provenance
check:          ; @$(MS) check
okf-check:      ; @$(MS) okf-check --bundle knowledge && $(MS) okf-fix-quotes --bundle knowledge --check
audit-assets:   ; @$(MS) audit-assets
prepub-check:   ; @$(MS) prepub-check
test-console:   ; @$(MS) test-console
build-server:   ; @$(MS) build-server start
build-server-stop: ; @$(MS) build-server stop
restore:        ; @$(MS) restore $(D)
bench:          ; @$(MS) bench --dataset $(or $(DATASET),employees) --repeat $(or $(REPEAT),1)

# the README's screenshots, taken by docs/screenshots/capture.py in the Playwright image on the stack's network
screenshots:
	@docker run --rm --network sql-megasamples_default -v "$(CURDIR)/docs/screenshots:/out" --label megasamples.transient=true \
	  mcr.microsoft.com/playwright/python:v1.49.1-noble sh -c "pip install -q --break-system-packages playwright==1.49.1 && python3 /out/capture.py"
	@ls -l docs/screenshots/*.png

# the build-time loader image: compiles SSB's dbgen and carries sysbench for TPC-C. Nothing from it
# reaches any published image.
loader-image:
	@$(MS) pull-image debian:12-slim
	@$(if $(shell docker version -f "{{json .Server.Components}}" 2>/dev/null | grep -q Podman && echo podman),,DOCKER_BUILDKIT=1 )docker build -f engines/mysql/loader.Dockerfile -t sql-megasamples-loader:dev .

#   MEGASAMPLES_ACCEPT_MSSQL_EULA=1 make wwi-export
wwi-export:
	@$(MS) fetch wideworldimporters wideworldimporters_dw
	@$(MS) wwi-export
#   MEGASAMPLES_ACCEPT_ORACLE_LICENSE=1 make verify-oracle [ONLY=oracle_hr] [KEEP=1]
verify-oracle:  ; @$(MS) verify-oracle $(if $(ONLY),--only $(ONLY),) $(if $(KEEP),--keep,)
#   MEGASAMPLES_ACCEPT_BIKESHARE_LICENSE=1 make load-citibike [MONTH=JC-202602]
load-citibike:  ; @$(MS) bikeshare citibike $(if $(MONTH),--month $(MONTH),)
load-divvy:     ; @$(MS) bikeshare divvy $(if $(MONTH),--month $(MONTH),)
load-tpcc:      ; @$(MS) tpcc-load --warehouses $(or $(W),1)

# one target per dataset: fetch, stage, load and verify it on MySQL
$(DATASETS):
	@$(MS) build --engine mysql $@
