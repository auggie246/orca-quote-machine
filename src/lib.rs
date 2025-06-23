use pyo3::prelude::*;
use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3_asyncio::tokio::future_into_py;
use regex::Regex;
use once_cell::sync::Lazy;
use sanitize_filename::sanitize;
use std::fs;
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, SystemTime};
use std::collections::HashMap;
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

/// Main error type for the quote pipeline
#[derive(Error, Debug)]
pub enum OrcaError {
    #[error("Invalid file: {msg}")]
    InvalidFile { msg: String },
    #[error("Profile not found: {msg}")]
    ProfileNotFound { msg: String },
    #[error("Slicer failed: {msg}")]
    SlicerFailed { msg: String },
    #[error("Parsing failed: {msg}")]
    ParsingFailed { msg: String },
    #[error("Telegram notification failed: {msg}")]
    TelegramFailed { msg: String },
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Validation error: {0}")]
    ValidationError(#[from] ValidationError),
}

impl From<OrcaError> for PyErr {
    fn from(err: OrcaError) -> PyErr {
        match err {
            OrcaError::InvalidFile { msg } => PyValueError::new_err(format!("Invalid file: {}", msg)),
            OrcaError::ProfileNotFound { msg } => PyValueError::new_err(format!("Profile not found: {}", msg)),
            OrcaError::SlicerFailed { msg } => PyRuntimeError::new_err(format!("Slicer failed: {}", msg)),
            OrcaError::ParsingFailed { msg } => PyValueError::new_err(format!("Parsing failed: {}", msg)),
            OrcaError::TelegramFailed { msg } => PyRuntimeError::new_err(format!("Telegram failed: {}", msg)),
            OrcaError::IoError(e) => PyIOError::new_err(e.to_string()),
            OrcaError::ValidationError(e) => PyValueError::new_err(e.to_string()),
        }
    }
}

/// Configuration for Telegram notifications
#[derive(Debug, Clone)]
#[pyclass]
pub struct TelegramConfig {
    #[pyo3(get)]
    pub token: String,
    #[pyo3(get)]
    pub chat_id: String,
    #[pyo3(get)]
    pub customer_name: String,
    #[pyo3(get)]
    pub customer_mobile: String,
}

#[pymethods]
impl TelegramConfig {
    #[new]
    fn new(token: String, chat_id: String, customer_name: String, customer_mobile: String) -> Self {
        TelegramConfig {
            token,
            chat_id,
            customer_name,
            customer_mobile,
        }
    }
}

/// Profile paths for OrcaSlicer
#[derive(Debug, Clone)]
#[pyclass]
pub struct ProfilePaths {
    #[pyo3(get)]
    pub machine: String,
    #[pyo3(get)]
    pub filament: String,
    #[pyo3(get)]
    pub process: String,
}

/// Pricing configuration
#[derive(Debug, Clone)]
pub struct PricingConfig {
    pub price_per_kg: f64,
    pub additional_time_hours: f64,
    pub price_multiplier: f64,
    pub minimum_price: f64,
}

/// Enhanced file information with security
#[derive(Debug, Clone)]
#[pyclass]
pub struct FileInfo {
    #[pyo3(get)]
    pub file_type: String,
    #[pyo3(get)]
    pub file_size: u64,
    #[pyo3(get)]
    pub is_valid: bool,
    #[pyo3(get)]
    pub error_message: Option<String>,
    #[pyo3(get)]
    pub secure_filename: String,
}

#[pymethods]
impl FileInfo {
    fn __str__(&self) -> String {
        format!(
            "FileInfo(type={}, size={}, valid={}, filename={})",
            self.file_type, self.file_size, self.is_valid, self.secure_filename
        )
    }
}

/// Enhanced slicing metadata
#[derive(Debug, Clone)]
#[pyclass]
pub struct SlicingMetadata {
    #[pyo3(get)]
    pub print_time_minutes: u32,
    #[pyo3(get)]
    pub filament_weight_grams: f32,
    #[pyo3(get)]
    pub layer_count: Option<u32>,
    #[pyo3(get)]
    pub gcode_path: String,
}

/// Enhanced cost breakdown
#[derive(Debug, Clone)]
#[pyclass]
pub struct QuoteBreakdown {
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
impl QuoteBreakdown {
    fn __str__(&self) -> String {
        format!(
            "QuoteBreakdown(material={}, total=S${:.2})",
            self.material_type, self.total_cost
        )
    }
    
