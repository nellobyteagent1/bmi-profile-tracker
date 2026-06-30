# BMI Calculator App

Single-service BMI calculator with:

- Angular frontend served by the backend
- PostgreSQL-backed user registration and login
- Persistent saved profile reuse on later visits
- BMI calculation and category display

## Run

```bash
export DATABASE_URL=postgresql://...
export PORT=8000
export BASE_PATH=/agent1/devops/bmi-calculator
python3 server.py
```

## Test

```bash
python3 -m unittest discover -s tests -v
python3 tests/integration_check.py
```
