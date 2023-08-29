.PHONY: help build-image 

CONTAINER_DIR      ?= .devcontainer
WORK_DIR           ?= $(shell pwd)
USERNAME           ?= testuser
USER_UID           ?= 1000
USER_GID           ?= 1000

IMAGE_NAME         ?= termdown
CONTAINER_NAME     ?= $(IMAGE_NAME)-$(USERNAME)-$(shell date +"%Y-%m-%d.%H-%M")
DOCKER_FILE        ?= $(CONTAINER_DIR)/python.Dockerfile
DOCKER_ENTRYPOINT  ?= 
SHARED_DIRS        ?= 


define BUILD_IMAGE_HELP_INFO
  build-image 
    Build the docker image
endef
export BUILD_IMAGE_HELP_INFO

build-image:
	@docker build -t $(IMAGE_NAME)                        \
		--build-arg DOCKER_ENTRYPOINT=$(DOCKER_ENTRYPOINT)  \
		--file $(DOCKER_FILE) .

# ============================================================================= #

define RUN_CONTAINER_HELP_INFO
  run-container
    Run container from the docker image
endef
export RUN_CONTAINER_HELP_INFO

run-container:
	@docker run -it $(IMAGE_NAME)

# ============================================================================= #

help:
	@echo "Usage: make [TARGET] [VARIABLE=value]\n"
	@echo "$$BUILD_IMAGE_HELP_INFO\n"
	@echo "$$RUN_CONTAINER_HELP_INFO\n"
