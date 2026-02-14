# YoYoMusic Backend (FastAPI)

## Setup
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration
Copy `.env.example` to `.env` (create one based on config.py).
Required variables:
- `DATABASE_URL`
- `REDIS_URL`

## Running Locally
```bash
uvicorn app.main:app --reload
```

## Running Migrations
```bash
alembic upgrade head
```
