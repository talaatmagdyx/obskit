# obskit-middleware-grpc

gRPC interceptors for obskit — adds correlation IDs and distributed tracing to gRPC services.

## Install

```bash
pip install obskit-middleware-grpc
```

## Quick start

```python
import grpc
from obskit.middleware.grpc import ObskitServerInterceptor

interceptor = ObskitServerInterceptor()
server = grpc.server(
    futures.ThreadPoolExecutor(max_workers=10),
    interceptors=[interceptor],
)
```
