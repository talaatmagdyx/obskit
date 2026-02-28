# obskit-middleware-flask

Flask middleware that automatically injects correlation IDs and RED metrics into every request.

## Install

```bash
pip install obskit-middleware-flask
```

## Quick start

```python
from flask import Flask
from obskit.middleware.flask import ObskitFlaskMiddleware

app = Flask(__name__)
ObskitFlaskMiddleware(app)

@app.route("/orders/<id>")
def get_order(id):
    return {"id": id}
```
