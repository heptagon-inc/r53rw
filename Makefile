.DEFAULT_GOAL := help


## clean artifacts
clean_artifacts:
	-rm -rf functions/artifacts

## artifacts
artifacts: clean_artifacts
	cp -a functions/src functions/artifacts
	pip install -r functions/src/requirements.txt -t functions/artifacts/

## diff
diff:
	-npx cdk diff

## deploy
deploy:
	npx cdk deploy --require-approval never

## help
help:
	@make2help $(MAKEFILE_LIST)


.PHONY: help
.SILENT:
