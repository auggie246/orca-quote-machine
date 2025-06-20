use pyo3::prelude::*;
use pyo3_asyncio::tokio::future_into_py;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};
use thiserror::Error;
use tokio::fs::File;
use tokio::io::{AsyncBufReadExt, BufReader as AsyncBufReader};

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

/// Enhanced slicing result with performance-critical calculations in Rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct SlicingResult {
    #[pyo3(get)]
    pub print_time_minutes: u32,
    #[pyo3(get)]
    pub filament_weight_grams: f32,
    #[pyo3(get)]
    pub layer_count: Option<u32>,
}

#[pymethods]
impl SlicingResult {
    #[staticmethod]
    #[pyo3(signature = (print_time_minutes, filament_weight_grams, layer_count=None))]
    fn create(
        print_time_minutes: u32,
        filament_weight_grams: f32,
        layer_count: Option<u32>,
    ) -> Self {
        Self {
            print_time_minutes,
            filament_weight_grams,
            layer_count,
        }
    }

    fn __str__(&self) -> String {
        format!(
            "SlicingResult(time={}min, filament={:.1}g, layers={:?})",
            self.print_time_minutes, self.filament_weight_grams, self.layer_count
        )
    }
}

/// File cleanup statistics
#[derive(Debug, Clone)]
#[pyclass]
pub struct CleanupStats {
    #[pyo3(get)]
    pub files_cleaned: u32,
    #[pyo3(get)]
    pub bytes_freed: u64,
}

#[pymethods]
impl CleanupStats {
    fn __str__(&self) -> String {
        format!(
            "CleanupStats(files={}, bytes={})",
            self.files_cleaned, self.bytes_freed
        )
    }
}

/// Cost breakdown calculation performed in Rust for enhanced performance
#[derive(Debug, Clone)]
#[pyclass]
pub struct CostBreakdown {
    #[pyo3(get)]
    pub material_type: String,
    #[pyo3(get)]
    pub filament_kg: f64,
    #[pyo3(get)]
    pub filament_grams: f32,
    #[pyo3(get)]
    pub print_time_hours: f64,
    #[pyo3(get)]
    pub print_time_minutes: u32,
    #[pyo3(get)]
    pub price_per_kg: f64,
    #[pyo3(get)]
    pub material_cost: f64,
    #[pyo3(get)]
    pub time_cost: f64,
    #[pyo3(get)]
    pub subtotal: f64,
    #[pyo3(get)]
    pub total_cost: f64,
    #[pyo3(get)]
    pub minimum_applied: bool,
    #[pyo3(get)]
    pub markup_percentage: f64,
}

#[pymethods]
impl CostBreakdown {
    fn __str__(&self) -> String {
        format!(
            "CostBreakdown(material={}, total=S${:.2})",
            self.material_type, self.total_cost
        )
    }
}

/// Parse time string to minutes using Rust regex for performance
fn parse_time_string_to_minutes(time_str: &str) -> u32 {
    // Create regexes for common time formats
    let hour_regex = Regex::new(r"(\d+)h").unwrap();
    let minute_regex = Regex::new(r"(\d+)m").unwrap();
    let minute_only_regex = Regex::new(r"^(\d+)$").unwrap();
    
    let clean_str = time_str.trim().to_lowercase();
    let mut minutes = 0;
    
    // Parse "1h 30m" format
    if let Some(hour_cap) = hour_regex.captures(&clean_str) {
        if let Ok(hours) = hour_cap[1].parse::<u32>() {
            minutes += hours * 60;
        }
    }
    
    if let Some(min_cap) = minute_regex.captures(&clean_str) {
        if let Ok(mins) = min_cap[1].parse::<u32>() {
            minutes += mins;
        }
    }
    
    // Parse minutes-only format if no hours/minutes pattern found
    if minutes == 0 {
        if let Some(min_only_cap) = minute_only_regex.captures(&clean_str) {
            if let Ok(mins) = min_only_cap[1].parse::<u32>() {
                minutes = mins;
            }
        }
    }
    
    if minutes == 0 { 60 } else { minutes } // Default to 1 hour if parsing fails
}