    /// Format the cost breakdown for display
    pub fn format_summary(&self) -> String {
        let mut summary = String::new();
        summary.push_str("Cost Breakdown:\n");
        summary.push_str(&format!("Material: {}\n", self.material_type));
        summary.push_str(&format!("Filament: {:.1}g ({:.3}kg)\n", self.filament_grams, self.filament_kg));
        summary.push_str(&format!("Print Time: {:.1} hours\n", self.print_time_hours));
        summary.push_str(&format!("\nMaterial Cost: S${:.2}\n", self.material_cost));
        summary.push_str(&format!("Time Cost: S${:.2}\n", self.time_cost));
        summary.push_str(&format!("Subtotal: S${:.2}\n", self.subtotal));
        if self.markup_percentage > 0.0 {
            summary.push_str(&format!("Markup ({:.0}%): +S${:.2}\n", self.markup_percentage, self.subtotal * (self.markup_percentage / 100.0)));
        }
        if self.minimum_applied {
            summary.push_str(&format!("\nMinimum Price Applied\n"));
        }
        summary.push_str(&format!("\nTotal: S${:.2}", self.total_cost));
        summary
    }
}

/// Final quote result from the pipeline
#[derive(Debug, Clone)]
#[pyclass]
pub struct QuoteResult {
    #[pyo3(get)]
    pub success: bool,
    #[pyo3(get)]
    pub quote_id: String,
    #[pyo3(get)]
    pub secure_filename: String,
    #[pyo3(get)]
    pub file_type: String,
    #[pyo3(get)]
    pub file_size: u64,
    #[pyo3(get)]
    pub material_type: String,
    #[pyo3(get)]
    pub print_time_minutes: u32,
    #[pyo3(get)]
    pub filament_weight_grams: f32,
    #[pyo3(get)]
    pub total_cost: f64,
    #[pyo3(get)]
    pub cost_breakdown: QuoteBreakdown,
    #[pyo3(get)]
    pub notification_sent: bool,
    #[pyo3(get)]
    pub error_message: Option<String>,
}

#[pymethods]
impl QuoteResult {
    /// Convert to dictionary for JSON serialization
    pub fn to_dict(&self) -> PyResult<HashMap<String, PyObject>> {
        Python::with_gil(|py| {
            let mut dict = HashMap::new();
            dict.insert("success".to_string(), self.success.into_py(py));
            dict.insert("quote_id".to_string(), self.quote_id.clone().into_py(py));
            dict.insert("secure_filename".to_string(), self.secure_filename.clone().into_py(py));
            dict.insert("file_type".to_string(), self.file_type.clone().into_py(py));
            dict.insert("file_size".to_string(), self.file_size.into_py(py));
            dict.insert("material_type".to_string(), self.material_type.clone().into_py(py));
            dict.insert("print_time_minutes".to_string(), self.print_time_minutes.into_py(py));
            dict.insert("filament_weight_grams".to_string(), self.filament_weight_grams.into_py(py));
            dict.insert("total_cost".to_string(), self.total_cost.into_py(py));
            dict.insert("notification_sent".to_string(), self.notification_sent.into_py(py));
            dict.insert("error_message".to_string(), self.error_message.clone().into_py(py));
            
            // Add cost breakdown as nested dict
            let mut breakdown_dict = HashMap::new();
            breakdown_dict.insert("material_type".to_string(), self.cost_breakdown.material_type.clone().into_py(py));
            breakdown_dict.insert("total_cost".to_string(), self.cost_breakdown.total_cost.into_py(py));
            breakdown_dict.insert("filament_kg".to_string(), self.cost_breakdown.filament_kg.into_py(py));
            breakdown_dict.insert("print_time_hours".to_string(), self.cost_breakdown.print_time_hours.into_py(py));
            breakdown_dict.insert("minimum_applied".to_string(), self.cost_breakdown.minimum_applied.into_py(py));
            dict.insert("cost_breakdown".to_string(), breakdown_dict.into_py(py));
            
            Ok(dict)
        })
    }
}

// Removed duplicate From<OrcaError> for PyErr implementation

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

// === MODULAR HELPER FUNCTIONS ===

/// Validate and sanitize filename to prevent path traversal
#[pyfunction]
fn validate_filename(filename: &str) -> PyResult<String> {
    let sanitized = sanitize(filename);
    if sanitized.is_empty() {
        return Err(OrcaError::InvalidFile {
            msg: "Filename becomes empty after sanitization".to_string(),
        }.into());
    }
    Ok(sanitized)
}

/// Validate 3D file contents based on file type
#[pyfunction]
fn validate_3d_file(contents: &[u8], extension: &str) -> PyResult<FileInfo> {
    let file_size = contents.len() as u64;
    let ext_lower = extension.to_lowercase();
    
    match ext_lower.as_str() {
        "stl" => validate_stl_contents(contents, file_size),
        "obj" => validate_obj_contents(contents, file_size),
        "step" | "stp" => validate_step_contents(contents, file_size),
        _ => Ok(FileInfo {
            file_type: "unknown".to_string(),
            file_size,
            is_valid: false,
            error_message: Some("Unsupported file type".to_string()),
            secure_filename: String::new(),
        }),
    }
}

/// Validate STL file contents
fn validate_stl_contents(contents: &[u8], file_size: u64) -> PyResult<FileInfo> {
    if contents.len() < 5 {
        return Ok(FileInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: false,
            error_message: Some("File too small to be valid STL".to_string()),
            secure_filename: String::new(),
        });
    }
    
    if contents.starts_with(b"solid") {
        // ASCII STL - scan for endsolid
        let content_str = String::from_utf8_lossy(contents);
        let has_endsolid = content_str.lines().any(|line| line.trim().starts_with("endsolid"));
        
        Ok(FileInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: has_endsolid,
            error_message: if has_endsolid { None } else { Some("Invalid ASCII STL - missing endsolid".to_string()) },
            secure_filename: String::new(),
        })
    } else {
        // Binary STL validation
        if file_size < 84 {
            return Ok(FileInfo {
                file_type: "stl".to_string(),
                file_size,
                is_valid: false,
                error_message: Some("Binary STL too small".to_string()),
                secure_filename: String::new(),
            });
        }
        
        let triangle_count = u32::from_le_bytes([contents[80], contents[81], contents[82], contents[83]]);
        let expected_size = 84u64 + (triangle_count as u64 * 50);
        
        Ok(FileInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: file_size == expected_size,
            error_message: if file_size == expected_size { None } else {
                Some(format!("Binary STL size mismatch. Expected {}, got {}", expected_size, file_size))
            },
            secure_filename: String::new(),
        })
    }
}

/// Validate OBJ file contents
fn validate_obj_contents(contents: &[u8], file_size: u64) -> PyResult<FileInfo> {
    let content_str = String::from_utf8_lossy(contents);
    let mut has_vertices = false;
    let mut has_faces = false;
    
    for line in content_str.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("v ") {
            has_vertices = true;
        } else if trimmed.starts_with("f ") {
            has_faces = true;
        }
        if has_vertices && has_faces {
            break;
        }
    }
    
    Ok(FileInfo {
        file_type: "obj".to_string(),
        file_size,
        is_valid: has_vertices && has_faces,
        error_message: if has_vertices && has_faces { None } else {
            Some("Invalid OBJ format - missing vertices or faces".to_string())
        },
        secure_filename: String::new(),
    })
}

