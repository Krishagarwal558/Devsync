# Neon PostgreSQL Setup

1. Create a Neon project.
2. Create a database named `devsync`.
3. Copy the pooled connection string.
4. Convert it for SQLAlchemy asyncpg:

```txt
postgresql+asyncpg://USER:PASSWORD@HOST/DB?ssl=require
```

5. Set it as:

```txt
DEVSYNC_DATABASE_URL=postgresql+asyncpg://...
```

6. Run migrations:

```bash
alembic -c server/alembic.ini upgrade head
```

7. Confirm backend health:

```bash
curl https://your-backend/health
```

