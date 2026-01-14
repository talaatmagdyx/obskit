# Architecture Diagrams

Visual representations of obskit's architecture and data flows.

## System Overview

```{mermaid}
flowchart TB
    subgraph Client["Client Layer"]
        Web[Web App]
        Mobile[Mobile App]
        API[API Client]
    end
    
    subgraph Gateway["API Gateway"]
        LB[Load Balancer]
        Auth[Auth Service]
    end
    
    subgraph Services["Microservices"]
        S1[Service A]
        S2[Service B]
        S3[Service C]
    end
    
    subgraph Data["Data Layer"]
        DB[(Database)]
        Cache[(Redis)]
        Queue[(Message Queue)]
    end
    
    subgraph Observability["Observability Stack"]
        Prom[(Prometheus)]
        Jaeger[(Jaeger)]
        Logs[(Log Aggregator)]
        Grafana[Grafana]
    end
    
    Web --> LB
    Mobile --> LB
    API --> LB
    LB --> Auth
    Auth --> S1
    Auth --> S2
    S1 --> S3
    S2 --> S3
    S3 --> DB
    S3 --> Cache
    S1 --> Queue
    
    S1 -.->|metrics| Prom
    S2 -.->|metrics| Prom
    S3 -.->|metrics| Prom
    
    S1 -.->|traces| Jaeger
    S2 -.->|traces| Jaeger
    S3 -.->|traces| Jaeger
    
    S1 -.->|logs| Logs
    S2 -.->|logs| Logs
    S3 -.->|logs| Logs
    
    Prom --> Grafana
    Jaeger --> Grafana
    Logs --> Grafana
```

## Metrics Collection Flow

```{mermaid}
flowchart LR
    subgraph Application
        Code[Your Code]
        RED[REDMetrics]
        Golden[GoldenSignals]
        USE[USEMetrics]
    end
    
    subgraph Registry["Prometheus Registry"]
        Counter[Counters]
        Histogram[Histograms]
        Gauge[Gauges]
    end
    
    subgraph Export["Export Methods"]
        HTTP[HTTP /metrics]
        Push[Push Gateway]
    end
    
    subgraph Storage
        Prometheus[(Prometheus)]
        Thanos[(Thanos/Cortex)]
    end
    
    Code --> RED
    Code --> Golden
    Code --> USE
    
    RED --> Counter
    RED --> Histogram
    Golden --> Counter
    Golden --> Histogram
    Golden --> Gauge
    USE --> Gauge
    
    Counter --> HTTP
    Histogram --> HTTP
    Gauge --> HTTP
    
    HTTP -->|pull| Prometheus
    Push -->|push| Prometheus
    Prometheus --> Thanos
```

## Distributed Tracing Flow

```{mermaid}
sequenceDiagram
    participant User
    participant Gateway
    participant ServiceA
    participant ServiceB
    participant Database
    participant Jaeger
    
    User->>Gateway: Request
    activate Gateway
    Note over Gateway: Create trace_id: abc123
    
    Gateway->>ServiceA: Forward (traceparent: abc123)
    activate ServiceA
    Note over ServiceA: Create span: service_a
    
    ServiceA->>ServiceB: Call (traceparent: abc123)
    activate ServiceB
    Note over ServiceB: Create span: service_b
    
    ServiceB->>Database: Query
    activate Database
    Note over ServiceB: Create span: db_query
    Database-->>ServiceB: Results
    deactivate Database
    
    ServiceB-->>ServiceA: Response
    deactivate ServiceB
    ServiceB-->>Jaeger: Export spans
    
    ServiceA-->>Gateway: Response
    deactivate ServiceA
    ServiceA-->>Jaeger: Export spans
    
    Gateway-->>User: Response
    deactivate Gateway
    Gateway-->>Jaeger: Export spans
    
    Note over Jaeger: Full trace: abc123<br/>Gateway → ServiceA → ServiceB → DB
```

## Circuit Breaker States