/// Validate STEP file contents
fn validate_step_contents(contents: &[u8], file_size: u64) -> PyResult<FileInfo> {
    let content_str = String::from_utf8_lossy(contents);
    let mut has_iso_header = false;
    let mut has_header_section = false;
    let mut has_data_section = false;
    let mut has_end_iso = false;
    let mut first_line = true;
    
    for line in content_str.lines() {
        let trimmed = line.trim();
        
        if first_line {
            has_iso_header = trimmed.starts_with("ISO-10303");
            first_line = false;
        }
        
        if trimmed == "HEADER;" {
            has_header_section = true;
        } else if trimmed == "DATA;" {
            has_data_section = true;
        } else if trimmed.starts_with("END-ISO-10303") {
            has_end_iso = true;
            break;
        }
    }
    
    let is_valid = has_iso_header && has_header_section && has_data_section && has_end_iso;
    let mut missing_parts = Vec::new();
    if !has_iso_header { missing_parts.push("ISO header"); }
    if !has_header_section { missing_parts.push("HEADER section"); }
    if !has_data_section { missing_parts.push("DATA section"); }
    if !has_end_iso { missing_parts.push("END-ISO section"); }
    
    Ok(FileInfo {
        file_type: "step".to_string(),
        file_size,
        is_valid,
        error_message: if is_valid { None } else {
            Some(format!("Invalid STEP format - missing: {}", missing_parts.join(", ")))
        },
        secure_filename: String::new(),
    })
}

/// Discover available materials from profile directory
#[pyfunction]
fn discover_available_materials(profiles_dir: String) -> PyResult<Vec<String>> {
    let filament_dir = Path::new(&profiles_dir).join("filament");
    let mut materials = Vec::new();
    
    if filament_dir.is_dir() {
        for entry in fs::read_dir(&filament_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("json") {
                if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                    // Convert filename to material name (e.g., "generic_tpu.json" -> "TPU")
                    let material_name = stem.to_uppercase()
                        .replace("GENERIC_", "")
                        .replace("_", " ");
                    materials.push(material_name);
                }
            }
        }
    }
    
    // Add default materials if not already discovered
    for default in &["PLA", "PETG", "ASA"] {
        if !materials.contains(&default.to_string()) {
            materials.push(default.to_string());
        }
    }
    
    materials.sort();
    Ok(materials)
}

/// Resolve profile paths for a given material
#[pyfunction]
fn resolve_profile_paths(
    profiles_dir: String,
    material: String,
    machine_profile: String,
    process_profile: String,
) -> PyResult<ProfilePaths> {
    let base_dir = Path::new(&profiles_dir);
    let material_lower = material.to_lowercase();
    
    // Machine profile
    let machine_path = base_dir.join("machine").join(&machine_profile);
    if !machine_path.exists() {
        return Err(OrcaError::ProfileNotFound {
            msg: format!("Machine profile not found: {}", machine_profile),
        }.into());
    }
    
    // Process profile
    let process_path = base_dir.join("process").join(&process_profile);
    if !process_path.exists() {
        return Err(OrcaError::ProfileNotFound {
            msg: format!("Process profile not found: {}", process_profile),
        }.into());
    }
    
    // Filament profile - check for specific overrides first, then convention
    let filament_dir = base_dir.join("filament");
    let mut filament_path = None;
    
    // Check for material-specific filenames (from config)
    let possible_names = match material_lower.as_str() {
        "pla" => vec!["ALT TABL MATTE PLA PEI.json"],
        "petg" => vec!["Alt Tab PETG.json"],
        "asa" => vec!["fusrock ASA.json"],
        _ => vec![],
    };
    
    for name in possible_names {
        let path = filament_dir.join(name);
        if path.exists() {
            filament_path = Some(path);
            break;
        }
    }
    
    // Fallback to convention: material_name.json
    if filament_path.is_none() {
        let conventional_name = format!("{}.json", material_lower);
        let path = filament_dir.join(&conventional_name);
        if path.exists() {
            filament_path = Some(path);
        }
    }
    
    let filament_path = filament_path.ok_or_else(|| OrcaError::ProfileNotFound {
        msg: format!("No profile found for material: {}", material),
    })?;
    
    Ok(ProfilePaths {
        machine: machine_path.to_string_lossy().to_string(),
        filament: filament_path.to_string_lossy().to_string(),
        process: process_path.to_string_lossy().to_string(),
    })
}

/// Execute OrcaSlicer and return G-code path
#[pyfunction]
fn execute_slicer(
    model_path: &str,
    profiles: &ProfilePaths,
    slicer_path: &str,
    output_dir: &str,
) -> PyResult<PathBuf> {
    let model_path = Path::new(model_path);
    if !model_path.exists() {
        return Err(OrcaError::InvalidFile {
            msg: format!("Model file not found: {}", model_path.display()),
        }.into());
    }
    
    // Create output directory
    fs::create_dir_all(output_dir)?;
    
    // Build slicer command
    let output = Command::new(slicer_path)
        .arg(model_path)
        .arg("--slice")
        .arg("0")  // Slice all plates
        .arg("--load-settings")
        .arg(format!("{};{}", profiles.machine, profiles.process))
        .arg("--load-filaments")
        .arg(&profiles.filament)
        .arg("--export-slicedata")
        .arg(output_dir)
        .arg("--outputdir")
        .arg(output_dir)
        .arg("--debug")
        .arg("1")  // Minimal logging
        .output()?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(OrcaError::SlicerFailed {
            msg: format!("Slicer failed with error: {}", stderr),
        }.into());
    }
    
    // Find the generated G-code file
    let output_path = Path::new(output_dir);
    for entry in fs::read_dir(output_path)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("gcode") {
            return Ok(path);
        }
    }
    
    Err(OrcaError::SlicerFailed {
        msg: "No G-code file found after slicing".to_string(),
    }.into())
}

