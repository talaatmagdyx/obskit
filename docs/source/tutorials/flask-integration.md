# Flask Integration Tutorial

Add full observability to a Flask application.

## Video Tutorial

<!-- Placeholder for asciinema embed -->
<div id="flask-demo">
<p><em>Record this tutorial: <code>asciinema rec flask.cast -c "bash docs/source/tutorials/scripts/flask.sh"</code></em></p>
</div>

## What You'll Learn

1. Adding obskit middleware to Flask
2. Automatic request metrics and tracing
3. Using Flask's extension pattern
4. Health check integration

## Prerequisites

- Python 3.11+
- Basic Flask knowledge

## Step-by-Step

### 1. Install dependencies

```bash
pip install obskit[flask]
```

### 2. Create the application

```python
# app.py
from flask import Flask, jsonify
from obskit import configure, get_red_metrics, get_logger, start_http_server
from obskit.middleware.flask import ObskitFlaskMiddleware

# Configure obskit
configure(
    service_name="flask-demo",
    log_format="console",
)

# Create Flask app
app = Flask(__name__)

# Add observability middleware
ObskitFlaskMiddleware(app)

# Get components
metrics = get_red_metrics()
logger = get_logger()

# Start metrics server
start_http_server(9090)

# Routes
@app.route("/")
def root():
    logger.info("root_accessed")
    return jsonify({"message": "Hello from Flask!"})

@app.route("/items/<int:item_id>")
def get_item(item_id):
    logger.info("item_requested", item_id=item_id)
    
    # Custom metrics
    with metrics.track_request("get_item_details"):
        import time
        time.sleep(0.05)  # Simulate work
    
    return jsonify({"item_id": item_id, "name": f"Item {item_id}"})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

### 3. Run the application

```bash
python app.py
```

### 4. Test the endpoints

```bash
# Root endpoint
curl http://localhost:5000/

# Get an item
curl http://localhost:5000/items/42

# View metrics
curl http://localhost:9090/metrics
```

## Using the Extension Pattern

For larger applications, use Flask's extension pattern:

```python
# extensions.py
from obskit.middleware.flask import ObskitFlaskMiddleware

obskit = ObskitFlaskMiddleware()

# app.py
from flask import Flask
from extensions import obskit

def create_app():
    app = Flask(__name__)
    obskit.init_app(app)
    return app
```

## Configuration Options

```python
ObskitFlaskMiddleware(
    app,
    exclude_paths=["/health", "/metrics", "/static"],  # Skip these
    track_metrics=True,   # Enable metrics
    track_logging=True,   # Enable logging
    track_tracing=True,   # Enable tracing
)
```

## Accessing Correlation ID in Views

```python
from flask import g
from obskit.core.context import get_correlation_id

@app.route("/")
def root():
    # Option 1: From Flask's g
    correlation_id = g._obskit_correlation_id
    
    # Option 2: From obskit context
    correlation_id = get_correlation_id()
    
    return jsonify({"correlation_id": correlation_id})
```

## Script for Recording

```bash
#!/bin/bash
# Flask integration tutorial

clear
echo "# Flask + obskit Integration"
sleep 1

pip install obskit flask --quiet

cat > /tmp/app.py << 'PYEOF'
from flask import Flask, jsonify
from obskit import configure, get_red_metrics, start_http_server
from obskit.middleware.flask import ObskitFlaskMiddleware

configure(service_name="flask-demo", log_format="console")

app = Flask(__name__)
ObskitFlaskMiddleware(app)

metrics = get_red_metrics()
start_http_server(9090)

@app.route("/")
def root():
    return jsonify({"message": "Hello!"})

@app.route("/items/<int:id>")
def get_item(id):
    import time
    with metrics.track_request("db_query"):
        time.sleep(0.05)
    return jsonify({"id": id})

if __name__ == "__main__":
    app.run(port=5000)
PYEOF

echo "# Start Flask server"
cd /tmp && python app.py &
sleep 2

echo ""
echo "# Test endpoints"
curl -s http://localhost:5000/
curl -s http://localhost:5000/items/42

echo ""
echo "# View metrics"
curl -s http://localhost:9090/metrics | grep flask

pkill -f "python app.py"
echo "# Done!"
```

## Next Steps

- [Django Integration](../examples/kubernetes.md)
- [Kubernetes Deployment](kubernetes-deployment.md)

