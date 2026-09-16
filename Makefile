.PHONY: install test demo proof
install:
	python3 -m pip install -e .
test:
	python3 -m unittest discover -s tests -v
demo:
	python3 -m web_data_pipeline.cli --input data/mock --output output
proof: test demo
	python3 -m web_data_pipeline.benchmark --output proof/benchmark.json