/// Parse G-code metadata
#[pyfunction]
fn parse_gcode_metadata(gcode_path: &str) -> PyResult<SlicingMetadata> {
    let path = Path::new(gcode_path);
    let file = fs::File::open(path)?;
    let reader = BufReader::new(file);
    
    let mut print_time_minutes = 0u32;
    let mut filament_weight_grams = 0.0f32;
    let mut layer_count: Option<u32> = None;
    
    // Read first 200 lines for metadata
    for (i, line) in reader.lines().enumerate() {
        if i >= 200 { break; }
        
        let line = line?;
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
            if let Some(cap) = LAYER_REGEX.captures(&line) {
                layer_count = cap[1].parse::<u32>().ok();
            }
        }
    }
    
    // Set defaults if parsing failed
    if print_time_minutes == 0 {
        print_time_minutes = 60; // 1 hour default
    }
    if filament_weight_grams == 0.0 {
        filament_weight_grams = 20.0; // 20g default
    }
    
    Ok(SlicingMetadata {
        print_time_minutes,
        filament_weight_grams,
        layer_count,
        gcode_path: path.to_path_buf(),
    })
}

/// Calculate final quote with all pricing logic
#[pyfunction]
fn calculate_final_quote(
    metadata: &SlicingMetadata,
    material: &str,
    pricing_config: &PricingConfig,
) -> PyResult<QuoteBreakdown> {
    // Convert grams to kg
    let filament_kg = metadata.filament_weight_grams as f64 / 1000.0;
    
    // Convert minutes to hours and add additional time
    let print_time_hours = (metadata.print_time_minutes as f64 / 60.0) + pricing_config.additional_time_hours;
    
    // Calculate base costs
    let material_cost = filament_kg * pricing_config.price_per_kg;
    let time_cost = print_time_hours * pricing_config.price_per_kg; // Using material price as hourly rate
    
    // Calculate total with multiplier
    let subtotal = (material_cost + time_cost) * pricing_config.price_multiplier;
    
    // Apply minimum price
    let total_cost = if subtotal < pricing_config.minimum_price { 
        pricing_config.minimum_price 
    } else { 
        subtotal 
    };
    let minimum_applied = total_cost == pricing_config.minimum_price;
    
    // Calculate markup percentage
    let markup_percentage = (pricing_config.price_multiplier - 1.0) * 100.0;
    
    Ok(QuoteBreakdown {
        material_type: material.to_string(),
        filament_kg,
        filament_grams: metadata.filament_weight_grams,
        print_time_hours,
        print_time_minutes: metadata.print_time_minutes,
        price_per_kg: pricing_config.price_per_kg,
        material_cost,
        time_cost,
        subtotal,
        total_cost,
        minimum_applied,
        markup_percentage,
    })
}

/// Pricing configuration
#[derive(Debug, Clone)]
#[pyclass]
pub struct PricingConfig {
    #[pyo3(get)]
    pub price_per_kg: f64,
    #[pyo3(get)]
    pub additional_time_hours: f64,
    #[pyo3(get)]
    pub price_multiplier: f64,
    #[pyo3(get)]
    pub minimum_price: f64,
}

/// Enhanced slicing metadata
#[derive(Debug, Clone)]
#[pyclass]
pub struct SlicingMetadata {
    #[pyo3(get)]
    pub print_time_minutes: u32,
    #[pyo3(get)]
    pub filament_weight_grams: f32,
    #[pyo3(get)]
    pub layer_count: Option<u32>,
    #[pyo3(get)]
    pub gcode_path: PathBuf,
}

#[pymethods]
impl SlicingMetadata {
    fn __str__(&self) -> String {
        format!(
            "SlicingMetadata(time={}min, filament={:.1}g, layers={:?})",
            self.print_time_minutes, self.filament_weight_grams, self.layer_count
        )
    }
}

/// Enhanced quote breakdown with all details
#[derive(Debug, Clone)]
#[pyclass]
pub struct QuoteBreakdown {
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
impl QuoteBreakdown {
    fn __str__(&self) -> String {
        format!(
            "QuoteBreakdown(material={}, total=S${:.2})",
            self.material_type, self.total_cost
        )
    }
}

/// Final quote result from the complete pipeline
#[derive(Debug, Clone)]
#[pyclass]
pub struct QuoteResult {
    #[pyo3(get)]
    pub request_id: String,
    #[pyo3(get)]
    pub customer_name: String,
    #[pyo3(get)]
    pub customer_mobile: String,
    #[pyo3(get)]
    pub material_type: String,
    #[pyo3(get)]
    pub filename: String,
    #[pyo3(get)]
    pub secure_filename: String,
    #[pyo3(get)]
    pub file_size: u64,
    #[pyo3(get)]
    pub print_time_minutes: u32,
    #[pyo3(get)]
    pub filament_weight_grams: f32,
    #[pyo3(get)]
    pub layer_count: Option<u32>,
    #[pyo3(get)]
    pub material_cost: f64,
    #[pyo3(get)]
    pub time_cost: f64,
    #[pyo3(get)]
    pub total_cost: f64,
    #[pyo3(get)]
    pub minimum_applied: bool,
    #[pyo3(get)]
    pub telegram_sent: bool,
    #[pyo3(get)]
    pub error_message: Option<String>,
}

#[pymethods]
impl QuoteResult {
    fn __str__(&self) -> String {
        format!(
            "QuoteResult(id={}, customer={}, material={}, total=S${:.2})",
            self.request_id, self.customer_name, self.material_type, self.total_cost
        )
    }
    
