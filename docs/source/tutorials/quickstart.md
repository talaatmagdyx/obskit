# Quickstart Tutorial

Get obskit running in under 2 minutes.

## Video Tutorial

<!-- Placeholder for asciinema embed -->
<div id="quickstart-demo">
<!-- Replace with your asciinema embed:
<script src="https://asciinema.org/a/XXXXX.js" id="asciicast-XXXXX" async></script>
-->
<p><em>Record this tutorial: <code>asciinema rec quickstart.cast -c "bash docs/source/tutorials/scripts/quickstart.sh"</code></em></p>
</div>

## What You'll Learn

1. Installing obskit
2. Basic configuration
3. Adding metrics to a function
4. Viewing metrics output

## Step-by-Step

### 1. Create a new project

```bash
mkdir obskit-demo && cd obskit-demo
python -m venv venv
source venv/bin/activate
```

### 2. Install obskit

```bash
pip install obskit
```

### 3. Create your first instrumented script

```python
# demo.py
from obskit import configure, get_red_metrics, get_logger

# Configure obskit
configure(
    service_name="demo-service",
    log_format="console",  # Pretty output for demo
)

# Get components
metrics = get_red_metrics()
logger = get_logger()

# Simulate some operations
logger.info("starting_demo")

for i in range(5):
    with metrics.track_request("process_item"):
        # Simulate work
        import time
        time.sleep(0.1)
        logger.info("processed_item", item_number=i)

logger.info("demo_complete", total_items=5)
```

### 4. Run it

```bash
python demo.py
```

### 5. Output

You'll see structured logs with timing information:

```
2024-01-15 10:30:45 [info] starting_demo service=demo-service
2024-01-15 10:30:45 [info] processed_item service=demo-service item_number=0
...
2024-01-15 10:30:46 [info] demo_complete service=demo-service total_items=5
```

## Script for Recording

Save this as `quickstart.sh`:

```bash
#!/bin/bash
# Quickstart tutorial script

# Clear screen for clean recording
clear

echo "# obskit Quickstart Tutorial"
echo ""
sleep 1

echo "# Step 1: Create project"
mkdir -p /tmp/obskit-demo && cd /tmp/obskit-demo
echo "mkdir obskit-demo && cd obskit-demo"
sleep 1

echo ""
echo "# Step 2: Install obskit"
pip install obskit --quiet
echo "pip install obskit"
sleep 1

echo ""
echo "# Step 3: Create demo script"
cat > demo.py << 'EOF'
from obskit import configure, get_red_metrics, get_logger
import time

configure(service_name="demo", log_format="console")

metrics = get_red_metrics()
logger = get_logger()

logger.info("starting_demo")

for i in range(3):
    with metrics.track_request("process"):
        time.sleep(0.1)
        logger.info("processed", item=i)

logger.info("complete")
EOF
echo "cat demo.py"
cat demo.py
sleep 2

echo ""
echo "# Step 4: Run it!"
python demo.py

echo ""
echo "# Done! You now have metrics, logging, and tracing ready."
```

## Next Steps

- [FastAPI Integration](fastapi-integration.md) - Add to a web app
- [User Guide](../user-guide/concepts.md) - Learn core concepts
- [Configuration](../config/index.md) - Customize settings