/// Parse filament weight from G-code comment using Rust regex
fn parse_filament_weight(line: &str) -> Option<f32> {
    let weight_regex = Regex::new(r"(\d+\.?\d*)\s*g").unwrap();
    
    if let Some(cap) = weight_regex.captures(line) {
        cap[1].parse::<f32>().ok()
    } else {
        None
    }
}

/// High-performance G-code and metadata parsing in Rust
#[pyfunction]
fn parse_slicer_output(py: Python, output_dir: String) -> PyResult<&PyAny> {
    future_into_py(py, async move {
        let dir_path = PathBuf::from(output_dir);
        let mut gcode_path: Option<PathBuf> = None;
        
        // Find the first .gcode file
        let mut entries = tokio::fs::read_dir(&dir_path).await?;
        while let Some(entry) = entries.next_entry().await? {
            if entry.path().extension().and_then(|s| s.to_str()) == Some("gcode") {
                gcode_path = Some(entry.path());
                break;
            }
        }
        
        let gcode_path = gcode_path.ok_or_else(|| {
            std::io::Error::new(std::io::ErrorKind::NotFound, "No .gcode file found")
        })?;
        
        let file = File::open(gcode_path).await?;
        let reader = AsyncBufReader::new(file);
        let mut lines = reader.lines();
        
        let mut print_time_minutes = 0u32;
        let mut filament_weight_grams = 0.0f32;
        let mut layer_count: Option<u32> = None;
        
        // Read first 200 lines for metadata (increased from 100 for better coverage)
        for _ in 0..200 {
            if let Some(line) = lines.next_line().await? {
                let lower_line = line.to_lowercase();
                
                // Parse print time
                if lower_line.contains("; estimated printing time") || lower_line.contains("; print time") {
                    if let Some(time_part) = line.split(':').last() {
                        print_time_minutes = parse_time_string_to_minutes(time_part.trim());
                    }
                }
                // Parse filament usage
                else if lower_line.contains("; filament used") || lower_line.contains("; material volume") {
                    if let Some(weight) = parse_filament_weight(&line) {
                        filament_weight_grams = weight;
                    }
                }
                // Parse layer count
                else if lower_line.contains("; layer_count") || lower_line.contains("; total layers") {
                    let layer_regex = Regex::new(r"(\d+)").unwrap();
                    if let Some(cap) = layer_regex.captures(&line) {
                        layer_count = cap[1].parse::<u32>().ok();
                    }
                }
            } else {
                break;
            }
        }
        
        // Set defaults if parsing failed
        if print_time_minutes == 0 {
            print_time_minutes = 60; // 1 hour default
        }
        if filament_weight_grams == 0.0 {
            filament_weight_grams = 20.0; // 20g default
        }
        
        Ok(SlicingResult {
            print_time_minutes,
            filament_weight_grams,
            layer_count,
        })
    })
}

/// Enhanced pricing calculation in Rust for performance
#[pyfunction]
fn calculate_quote_rust(
    print_time_minutes: u32,
    filament_weight_grams: f32,
    material_type: String,
    price_per_kg: f64,
    additional_time_hours: f64,
    price_multiplier: f64,
    minimum_price: f64,
) -> PyResult<CostBreakdown> {
    // Convert grams to kg
    let filament_kg = filament_weight_grams as f64 / 1000.0;
    
    // Convert minutes to hours and add additional time
    let print_time_hours = (print_time_minutes as f64 / 60.0) + additional_time_hours;
    
    // Calculate base costs
    let material_cost = filament_kg * price_per_kg;
    let time_cost = print_time_hours * price_per_kg; // Using material price as hourly rate
    
    // Calculate total with multiplier
    let subtotal = (material_cost + time_cost) * price_multiplier;
    
    // Apply minimum price
    let total_cost = if subtotal < minimum_price { minimum_price } else { subtotal };
    let minimum_applied = total_cost == minimum_price;
    
    // Calculate markup percentage
    let markup_percentage = (price_multiplier - 1.0) * 100.0;
    
    Ok(CostBreakdown {
        material_type,
        filament_kg,
        filament_grams: filament_weight_grams,
        print_time_hours,
        print_time_minutes,
        price_per_kg,
        material_cost,
        time_cost,
        subtotal,
        total_cost,
        minimum_applied,
        markup_percentage,
    })
}

