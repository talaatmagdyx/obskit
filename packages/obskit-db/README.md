# obskit-db

SQLAlchemy and database instrumentation for the obskit observability toolkit.

## Installation

```bash
pip install obskit-db

# With SQLAlchemy support
pip install "obskit-db[sqlalchemy]"
```

## Features

- **SQLAlchemy event listeners** — Automatic query metrics and slow-query logging
- **Query analyzer** — Identify N+1 queries and slow operations
- **Connection pool monitoring** — Track pool exhaustion and wait times
- **Database health checks** — Integration with `obskit-health`

## Usage

```python
from obskit.db import instrument_sqlalchemy
from sqlalchemy import create_engine

engine = create_engine("postgresql://user:pass@localhost/db")
instrument_sqlalchemy(engine, service_name="order-service")
```

## Part of obskit

This package is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo.