```{mermaid}
stateDiagram-v2
    [*] --> Closed: Initialize
    
    Closed --> Closed: Success
    note right of Closed
        Normal operation
        All requests pass through
        Failure counter tracks errors
    end note
    
    Closed --> Open: Failures >= Threshold
    note left of Open
        Circuit trips
        All requests fail immediately
        Timer starts
    end note
    
    Open --> HalfOpen: Recovery Timeout Elapsed
    note right of HalfOpen
        Test state
        Allow single request
        Decide based on result
    end note
    
    HalfOpen --> Closed: Test Request Succeeds
    HalfOpen --> Open: Test Request Fails
    
    Open --> Open: Requests Rejected
```

## Request Lifecycle

```{mermaid}
flowchart TB
    subgraph Ingress
        Request[Incoming Request]
    end
    
    subgraph Middleware["Middleware Layer"]
        Extract[Extract Trace Context]
        SetCorrelation[Set Correlation ID]
        StartSpan[Start Trace Span]
        StartMetrics[Start Metrics Timer]
        LogStart[Log Request Start]
    end
    
    subgraph Application["Application Layer"]
        Auth[Authentication]
        Validation[Validation]
        Business[Business Logic]
        External[External Calls]
    end
    
    subgraph Resilience["Resilience Layer"]
        CB[Circuit Breaker]
        Retry[Retry Logic]
        RateLimit[Rate Limiter]
    end
    
    subgraph Response["Response"]
        BuildResponse[Build Response]
        LogEnd[Log Request End]
        RecordMetrics[Record Metrics]
        EndSpan[End Trace Span]
        SendResponse[Send Response]
    end
    
    Request --> Extract
    Extract --> SetCorrelation
    SetCorrelation --> StartSpan
    StartSpan --> StartMetrics
    StartMetrics --> LogStart
    
    LogStart --> Auth
    Auth --> Validation
    Validation --> Business
    Business --> External
    
    External --> RateLimit
    RateLimit --> CB
    CB --> Retry
    
    Retry --> BuildResponse
    BuildResponse --> LogEnd
    LogEnd --> RecordMetrics
    RecordMetrics --> EndSpan
    EndSpan --> SendResponse
```

## Health Check Flow

```{mermaid}
flowchart TB
    subgraph Kubernetes
        Kubelet[Kubelet]
    end
    
    subgraph Pod
        App[Application]
        
        subgraph HealthChecker
            Liveness[Liveness Check]
            Readiness[Readiness Check]
        end
        
        subgraph Dependencies
            DB[(Database)]
            Cache[(Redis)]
            ExtAPI[External API]
        end
    end
    
    Kubelet -->|"/health"| Liveness
    Kubelet -->|"/ready"| Readiness
    
    Liveness -->|"is process alive?"| App
    
    Readiness -->|"can connect?"| DB
    Readiness -->|"can connect?"| Cache
    Readiness -->|"is available?"| ExtAPI
    
    Liveness -->|"200 OK / 503"| Kubelet
    Readiness -->|"200 OK / 503"| Kubelet
    
    Kubelet -->|"restart if unhealthy"| Pod
    Kubelet -->|"remove from LB if not ready"| Pod
```

## Error Budget Calculation

```{mermaid}
flowchart LR
    subgraph Inputs
        SLO[SLO Target: 99.9%]
        Window[Window: 30 days]
        Requests[Total Requests]
        Failures[Failed Requests]
    end
    
    subgraph Calculation
        Budget["Error Budget = 1 - SLO<br/>= 0.1%"]
        BudgetMinutes["Budget in minutes<br/>= 0.1% × 30 × 24 × 60<br/>= 43.2 minutes"]
        CurrentSLI["Current SLI<br/>= (Requests - Failures) / Requests"]
        Consumed["Budget Consumed<br/>= (SLO - CurrentSLI) / (1 - SLO)"]
    end
    
    subgraph Output
        Remaining["Budget Remaining<br/>= 1 - Consumed"]
        BurnRate["Burn Rate<br/>= Consumed / Time Elapsed"]
    end
    
    SLO --> Budget
    Window --> BudgetMinutes
    Requests --> CurrentSLI
    Failures --> CurrentSLI
    Budget --> Consumed
    CurrentSLI --> Consumed
    Consumed --> Remaining
    Consumed --> BurnRate
```

