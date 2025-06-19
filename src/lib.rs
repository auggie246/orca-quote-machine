use pyo3::prelude::*;
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::Path;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ValidationError {
    #[error("File not found: {0}")]
    FileNotFound(String),
    #[error("Invalid file format: {0}")]
    InvalidFormat(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

impl From<ValidationError> for PyErr {
    fn from(err: ValidationError) -> PyErr {
        pyo3::exceptions::PyValueError::new_err(err.to_string())
    }
}

#[derive(Debug, Clone)]
#[pyclass]
pub struct ModelInfo {
    #[pyo3(get)]
    pub file_type: String,
    #[pyo3(get)]
    pub file_size: u64,
    #[pyo3(get)]
    pub is_valid: bool,
    #[pyo3(get)]
    pub error_message: Option<String>,
}

#[pymethods]
impl ModelInfo {
    fn __str__(&self) -> String {
        format!(
            "ModelInfo(type={}, size={}, valid={}, error={:?})",
            self.file_type, self.file_size, self.is_valid, self.error_message
        )
    }
}

/// Fast validation for STL files
#[pyfunction]
fn validate_stl(file_path: String) -> PyResult<ModelInfo> {
    let path = Path::new(&file_path);
    
    if !path.exists() {
        return Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size: 0,
            is_valid: false,
            error_message: Some("File not found".to_string()),
        });
    }

    let file_size = fs::metadata(path)?.len();
    
    // Read first few bytes to determine if binary or ASCII STL
    let data = fs::read(path)?;
    
    if data.len() < 84 {
        return Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: false,
            error_message: Some("File too small to be valid STL".to_string()),
        });
    }

    // Check if it's ASCII STL (starts with "solid")
    if data.starts_with(b"solid") {
        // For ASCII STL, use buffered reading to avoid loading entire file
        let file = fs::File::open(path)?;
        let reader = BufReader::new(file);
        
        let mut found_endsolid = false;
        for line in reader.lines() {
            let line = line?;
            if line.trim().starts_with("endsolid") {
                found_endsolid = true;
                break;
            }
        }
        
        return Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: found_endsolid,
            error_message: if found_endsolid { None } else { Some("Invalid ASCII STL format - missing endsolid".to_string()) },
        });
    }

    // Binary STL validation
    if data.len() < 84 {
        return Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: false,
            error_message: Some("Binary STL too small".to_string()),
        });
    }

    // Read triangle count from bytes 80-83
    let triangle_count = u32::from_le_bytes([data[80], data[81], data[82], data[83]]);
    let expected_size = 80 + 4 + (triangle_count * 50); // Header + count + triangles

    if data.len() as u32 != expected_size {
        return Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: false,
            error_message: Some(format!(
                "Binary STL size mismatch. Expected {}, got {}",
                expected_size,
                data.len()
            )),
        });
    }

    Ok(ModelInfo {
        file_type: "stl".to_string(),
        file_size,
        is_valid: true,
        error_message: None,
    })
}

/// Basic validation for OBJ files
#[pyfunction]
fn validate_obj(file_path: String) -> PyResult<ModelInfo> {
    let path = Path::new(&file_path);
    
    if !path.exists() {
        return Ok(ModelInfo {
            file_type: "obj".to_string(),
            file_size: 0,
            is_valid: false,
            error_message: Some("File not found".to_string()),
        });
    }

    let file_size = fs::metadata(path)?.len();
    let file = fs::File::open(path)?;
    let reader = BufReader::new(file);
    
    // Basic OBJ validation - check for vertices and faces using buffered reading
    let mut has_vertices = false;
    let mut has_faces = false;
    
    for line in reader.lines() {
        let line = line?;
        let trimmed = line.trim();
        
        if trimmed.starts_with("v ") {
            has_vertices = true;
        } else if trimmed.starts_with("f ") {
            has_faces = true;
        }
        
        // Early exit once both are found
        if has_vertices && has_faces {
            break;
        }
    }
    
    if has_vertices && has_faces {
        Ok(ModelInfo {
            file_type: "obj".to_string(),
            file_size,
            is_valid: true,
            error_message: None,
        })
    } else {
        Ok(ModelInfo {
            file_type: "obj".to_string(),
            file_size,
            is_valid: false,
            error_message: Some("Invalid OBJ format - missing vertices or faces".to_string()),
        })
    }
}

/// Basic validation for STEP files
#[pyfunction]
fn validate_step(file_path: String) -> PyResult<ModelInfo> {
    let path = Path::new(&file_path);
    
    if !path.exists() {
        return Ok(ModelInfo {
            file_type: "step".to_string(),
            file_size: 0,
            is_valid: false,
            error_message: Some("File not found".to_string()),
        });
    }

    let file_size = fs::metadata(path)?.len();
    let file = fs::File::open(path)?;
    let reader = BufReader::new(file);
    
    // Basic STEP validation - check for required headers using buffered reading
    let mut has_iso_header = false;
    let mut has_header_section = false;
    let mut has_data_section = false;
    let mut has_end_iso = false;
    let mut first_line = true;
    
    for line in reader.lines() {
        let line = line?;
        let trimmed = line.trim();
        
        // Check first line for ISO header
        if first_line {
            has_iso_header = trimmed.starts_with("ISO-10303");
            first_line = false;
        }
        
        // Check for required sections
        if trimmed == "HEADER;" {
            has_header_section = true;
        } else if trimmed == "DATA;" {
            has_data_section = true;
        } else if trimmed.starts_with("END-ISO-10303") {
            has_end_iso = true;
            break; // This should be near the end, so we can stop here
        }
    }
    
    if has_iso_header && has_header_section && has_data_section && has_end_iso {
        Ok(ModelInfo {
            file_type: "step".to_string(),
            file_size,
            is_valid: true,
            error_message: None,
        })
    } else {
        let mut missing_parts = Vec::new();
        if !has_iso_header { missing_parts.push("ISO header"); }
        if !has_header_section { missing_parts.push("HEADER section"); }
        if !has_data_section { missing_parts.push("DATA section"); }
        if !has_end_iso { missing_parts.push("END-ISO section"); }
        
        Ok(ModelInfo {
            file_type: "step".to_string(),
            file_size,
            is_valid: false,
            error_message: Some(format!("Invalid STEP format - missing: {}", missing_parts.join(", "))),
        })
    }
}

/// Validate 3D model file based on extension
#[pyfunction]
fn validate_3d_model(file_path: String) -> PyResult<ModelInfo> {
    let path = Path::new(&file_path);
    
    match path.extension().and_then(|ext| ext.to_str()) {
        Some("stl") | Some("STL") => validate_stl(file_path),
        Some("obj") | Some("OBJ") => validate_obj(file_path),
        Some("step") | Some("STEP") | Some("stp") | Some("STP") => validate_step(file_path),
        _ => Ok(ModelInfo {
            file_type: "unknown".to_string(),
            file_size: 0,
            is_valid: false,
            error_message: Some("Unsupported file type".to_string()),
        }),
    }
}

/// Python module definition
#[pymodule]
fn _rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_stl, m)?)?;
    m.add_function(wrap_pyfunction!(validate_obj, m)?)?;
    m.add_function(wrap_pyfunction!(validate_step, m)?)?;
    m.add_function(wrap_pyfunction!(validate_3d_model, m)?)?;
    m.add_class::<ModelInfo>()?;
    Ok(())
}