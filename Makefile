.PHONY: clean

clean:
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete
	find . -name '__pycache__' -delete

test:
	docker-compose up --build --abort-on-container-exit