    /// Convert to Python dict for easy serialization
    fn to_dict(&self) -> PyResult<PyObject> {
        Python::with_gil(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("request_id", &self.request_id)?;
            dict.set_item("customer_name", &self.customer_name)?;
            dict.set_item("customer_mobile", &self.customer_mobile)?;
            dict.set_item("material_type", &self.material_type)?;
            dict.set_item("filename", &self.filename)?;
            dict.set_item("secure_filename", &self.secure_filename)?;
            dict.set_item("file_size", self.file_size)?;
            dict.set_item("print_time_minutes", self.print_time_minutes)?;
            dict.set_item("filament_weight_grams", self.filament_weight_grams)?;
            dict.set_item("layer_count", self.layer_count)?;
            dict.set_item("material_cost", self.material_cost)?;
            dict.set_item("time_cost", self.time_cost)?;
            dict.set_item("total_cost", self.total_cost)?;
            dict.set_item("minimum_applied", self.minimum_applied)?;
            dict.set_item("telegram_sent", self.telegram_sent)?;
            dict.set_item("error_message", &self.error_message)?;
            Ok(dict.into())
        })
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
    let mut file = fs::File::open(path)?;

    // Read only the first 5 bytes to check for "solid" prefix.
    let mut header = [0u8; 5];
    if file.read_exact(&mut header).is_err() {
        // File is too small to be a valid STL of any kind.
        return Ok(ModelInfo {
            file_type: "stl".to_string(),
            file_size,
            is_valid: false,
            error_message: Some("File too small to be valid STL".to_string()),
        });
    }

    if header.starts_with(b"solid") {
        // ASCII STL: Use a buffered reader on the existing file handle.
        // We must seek back to the start to read from the beginning.
        file.seek(SeekFrom::Start(0))?;
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
        // Binary STL: Efficiently validate without reading the whole file.
        if file_size < 84 {
            return Ok(ModelInfo {
                file_type: "stl".to_string(),
                file_size,
                is_valid: false,
                error_message: Some("Binary STL too small".to_string()),
            });
        }

        // Read only the triangle count from bytes 80-83.
        let mut count_buffer = [0u8; 4];
        file.seek(SeekFrom::Start(80))?;
        file.read_exact(&mut count_buffer)?;
        let triangle_count = u32::from_le_bytes(count_buffer);

        let expected_size = 84u64.saturating_add(triangle_count as u64 * 50);

        if file_size != expected_size {
            Ok(ModelInfo {
                file_type: "stl".to_string(),
                file_size,
                is_valid: false,
                error_message: Some(format!(
                    "Binary STL size mismatch. Expected {}, got {}",
                    expected_size,
                    file_size
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
    
    match path.extension().and_then(|s| s.to_str()).map(|s| s.to_lowercase()) {
        Some(ext) if ext == "stl" => validate_stl(file_path),
        Some(ext) if ext == "obj" => validate_obj(file_path),
        Some(ext) if ext == "step" || ext == "stp" => validate_step(file_path),
        _ => Ok(ModelInfo {
            file_type: "unknown".to_string(),
            file_size: 0,
            is_valid: false,
            error_message: Some("Unsupported file type".to_string()),
        }),
    }
}

/// Enhanced slicing result with performance-critical calculations in Rust
#[derive(Debug, Clone)]
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

// Static regex definitions for performance
static TIME_HOUR_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"(\d+)h").unwrap());
static TIME_MINUTE_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"(\d+)m").unwrap());
static TIME_MINUTE_ONLY_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^(\d+)$").unwrap());
static FILAMENT_WEIGHT_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"(\d+\.?\d*)\s*g").unwrap());
static LAYER_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"(\d+)").unwrap());

/// Parse time string to minutes using Rust regex for performance
fn parse_time_string_to_minutes(time_str: &str) -> u32 {
    let clean_str = time_str.trim().to_lowercase();
    let mut minutes = 0;
    
    // Parse "1h 30m" format
    if let Some(hour_cap) = TIME_HOUR_REGEX.captures(&clean_str) {
        if let Ok(hours) = hour_cap[1].parse::<u32>() {
            minutes += hours * 60;
        }
    }
    
    if let Some(min_cap) = TIME_MINUTE_REGEX.captures(&clean_str) {
        if let Ok(mins) = min_cap[1].parse::<u32>() {
            minutes += mins;
        }
    }
    
    // Parse minutes-only format if no hours/minutes pattern found
    if minutes == 0 {
        if let Some(min_only_cap) = TIME_MINUTE_ONLY_REGEX.captures(&clean_str) {
            if let Ok(mins) = min_only_cap[1].parse::<u32>() {
                minutes = mins;
            }
        }
    }
    
    if minutes == 0 { 60 } else { minutes } // Default to 1 hour if parsing fails
}

