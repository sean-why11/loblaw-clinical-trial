.PHONY: setup pipeline dashboard

setup:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

pipeline:
	python run_pipeline.py

dashboard:
	python -m streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
