# obskit-middleware-django

Django middleware that automatically injects correlation IDs and RED metrics into every request.

## Install

```bash
pip install obskit-middleware-django
```

## Quick start

In `settings.py`:

```python
MIDDLEWARE = [
    "obskit.middleware.django.ObskitDjangoMiddleware",
    # ... other middleware
]
```