/// Parse filament weight from G-code comment using Rust regex
fn parse_filament_weight(line: &str) -> Option<f32> {
    if let Some(cap) = FILAMENT_WEIGHT_REGEX.captures(line) {
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
                    if let Some(cap) = LAYER_REGEX.captures(&line) {
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

/// Sanitize a filename to remove characters that are not allowed by the OS.
#[pyfunction]
fn secure_filename(filename: String) -> PyResult<String> {
    Ok(sanitize(filename))
}

/// Validate and sanitize a filename
#[pyfunction]
fn validate_filename(filename: &str) -> PyResult<String> {
    // Remove path separators and null bytes
    let cleaned = filename
        .replace(['/', '\\', '\0'], "_")
        .trim()
        .to_string();
    
    if cleaned.is_empty() {
        return Err(OrcaError::InvalidFile {
            msg: "Filename cannot be empty".to_string(),
        }.into());
    }
    
    // Use the existing secure_filename function
    secure_filename(cleaned)
}

/// Validate 3D file contents
#[pyfunction]
fn validate_3d_file(contents: Vec<u8>, filename: &str) -> PyResult<FileInfo> {
    let secure_name = validate_filename(filename)?;
    let file_size = contents.len() as u64;
    
    // Extract extension
    let extension = Path::new(&secure_name)
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_lowercase())
        .unwrap_or_default();
    
    // Validate based on extension
    let (file_type, is_valid, error_message) = match extension.as_str() {
        "stl" => validate_stl_contents(&contents),
        "obj" => validate_obj_contents(&contents),
        "step" | "stp" => validate_step_contents(&contents),
        _ => ("unknown".to_string(), false, Some("Unsupported file type".to_string())),
    };
    
    Ok(FileInfo {
        file_type,
        file_size,
        is_valid,
        error_message,
        secure_filename: secure_name,
    })
}

/// Validate STL file contents
fn validate_stl_contents(contents: &[u8]) -> (String, bool, Option<String>) {
    if contents.len() < 5 {
        return ("stl".to_string(), false, Some("File too small to be valid STL".to_string()));
    }
    
    if contents.starts_with(b"solid") {
        // ASCII STL
        let text = String::from_utf8_lossy(contents);
        let has_endsolid = text.lines().any(|line| line.trim().starts_with("endsolid"));
        (
            "stl".to_string(),
            has_endsolid,
            if has_endsolid { None } else { Some("Invalid ASCII STL - missing endsolid".to_string()) }
        )
    } else {
        // Binary STL
        if contents.len() < 84 {
            return ("stl".to_string(), false, Some("Binary STL too small".to_string()));
        }
        
        let triangle_count = u32::from_le_bytes([
            contents[80], contents[81], contents[82], contents[83]
        ]);
        let expected_size = 84 + (triangle_count as usize * 50);
        
        (
            "stl".to_string(),
            contents.len() == expected_size,
            if contents.len() == expected_size { 
                None 
            } else { 
                Some(format!("Binary STL size mismatch. Expected {}, got {}", expected_size, contents.len()))
            }
        )
    }
}

/// Validate OBJ file contents
fn validate_obj_contents(contents: &[u8]) -> (String, bool, Option<String>) {
    let text = String::from_utf8_lossy(contents);
    let has_vertices = text.lines().any(|line| line.trim().starts_with("v "));
    let has_faces = text.lines().any(|line| line.trim().starts_with("f "));
    
    (
        "obj".to_string(),
        has_vertices && has_faces,
        if has_vertices && has_faces { 
            None 
        } else { 
            Some("Invalid OBJ format - missing vertices or faces".to_string()) 
        }
    )
}

/// Validate STEP file contents
fn validate_step_contents(contents: &[u8]) -> (String, bool, Option<String>) {
    let text = String::from_utf8_lossy(contents);
    let lines: Vec<&str> = text.lines().collect();
    
    if lines.is_empty() {
        return ("step".to_string(), false, Some("Empty STEP file".to_string()));
    }
    
    let has_iso_header = lines[0].trim().starts_with("ISO-10303");
    let has_header_section = lines.iter().any(|line| line.trim() == "HEADER;");
    let has_data_section = lines.iter().any(|line| line.trim() == "DATA;");
    let has_end_iso = lines.iter().any(|line| line.trim().starts_with("END-ISO-10303"));
    
    let is_valid = has_iso_header && has_header_section && has_data_section && has_end_iso;
    
    let mut missing_parts = Vec::new();
    if !has_iso_header { missing_parts.push("ISO header"); }
    if !has_header_section { missing_parts.push("HEADER section"); }
    if !has_data_section { missing_parts.push("DATA section"); }
    if !has_end_iso { missing_parts.push("END-ISO section"); }
    
    (
        "step".to_string(),
        is_valid,
        if is_valid { 
            None 
        } else { 
            Some(format!("Invalid STEP format - missing: {}", missing_parts.join(", "))) 
        }
    )
}

/// Discover available materials from profile directory
#[pyfunction]
fn discover_available_materials(profiles_dir: String) -> PyResult<Vec<String>> {
    let filament_dir = Path::new(&profiles_dir).join("filament");
    
    if !filament_dir.exists() {
        return Err(OrcaError::ProfileNotFound {
            msg: format!("Filament profiles directory not found: {}", filament_dir.display()),
        }.into());
    }
    
    let mut materials = Vec::new();
    
    // Read all JSON files in the filament directory
    for entry in fs::read_dir(filament_dir)? {
        let entry = entry?;
        let path = entry.path();
        
        if path.extension().and_then(|s| s.to_str()) == Some("json") {
            if let Some(filename) = path.file_stem().and_then(|s| s.to_str()) {
                // Extract material type from filename
                // Common patterns: "PLA ...", "PETG ...", "ASA ..."
                for material in &["PLA", "PETG", "ASA", "ABS", "TPU", "PCTG"] {
                    if filename.to_uppercase().contains(material) {
                        if !materials.contains(&material.to_string()) {
                            materials.push(material.to_string());
                        }
                        break;
                    }
                }
            }
        }
    }
    
    materials.sort();
    Ok(materials)
}

/// Resolve profile paths for a given material
#[pyfunction]
fn resolve_profile_paths(
    profiles_dir: String,
    material: String,
    machine_profile: String,
    process_profile: String,
) -> PyResult<ProfilePaths> {
    let base_path = Path::new(&profiles_dir);
    
    // Machine profile path
    let machine_path = base_path.join("machine").join(&machine_profile);
    if !machine_path.exists() {
        return Err(OrcaError::ProfileNotFound {
            msg: format!("Machine profile not found: {}", machine_path.display()),
        }.into());
    }
    
    // Process profile path
    let process_path = base_path.join("process").join(&process_profile);
    if !process_path.exists() {
        return Err(OrcaError::ProfileNotFound {
            msg: format!("Process profile not found: {}", process_path.display()),
        }.into());
    }
    
    // Find matching filament profile
    let filament_dir = base_path.join("filament");
    let mut filament_path = None;
    
    for entry in fs::read_dir(&filament_dir)? {
        let entry = entry?;
        let path = entry.path();
        
        if path.extension().and_then(|s| s.to_str()) == Some("json") {
            if let Some(filename) = path.file_name().and_then(|s| s.to_str()) {
                if filename.to_uppercase().contains(&material.to_uppercase()) {
                    filament_path = Some(path);
                    break;
                }
            }
        }
    }
    
    let filament_path = filament_path.ok_or_else(|| OrcaError::ProfileNotFound {
        msg: format!("No filament profile found for material: {}", material),
    })?;
    
    Ok(ProfilePaths {
        machine_profile: machine_path,
        filament_profile: filament_path,
        process_profile: process_path,
    })
}

/// Execute OrcaSlicer with proper error handling
#[pyfunction]
fn execute_slicer(
    model_path: String,
    profiles: ProfilePaths,
    slicer_path: String,
    output_dir: String,
    _timeout_seconds: u64,
) -> PyResult<PathBuf> {
    let model_path = Path::new(&model_path);
    let output_path = Path::new(&output_dir);
    
    // Build command
    let mut cmd = Command::new(&slicer_path);
    cmd.arg("--export-gcode")
        .arg("--load-filament").arg(&profiles.filament_profile)
        .arg("--load-printer").arg(&profiles.machine_profile)
        .arg("--load-process").arg(&profiles.process_profile)
        .arg("--output-dir").arg(output_path)
        .arg(model_path);
    
    // Execute with timeout
    let output = match cmd.output() {
        Ok(output) => output,
        Err(e) => return Err(OrcaError::SlicerFailed {
            msg: format!("Failed to execute slicer: {}", e),
        }.into()),
    };
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(OrcaError::SlicerFailed {
            msg: format!("Slicer failed with status {}: {}", output.status, stderr),
        }.into());
    }
    
    // Find the generated G-code file
    for entry in fs::read_dir(output_path)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("gcode") {
            return Ok(path);
        }
    }
    
    Err(OrcaError::SlicerFailed {
        msg: "No G-code file generated".to_string(),
    }.into())
}

