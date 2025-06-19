# Rust Calc Command

Creates a new Rust calculation function with proper PyO3 bindings.

This command scaffolds:
- Rust function with panic handling
- PyO3 Python bindings
- Python wrapper with error handling
- Type safety between Rust/Python boundary

## Usage
```
/rust-calc <function_name> <input_types> <output_type>
```

## Example
```
/rust-calc mesh_volume "Vec<f32>, Vec<u32>" f64
```

This generates the complete Rust calculation pattern with proper memory safety and error propagation.