## Multi-Tenant Architecture

```{mermaid}
flowchart TB
    subgraph Clients
        T1[Tenant A]
        T2[Tenant B]
        T3[Tenant C]
    end
    
    subgraph Gateway
        LB[Load Balancer]
        TenantRouter[Tenant Router]
    end
    
    subgraph Services["Shared Services"]
        API[API Service]
        Worker[Worker Service]
    end
    
    subgraph Isolation["Tenant Isolation"]
        RL1[Rate Limiter A]
        RL2[Rate Limiter B]
        RL3[Rate Limiter C]
        CB1[Circuit Breaker A]
        CB2[Circuit Breaker B]
        CB3[Circuit Breaker C]
    end
    
    subgraph Data["Data Layer"]
        DB[(Shared DB)]
    end
    
    subgraph Metrics["Per-Tenant Metrics"]
        M1[Metrics: tenant_a]
        M2[Metrics: tenant_b]
        M3[Metrics: tenant_c]
    end
    
    T1 --> LB
    T2 --> LB
    T3 --> LB
    
    LB --> TenantRouter
    TenantRouter --> RL1
    TenantRouter --> RL2
    TenantRouter --> RL3
    
    RL1 --> CB1
    RL2 --> CB2
    RL3 --> CB3
    
    CB1 --> API
    CB2 --> API
    CB3 --> API
    
    API --> Worker
    Worker --> DB
    
    API --> M1
    API --> M2
    API --> M3
```

## Logging Pipeline

```{mermaid}
flowchart LR
    subgraph Application
        Code[Application Code]
        Logger[Structured Logger]
    end
    
    subgraph Processing["Log Processing"]
        Context[Add Context]
        Redact[PII Redaction]
        Format[JSON Formatting]
    end
    
    subgraph Output
        Stdout[stdout/stderr]
        File[Log Files]
    end
    
    subgraph Collection
        Agent[Log Agent]
    end
    
    subgraph Storage
        ES[(Elasticsearch)]
        Loki[(Loki)]
        CloudWatch[(CloudWatch)]
    end
    
    subgraph Visualization
        Kibana[Kibana]
        Grafana[Grafana]
    end
    
    Code --> Logger
    Logger --> Context
    Context --> Redact
    Redact --> Format
    Format --> Stdout
    Format --> File
    
    Stdout --> Agent
    File --> Agent
    
    Agent --> ES
    Agent --> Loki
    Agent --> CloudWatch
    
    ES --> Kibana
    Loki --> Grafana
```

## Deployment Architecture

```{mermaid}
flowchart TB
    subgraph Kubernetes["Kubernetes Cluster"]
        subgraph Namespace["app-namespace"]
            Deploy[Deployment]
            SVC[Service]
            CM[ConfigMap]
            Secret[Secret]
        end
        
        subgraph Monitoring["monitoring-namespace"]
            Prom[Prometheus]
            Grafana[Grafana]
            Jaeger[Jaeger]
        end
    end
    
    subgraph External
        Users[Users]
        Ingress[Ingress Controller]
    end
    
    Users --> Ingress
    Ingress --> SVC
    SVC --> Deploy
    Deploy --> CM
    Deploy --> Secret
    
    Deploy -.->|scrape| Prom
    Deploy -.->|traces| Jaeger
    Prom --> Grafana
    Jaeger --> Grafana
```

## Next Steps

- **[Overview](overview.md)** - Component descriptions
- **[Performance](../performance/index.md)** - Performance tuning
- **[Configuration](../config/index.md)** - Configuration options