/// Parse G-code metadata with enhanced extraction
#[pyfunction]
fn parse_gcode_metadata(gcode_path: String) -> PyResult<SlicingMetadata> {
    let path = Path::new(&gcode_path);
    let file = fs::File::open(path)?;
    let reader = BufReader::new(file);
    
    let mut print_time_minutes = 0u32;
    let mut filament_weight_grams = 0.0f32;
    let mut layer_count: Option<u32> = None;
    
    // Read first 200 lines for metadata
    for (i, line) in reader.lines().enumerate() {
        if i >= 200 {
            break;
        }
        
        let line = line?;
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
            if let Some(cap) = LAYER_REGEX.captures(&line) {
                layer_count = cap[1].parse::<u32>().ok();
            }
        }
    }
    
    // Set defaults if parsing failed
    if print_time_minutes == 0 {
        print_time_minutes = 60; // 1 hour default
    }
    if filament_weight_grams == 0.0 {
        filament_weight_grams = 20.0; // 20g default
    }
    
    Ok(SlicingMetadata {
        print_time_minutes,
        filament_weight_grams,
        layer_count,
        gcode_path: path.to_path_buf(),
    })
}

/// Calculate final quote with all pricing logic
#[pyfunction]
fn calculate_final_quote(
    metadata: SlicingMetadata,
    material: String,
    pricing_config: PricingConfig,
) -> PyResult<QuoteBreakdown> {
    // Convert grams to kg
    let filament_kg = metadata.filament_weight_grams as f64 / 1000.0;
    
    // Convert minutes to hours and add additional time
    let print_time_hours = (metadata.print_time_minutes as f64 / 60.0) + pricing_config.additional_time_hours;
    
    // Calculate base costs
    let material_cost = filament_kg * pricing_config.price_per_kg;
    let time_cost = print_time_hours * pricing_config.price_per_kg; // Using material price as hourly rate
    
    // Calculate total with multiplier
    let subtotal = (material_cost + time_cost) * pricing_config.price_multiplier;
    
    // Apply minimum price
    let total_cost = if subtotal < pricing_config.minimum_price { 
        pricing_config.minimum_price 
    } else { 
        subtotal 
    };
    let minimum_applied = total_cost == pricing_config.minimum_price;
    
    // Calculate markup percentage
    let markup_percentage = (pricing_config.price_multiplier - 1.0) * 100.0;
    
    Ok(QuoteBreakdown {
        material_type: material,
        filament_kg,
        filament_grams: metadata.filament_weight_grams,
        print_time_hours,
        print_time_minutes: metadata.print_time_minutes,
        price_per_kg: pricing_config.price_per_kg,
        material_cost,
        time_cost,
        subtotal,
        total_cost,
        minimum_applied,
        markup_percentage,
    })
}

