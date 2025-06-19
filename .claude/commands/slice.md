# Slice Command

Creates a new slicing workflow using the API Task Offload pattern.

This command scaffolds:
- FastAPI endpoint for file upload
- Celery task for OrcaSlicer processing
- Status polling endpoint
- Pydantic models for request/response
- Proper async/sync boundary handling

## Usage
```
/slice <endpoint_name> <material_type>
```

## Example
```
/slice quote_model PLA
```

This generates the complete workflow for handling 3D model slicing with proper error handling, file cleanup, and progress tracking.