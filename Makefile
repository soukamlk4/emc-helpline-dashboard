.PHONY: help install up down init-db etl kpi test dashboard clean

help:
	@echo "Commandes disponibles :"
	@echo "  make install    - installe les dépendances Python"
	@echo "  make up         - démarre PostgreSQL (Docker)"
	@echo "  make down       - arrête PostgreSQL (Docker)"
	@echo "  make init-db    - applique le schéma (docker/postgres/init.sql)"
	@echo "  make etl        - lance le pipeline ETL sur data/bronze/signalements.xlsx"
	@echo "  make kpi        - affiche les 8 KPI recalculés depuis la base"
	@echo "  make test       - lance la suite de tests pytest"
	@echo "  make dashboard  - lance le dashboard Streamlit"
	@echo "  make clean      - supprime les fichiers temporaires (cache, logs)"

install:
	pip install -r requirements.txt

up:
	docker-compose up -d

down:
	docker-compose down

init-db:
	docker exec -i emc_helpline_db psql -U postgres -d emc_helpline < docker/postgres/init.sql

etl:
	python3 -m src.etl_main data/bronze/signalements.xlsx

kpi:
	python3 -m src.gold.kpi_calculator

test:
	python3 -m pytest tests/ -v

dashboard:
	streamlit run dashboard/app.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -f logs/*.log