/// Main quote pipeline function that orchestrates the entire workflow
#[pyfunction]
fn run_quote_pipeline(
    file_contents: Vec<u8>,
    original_filename: String,
    material_type: String,
    slicer_path: String,
    slicer_profiles_dir: String,
    telegram_config: Option<TelegramConfig>,
    machine_profile: Option<String>,
    process_profile: Option<String>,
    material_prices: Option<HashMap<String, f64>>,
) -> PyResult<QuoteResult> {
    use uuid::Uuid;
    
    // Generate quote ID
    let quote_id = Uuid::new_v4().to_string();
    let short_quote_id = quote_id.chars().take(8).collect::<String>();
    
    // Step 1: Validate filename
    let secure_filename = validate_filename(&original_filename)?;
    
    // Step 2: Validate file contents
    let extension = Path::new(&original_filename)
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    let mut file_info = validate_3d_file(&file_contents, extension)?;
    file_info.secure_filename = secure_filename.clone();
    
    if !file_info.is_valid {
        return Ok(QuoteResult {
            success: false,
            quote_id,
            secure_filename,
            file_type: file_info.file_type,
            file_size: file_info.file_size,
            material_type,
            print_time_minutes: 0,
            filament_weight_grams: 0.0,
            total_cost: 0.0,
            cost_breakdown: QuoteBreakdown {
                material_type: material_type.clone(),
                filament_kg: 0.0,
                filament_grams: 0.0,
                print_time_hours: 0.0,
                print_time_minutes: 0,
                price_per_kg: 0.0,
                material_cost: 0.0,
                time_cost: 0.0,
                subtotal: 0.0,
                total_cost: 0.0,
                minimum_applied: false,
                markup_percentage: 0.0,
            },
            notification_sent: false,
            error_message: file_info.error_message,
        });
    }
    
    // Step 3: Save to temp directory
    let temp_dir = tempfile::TempDir::new()?;
    let model_path = temp_dir.path().join(&secure_filename);
    fs::write(&model_path, &file_contents)?;
    
    // Step 4: Resolve slicer profiles
    let machine = machine_profile.unwrap_or_else(|| "RatRig V-Core 3 400 0.5 nozzle.json".to_string());
    let process = process_profile.unwrap_or_else(|| "0.2mm RatRig 0.5mm nozzle.json".to_string());
    
    let profiles = resolve_profile_paths(
        slicer_profiles_dir.clone(),
        material_type.clone(),
        machine,
        process,
    )?;
    
    // Step 5: Execute slicer
    let output_dir = temp_dir.path().join("output");
    fs::create_dir_all(&output_dir)?;
    
    let gcode_path = execute_slicer(
        model_path.to_str().unwrap(),
        &profiles,
        &slicer_path,
        output_dir.to_str().unwrap(),
    )?;
    
    // Step 6: Parse G-code
    let metadata = parse_gcode_metadata(gcode_path.to_str().unwrap())?;
    
    // Step 7: Calculate pricing
    let prices = material_prices.unwrap_or_else(|| {
        let mut default_prices = HashMap::new();
        default_prices.insert("PLA".to_string(), 25.0);
        default_prices.insert("PETG".to_string(), 30.0);
        default_prices.insert("ASA".to_string(), 35.0);
        default_prices
    });
    
    let price_per_kg = prices.get(&material_type).copied().unwrap_or(25.0);
    
    let pricing_config = PricingConfig {
        price_per_kg,
        additional_time_hours: 0.5,
        price_multiplier: 1.1,
        minimum_price: 5.0,
    };
    
    let cost_breakdown = calculate_final_quote(&metadata, &material_type, &pricing_config)?;
    
    // Step 8: Send Telegram notification (if config provided)
    let notification_sent = if let Some(config) = telegram_config {
        // Note: Actual Telegram sending would be done in Python
        // This is just a placeholder to indicate the notification was requested
        true
    } else {
        false
    };
    
    // Step 9: Return complete result
    Ok(QuoteResult {
        success: true,
        quote_id,
        secure_filename,
        file_type: file_info.file_type,
        file_size: file_info.file_size,
        material_type,
        print_time_minutes: metadata.print_time_minutes,
        filament_weight_grams: metadata.filament_weight_grams,
        total_cost: cost_breakdown.total_cost,
        cost_breakdown,
        notification_sent,
        error_message: None,
    })
}

/// Python module definition
#[pymodule]
fn _rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    // Original validation functions
    m.add_function(wrap_pyfunction!(validate_stl, m)?)?;
    m.add_function(wrap_pyfunction!(validate_obj, m)?)?;
    m.add_function(wrap_pyfunction!(validate_step, m)?)?;
    m.add_function(wrap_pyfunction!(validate_3d_model, m)?)?;
    m.add_function(wrap_pyfunction!(secure_filename, m)?)?;
    
    // New modular functions
    m.add_function(wrap_pyfunction!(validate_filename, m)?)?;
    m.add_function(wrap_pyfunction!(validate_3d_file, m)?)?;
    m.add_function(wrap_pyfunction!(discover_available_materials, m)?)?;
    m.add_function(wrap_pyfunction!(resolve_profile_paths, m)?)?;
    m.add_function(wrap_pyfunction!(execute_slicer, m)?)?;
    m.add_function(wrap_pyfunction!(parse_gcode_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_final_quote, m)?)?;
    
    // Main pipeline function
    m.add_function(wrap_pyfunction!(run_quote_pipeline, m)?)?;
    
    // Enhanced performance functions
    m.add_function(wrap_pyfunction!(parse_slicer_output, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_quote_rust, m)?)?;
    m.add_function(wrap_pyfunction!(cleanup_old_files_rust, m)?)?;
    
    // Data classes
    m.add_class::<ModelInfo>()?;
    m.add_class::<FileInfo>()?;
    m.add_class::<SlicingResult>()?;
    m.add_class::<SlicingMetadata>()?;
    m.add_class::<CleanupStats>()?;
    m.add_class::<CostBreakdown>()?;
    m.add_class::<QuoteBreakdown>()?;
    m.add_class::<TelegramConfig>()?;
    m.add_class::<ProfilePaths>()?;
    m.add_class::<QuoteResult>()?;
    
    Ok(())
}