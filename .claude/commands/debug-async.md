# Debug Async Command

Comprehensive debugging for async/Celery issues in the application.

This command provides:
- Celery worker status and active tasks
- Redis connection diagnostics
- Async/sync boundary analysis
- Performance profiling commands
- Task queue monitoring

## Usage
```
/debug-async [component]
```

## Components
- `celery` - Worker status and task monitoring
- `redis` - Connection and latency testing  
- `tasks` - Active task analysis
- `performance` - System resource monitoring
- `all` - Complete diagnostic suite (default)

Automatically runs appropriate diagnostic commands based on current system state.