/// High-performance file cleanup in Rust
#[pyfunction]
fn cleanup_old_files_rust(upload_dir: String, max_age_hours: u64) -> PyResult<CleanupStats> {
    let dir = Path::new(&upload_dir);
    let now = SystemTime::now();
    let max_age = Duration::from_secs(max_age_hours * 3600);
    
    let mut stats = CleanupStats {
        files_cleaned: 0,
        bytes_freed: 0,
    };
    
    if dir.is_dir() {
        for entry in fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() {
                let metadata = entry.metadata()?;
                if let Ok(modified) = metadata.modified() {
                    if now.duration_since(modified).unwrap_or_default() > max_age {
                        stats.bytes_freed += metadata.len();
                        fs::remove_file(path)?;
                        stats.files_cleaned += 1;
                    }
                }
            }
        }
    }
    
    Ok(stats)
}

/// Fix inefficient STL validation to use buffered I/O
#[pyfunction]
fn validate_stl_optimized(file_path: String) -> PyResult<ModelInfo> {
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
    let mut file = fs::File::open(path)?;

    // Read first 5 bytes to check for "solid"
    let mut header = [0u8; 5];
    file.read_exact(&mut header)?;

    // Reset cursor to the beginning of the file
    file.seek(SeekFrom::Start(0))?;

    if &header == b"solid" {
        // ASCII STL: Use a buffered reader on the existing file handle
        let reader = BufReader::new(file);
        let mut found_endsolid = false;
        for line in reader.lines() {
            if line?.trim().starts_with("endsolid") {
                found_endsolid = true;
                break;
            }
        }
        
        Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: found_endsolid,
            error_message: if found_endsolid { 
                None 
            } else { 
                Some("Invalid ASCII STL format - missing endsolid".to_string()) 
            },
        })
    } else {
        // Binary STL: Read the whole file now that we know we need to
        let mut data = Vec::new();
        file.read_to_end(&mut data)?;
        
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
            Ok(ModelInfo {
                file_type: "stl".to_string(),
                file_size,
                is_valid: false,
                error_message: Some(format!(
                    "Binary STL size mismatch. Expected {}, got {}",
                    expected_size,
                    data.len()
                )),
            })
        } else {
            Ok(ModelInfo {
                file_type: "stl".to_string(),
                file_size,
                is_valid: true,
                error_message: None,
            })
        }
    }
}

/// Python module definition
#[pymodule]
fn _rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // Original validation functions
    m.add_function(wrap_pyfunction!(validate_stl, m)?)?;
    m.add_function(wrap_pyfunction!(validate_obj, m)?)?;
    m.add_function(wrap_pyfunction!(validate_step, m)?)?;
    m.add_function(wrap_pyfunction!(validate_3d_model, m)?)?;
    
    // Enhanced performance functions
    m.add_function(wrap_pyfunction!(parse_slicer_output, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_quote_rust, m)?)?;
    m.add_function(wrap_pyfunction!(cleanup_old_files_rust, m)?)?;
    m.add_function(wrap_pyfunction!(validate_stl_optimized, m)?)?;
    
    // Data classes
    m.add_class::<ModelInfo>()?;
    m.add_class::<SlicingResult>()?;
    m.add_class::<CleanupStats>()?;
    m.add_class::<CostBreakdown>()?;
    
    Ok(())
}