use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::env;
use std::io::{BufRead, BufReader, Read};
use std::path::{Component, Path, PathBuf};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, Manager, State};
use url::Url;

const ALLOWED_YOUTUBE_HOSTS: [&str; 4] = [
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
];

type SharedDownloadState = Arc<DownloadState>;

struct DownloadState {
    current_process: Mutex<Option<Child>>,
    is_canceled: AtomicBool,
}

impl Default for DownloadState {
    fn default() -> Self {
        Self {
            current_process: Mutex::new(None),
            is_canceled: AtomicBool::new(false),
        }
    }
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct VideoSection {
    pub start: Option<i64>,
    pub end: Option<i64>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoInfo {
    pub id: String,
    pub title: String,
    pub duration: Option<i64>,
    pub is_live: bool,
    pub is_scheduled: bool,
    pub scheduled_start_time: Option<String>,
    pub thumbnail: Option<String>,
    pub uploader: Option<String>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadResult {
    pub success: bool,
    pub file_path: String,
    pub file_size: u64,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CancelResult {
    pub success: bool,
    pub message: Option<String>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LogInfo {
    pub log_path: String,
    pub resources_path: String,
    pub app_path: String,
    pub is_packaged: bool,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadOptions {
    pub url: String,
    pub save_path: String,
    #[serde(default)]
    pub start_time: Option<i64>,
    #[serde(default)]
    pub end_time: Option<i64>,
    #[serde(default)]
    pub sections: Option<Vec<VideoSection>>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessLocalOptions {
    pub input_path: String,
    pub save_path: String,
    #[serde(default)]
    pub sections: Option<Vec<VideoSection>>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedDownloadRequest {
    pub url: String,
    pub save_path: PathBuf,
    pub sections: Vec<VideoSection>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedLocalProcessRequest {
    pub input_path: PathBuf,
    pub save_path: PathBuf,
    pub sections: Vec<VideoSection>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct DownloadProgressData {
    percent: Option<f64>,
    downloaded_bytes: Option<u64>,
    total_bytes: Option<u64>,
    speed: Option<String>,
    eta: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PythonExtractResponse {
    success: bool,
    video_info: Option<VideoInfo>,
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PythonDownloadResponse {
    success: bool,
    file_path: Option<String>,
    file_size: Option<u64>,
    error_message: Option<String>,
}

struct ProcessOutput {
    status: ExitStatus,
    stdout: String,
    stderr: String,
}

#[tauri::command]
async fn extract_video_info(app: AppHandle, url: String) -> Result<VideoInfo, String> {
    tauri::async_runtime::spawn_blocking(move || run_extract_video_info(app, url))
        .await
        .map_err(|error| format!("Failed to run video info extraction task: {error}"))?
}

#[tauri::command]
async fn download_video(
    app: AppHandle,
    state: State<'_, SharedDownloadState>,
    options: DownloadOptions,
) -> Result<DownloadResult, String> {
    let shared_state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || run_download_video(app, shared_state, options))
        .await
        .map_err(|error| format!("Failed to run download task: {error}"))?
}

#[tauri::command]
async fn process_local_video(
    app: AppHandle,
    state: State<'_, SharedDownloadState>,
    options: ProcessLocalOptions,
) -> Result<DownloadResult, String> {
    let shared_state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        run_process_local_video(app, shared_state, options)
    })
    .await
    .map_err(|error| format!("Failed to run local processing task: {error}"))?
}

#[tauri::command]
fn cancel_download(state: State<'_, SharedDownloadState>) -> CancelResult {
    let state = state.inner().clone();
    let mut process_guard = match state.current_process.lock() {
        Ok(guard) => guard,
        Err(_) => {
            return CancelResult {
                success: false,
                message: Some("Failed to access active process state".into()),
            };
        }
    };

    if let Some(child) = process_guard.as_mut() {
        state.is_canceled.store(true, Ordering::SeqCst);
        let _ = child.kill();
        return CancelResult {
            success: true,
            message: None,
        };
    }

    CancelResult {
        success: false,
        message: Some("No active download".into()),
    }
}

#[tauri::command]
fn get_log_info(app: AppHandle) -> Result<LogInfo, String> {
    let log_dir = app
        .path()
        .app_log_dir()
        .map_err(|error| format!("Failed to resolve app log directory: {error}"))?;
    let resources_path = app
        .path()
        .resource_dir()
        .map(|path| path.to_string_lossy().to_string())
        .unwrap_or_default();
    let app_path = env::current_exe()
        .map_err(|error| format!("Failed to resolve executable path: {error}"))?;

    Ok(LogInfo {
        log_path: log_dir.join("main.log").to_string_lossy().to_string(),
        resources_path,
        app_path: app_path.to_string_lossy().to_string(),
        is_packaged: !is_dev_mode(),
    })
}

fn run_extract_video_info(app: AppHandle, url: String) -> Result<VideoInfo, String> {
    let validated_url = validate_youtube_url(&url).map_err(|e| format!("Invalid input: {e}"))?;
    let python_path = get_python_path(&app)?;
    let script_path = get_python_script_path(&app)?;
    validate_python_path_for_mode(&python_path)?;

    let args = vec![
        script_path.to_string_lossy().to_string(),
        "--validate".to_string(),
        validated_url.clone(),
    ];

    let python_dir = get_python_working_dir(&python_path);
    let child = spawn_python_process(
        "Failed to start download process",
        &python_path,
        &args,
        python_dir.as_deref(),
        &[],
    )?;
    let output = run_untracked_process(child)?;
    if !output.status.success() {
        return Err(format!(
            "Python process failed: {}",
            if output.stderr.trim().is_empty() {
                format!("Process exited with code {}", output.status)
            } else {
                output.stderr.trim().to_string()
            }
        ));
    }

    let value = parse_json_payload(&output.stdout)
        .map_err(|error| format!("Failed to parse video info: {error}"))?;
    let response: PythonExtractResponse = serde_json::from_value(value)
        .map_err(|error| format!("Failed to parse video info response: {error}"))?;
    if response.success {
        if let Some(video_info) = response.video_info {
            return Ok(video_info);
        }
        return Err("Failed to extract video info".into());
    }

    Err(response
        .error
        .unwrap_or_else(|| "Failed to extract video info".into()))
}

fn run_download_video(
    app: AppHandle,
    state: SharedDownloadState,
    options: DownloadOptions,
) -> Result<DownloadResult, String> {
    let validated = validate_download_input(&options).map_err(|e| format!("Invalid input: {e}"))?;
    reset_and_kill_existing_process(&state)?;

    let python_path = get_python_path(&app)?;
    let script_path = get_python_script_path(&app)?;
    let ffmpeg_path = get_ffmpeg_path(&app)?;
    validate_python_path_for_mode(&python_path)?;

    let sections_json = serde_json::to_string(&validated.sections)
        .map_err(|error| format!("Failed to serialize sections: {error}"))?;

    let args = vec![
        script_path.to_string_lossy().to_string(),
        validated.url,
        "false".to_string(),
        "bestvideo*+bestaudio".to_string(),
        sections_json,
        validated.save_path.to_string_lossy().to_string(),
    ];

    let python_dir = get_python_working_dir(&python_path);
    let env_overrides = vec![("FFMPEG_PATH", ffmpeg_path.to_string_lossy().to_string())];
    let child = spawn_python_process(
        "Failed to start download process",
        &python_path,
        &args,
        python_dir.as_deref(),
        &env_overrides,
    )?;

    let output = run_tracked_process(app, state.clone(), child, true)?;
    if state.is_canceled.load(Ordering::SeqCst) {
        return Err("Download canceled by user".into());
    }

    if !output.status.success() {
        let stderr = output.stderr.trim();
        let message = if stderr.is_empty() {
            format!("Process exited with code {}", output.status)
        } else {
            stderr.to_string()
        };
        return Err(format!("Download process failed: {message}"));
    }

    parse_download_result(&output.stdout, "Download failed")
}

fn run_process_local_video(
    app: AppHandle,
    state: SharedDownloadState,
    options: ProcessLocalOptions,
) -> Result<DownloadResult, String> {
    let validated =
        validate_local_process_input(&options).map_err(|e| format!("Invalid input: {e}"))?;
    reset_and_kill_existing_process(&state)?;

    let python_path = get_python_path(&app)?;
    let script_path = get_python_script_path(&app)?;
    let ffmpeg_path = get_ffmpeg_path(&app)?;
    validate_python_path_for_mode(&python_path)?;

    let sections_json = serde_json::to_string(&validated.sections)
        .map_err(|error| format!("Failed to serialize sections: {error}"))?;
    let args = vec![
        script_path.to_string_lossy().to_string(),
        "--local".to_string(),
        validated.input_path.to_string_lossy().to_string(),
        sections_json,
        validated.save_path.to_string_lossy().to_string(),
    ];

    let python_dir = get_python_working_dir(&python_path);
    let env_overrides = vec![("FFMPEG_PATH", ffmpeg_path.to_string_lossy().to_string())];
    let child = spawn_python_process(
        "Failed to start processing",
        &python_path,
        &args,
        python_dir.as_deref(),
        &env_overrides,
    )?;

    let output = run_tracked_process(app, state.clone(), child, false)?;
    if state.is_canceled.load(Ordering::SeqCst) {
        return Err("Processing canceled by user".into());
    }

    if !output.status.success() {
        let stderr = output.stderr.trim();
        let message = if stderr.is_empty() {
            format!("Process exited with code {}", output.status)
        } else {
            stderr.to_string()
        };
        return Err(format!("Processing failed: {message}"));
    }

    parse_download_result(&output.stdout, "Processing failed")
}

fn run_untracked_process(mut child: Child) -> Result<ProcessOutput, String> {
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Failed to capture process stdout".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Failed to capture process stderr".to_string())?;

    let stdout_thread = thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut output = String::new();
        let _ = reader.read_to_string(&mut output);
        output
    });
    let stderr_thread = thread::spawn(move || {
        let mut reader = BufReader::new(stderr);
        let mut output = String::new();
        let _ = reader.read_to_string(&mut output);
        output
    });

    let status = child
        .wait()
        .map_err(|error| format!("Failed waiting for python process: {error}"))?;
    let stdout = stdout_thread
        .join()
        .map_err(|_| "Failed joining stdout reader thread".to_string())?;
    let stderr = stderr_thread
        .join()
        .map_err(|_| "Failed joining stderr reader thread".to_string())?;

    Ok(ProcessOutput {
        status,
        stdout,
        stderr,
    })
}

fn run_tracked_process(
    app: AppHandle,
    state: SharedDownloadState,
    mut child: Child,
    emit_progress: bool,
) -> Result<ProcessOutput, String> {
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "Failed to capture process stdout".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Failed to capture process stderr".to_string())?;

    {
        let mut guard = state
            .current_process
            .lock()
            .map_err(|_| "Failed to acquire process lock".to_string())?;
        *guard = Some(child);
    }

    let stdout_thread = thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut output = String::new();
        let _ = reader.read_to_string(&mut output);
        output
    });

    let app_for_stderr = app.clone();
    let stderr_thread = thread::spawn(move || {
        let reader = BufReader::new(stderr);
        let mut output = String::new();
        for line in reader.lines() {
            let line = match line {
                Ok(line) => line,
                Err(_) => continue,
            };
            output.push_str(&line);
            output.push('\n');
            if emit_progress {
                if let Some(progress) = parse_progress_line(&line) {
                    let _ = app_for_stderr.emit("download-progress", progress);
                }
                if is_quality_debug_line(&line) {
                    eprintln!("{line}");
                }
            }
        }
        output
    });

    let status = {
        let mut guard = state
            .current_process
            .lock()
            .map_err(|_| "Failed to acquire process lock".to_string())?;
        let process = guard
            .as_mut()
            .ok_or_else(|| "Process state lost before completion".to_string())?;
        process
            .wait()
            .map_err(|error| format!("Failed waiting for python process: {error}"))?
    };

    {
        let mut guard = state
            .current_process
            .lock()
            .map_err(|_| "Failed to acquire process lock".to_string())?;
        *guard = None;
    }

    let stdout = stdout_thread
        .join()
        .map_err(|_| "Failed joining stdout reader thread".to_string())?;
    let stderr = stderr_thread
        .join()
        .map_err(|_| "Failed joining stderr reader thread".to_string())?;

    Ok(ProcessOutput {
        status,
        stdout,
        stderr,
    })
}

fn parse_progress_line(line: &str) -> Option<DownloadProgressData> {
    let value: Value = serde_json::from_str(line.trim()).ok()?;
    if value.get("type")?.as_str()? != "progress" {
        return None;
    }

    let downloaded_bytes = value.get("downloaded_bytes").and_then(|v| v.as_u64());
    let total_bytes = value.get("total_bytes").and_then(|v| v.as_u64());
    let percent = value.get("percent").and_then(|v| v.as_f64()).or_else(|| {
        match (downloaded_bytes, total_bytes) {
            (Some(downloaded), Some(total)) if total > 0 => {
                Some((downloaded as f64 / total as f64) * 100.0)
            }
            _ => None,
        }
    });

    Some(DownloadProgressData {
        percent,
        downloaded_bytes,
        total_bytes,
        speed: value
            .get("speed")
            .and_then(|v| v.as_str())
            .map(ToOwned::to_owned),
        eta: value
            .get("eta")
            .and_then(|v| v.as_str())
            .map(ToOwned::to_owned),
    })
}

fn is_quality_debug_line(line: &str) -> bool {
    let value: Value = match serde_json::from_str(line.trim()) {
        Ok(value) => value,
        Err(_) => return false,
    };
    matches!(
        value.get("type").and_then(|value| value.as_str()),
        Some("quality_debug")
    )
}

fn parse_download_result(stdout: &str, default_error: &str) -> Result<DownloadResult, String> {
    let value = parse_json_payload(stdout)
        .map_err(|error| format!("Failed to parse download result: {error}"))?;
    let response: PythonDownloadResponse = serde_json::from_value(value)
        .map_err(|error| format!("Failed to parse download response: {error}"))?;

    if !response.success {
        return Err(response
            .error_message
            .unwrap_or_else(|| default_error.to_string()));
    }

    let file_path = response
        .file_path
        .ok_or_else(|| "Missing file_path in download response".to_string())?;

    Ok(DownloadResult {
        success: true,
        file_path,
        file_size: response.file_size.unwrap_or(0),
    })
}

fn parse_json_payload(stdout: &str) -> Result<Value, String> {
    let trimmed = stdout.trim();
    if trimmed.is_empty() {
        return Err("Python process returned empty output".into());
    }

    if trimmed.starts_with('{') {
        return serde_json::from_str::<Value>(trimmed)
            .map_err(|error| format!("Invalid JSON payload: {error}"));
    }

    for (index, _) in trimmed.match_indices('{').rev() {
        if let Ok(value) = serde_json::from_str::<Value>(&trimmed[index..]) {
            return Ok(value);
        }
    }

    Err("No JSON payload found in process output".into())
}

fn reset_and_kill_existing_process(state: &SharedDownloadState) -> Result<(), String> {
    state.is_canceled.store(false, Ordering::SeqCst);
    let mut guard = state
        .current_process
        .lock()
        .map_err(|_| "Failed to acquire process lock".to_string())?;
    if let Some(child) = guard.as_mut() {
        let _ = child.kill();
        let _ = child.wait();
    }
    *guard = None;
    Ok(())
}

fn spawn_python_process(
    context: &str,
    python_path: &Path,
    args: &[String],
    cwd: Option<&Path>,
    env_overrides: &[(&str, String)],
) -> Result<Child, String> {
    let mut command = Command::new(python_path);
    command.args(args);
    command.stdin(Stdio::null());
    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    for (key, value) in env_overrides {
        command.env(key, value);
    }

    command
        .spawn()
        .map_err(|error| map_spawn_error(context, python_path, &error))
}

fn map_spawn_error(context: &str, python_path: &Path, error: &std::io::Error) -> String {
    match error.kind() {
        std::io::ErrorKind::NotFound => {
            format!(
        "Python executable not found at: {}. Please ensure the application is properly installed.",
        python_path.to_string_lossy()
      )
        }
        std::io::ErrorKind::PermissionDenied => {
            format!(
        "Permission denied when trying to run Python at: {}. Please check file permissions.",
        python_path.to_string_lossy()
      )
        }
        _ => format!("{context}: {error}"),
    }
}

fn get_python_working_dir(python_path: &Path) -> Option<PathBuf> {
    if !is_dev_mode() && cfg!(target_os = "windows") {
        return python_path.parent().map(ToOwned::to_owned);
    }
    None
}

fn get_python_path(app: &AppHandle) -> Result<PathBuf, String> {
    if is_dev_mode() {
        resolve_dev_python_path().ok_or_else(|| {
            "Configuration error: Python executable not found. Install python3 or set YT_DOWNLOADER_PYTHON.".into()
        })
    } else {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|error| format!("Failed to resolve resources path: {error}"))?;
        if cfg!(target_os = "windows") {
            Ok(resource_dir.join("python").join("python.exe"))
        } else {
            Ok(resource_dir.join("python").join("bin").join("python3"))
        }
    }
}

fn validate_python_path_for_mode(python_path: &Path) -> Result<(), String> {
    if !is_dev_mode() && !python_path.exists() {
        return Err(format!(
            "Configuration error: Python executable not found at: {}",
            python_path.to_string_lossy()
        ));
    }
    Ok(())
}

fn get_python_script_path(app: &AppHandle) -> Result<PathBuf, String> {
    let path = if is_dev_mode() {
        resolve_dev_python_script_path(&project_root())
    } else {
        app.path()
            .resource_dir()
            .map_err(|error| format!("Failed to resolve resources path: {error}"))?
            .join("python")
            .join("downloader.py")
    };

    if !path.exists() {
        return Err(format!(
            "Configuration error: Python script not found at: {}",
            path.to_string_lossy()
        ));
    }
    Ok(path)
}

fn get_ffmpeg_path(app: &AppHandle) -> Result<PathBuf, String> {
    if is_dev_mode() {
        return resolve_dev_ffmpeg_path().ok_or_else(|| {
            "Configuration error: FFmpeg not found in dev mode. Install ffmpeg, set FFMPEG_PATH, or bundle it at src-tauri/resources/ffmpeg/".to_string()
        });
    }

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| format!("Failed to resolve resources path: {error}"))?;

    let path = if cfg!(target_os = "windows") {
        resource_dir.join("ffmpeg").join("ffmpeg.exe")
    } else {
        resource_dir.join("ffmpeg").join("ffmpeg")
    };

    if !path.exists() {
        return Err(format!(
            "Configuration error: FFmpeg not found at: {}",
            path.to_string_lossy()
        ));
    }
    Ok(path)
}

fn project_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap_or(Path::new(env!("CARGO_MANIFEST_DIR")))
        .to_path_buf()
}

fn resolve_dev_python_script_path(repo_root: &Path) -> PathBuf {
    repo_root.join("python").join("downloader.py")
}

fn resolve_dev_python_path() -> Option<PathBuf> {
    if let Some(path) = env::var_os("YT_DOWNLOADER_PYTHON") {
        let path = PathBuf::from(path);
        if path.exists() || path.components().count() == 1 {
            return Some(path);
        }
    }

    let bundled_python = if cfg!(target_os = "windows") {
        project_root()
            .join("src-tauri")
            .join("resources")
            .join("python")
            .join("python.exe")
    } else {
        project_root()
            .join("src-tauri")
            .join("resources")
            .join("python")
            .join("bin")
            .join("python3")
    };
    if bundled_python.exists() {
        return Some(bundled_python);
    }

    let candidates: &[&str] = if cfg!(target_os = "windows") {
        &["python", "py"]
    } else {
        &["python3", "python"]
    };

    for candidate in candidates {
        if command_available(candidate) {
            return Some(PathBuf::from(candidate));
        }
    }

    None
}

fn resolve_dev_ffmpeg_path() -> Option<PathBuf> {
    if let Some(path) = env::var_os("FFMPEG_PATH") {
        let path = PathBuf::from(path);
        if path.exists() || (path.components().count() == 1 && command_available(&path.to_string_lossy())) {
            return Some(path);
        }
    }

    let bundled_ffmpeg = if cfg!(target_os = "windows") {
        project_root()
            .join("src-tauri")
            .join("resources")
            .join("ffmpeg")
            .join("ffmpeg.exe")
    } else {
        project_root()
            .join("src-tauri")
            .join("resources")
            .join("ffmpeg")
            .join("ffmpeg")
    };
    if bundled_ffmpeg.exists() {
        return Some(bundled_ffmpeg);
    }

    if command_available("ffmpeg") {
        return Some(PathBuf::from("ffmpeg"));
    }

    None
}

fn command_available(command: &str) -> bool {
    Command::new(command)
        .arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok()
}

fn is_dev_mode() -> bool {
    env::var("TAURI_ENV")
        .map(|value| value.eq_ignore_ascii_case("dev"))
        .unwrap_or(cfg!(debug_assertions))
}

pub fn validate_download_input(
    options: &DownloadOptions,
) -> Result<ValidatedDownloadRequest, String> {
    let validated_url = validate_youtube_url(&options.url)?;
    let validated_save_path = validate_save_path(&options.save_path)?;
    let validated_sections = if let Some(sections) = &options.sections {
        if sections.is_empty() {
            validate_legacy_start_end(options.start_time, options.end_time)?;
            vec![VideoSection {
                start: options.start_time,
                end: options.end_time,
            }]
        } else {
            validate_sections(sections)?
        }
    } else {
        validate_legacy_start_end(options.start_time, options.end_time)?;
        vec![VideoSection {
            start: options.start_time,
            end: options.end_time,
        }]
    };

    Ok(ValidatedDownloadRequest {
        url: validated_url,
        save_path: validated_save_path,
        sections: validated_sections,
    })
}

pub fn validate_local_process_input(
    options: &ProcessLocalOptions,
) -> Result<ValidatedLocalProcessRequest, String> {
    if options.input_path.trim().is_empty() || options.save_path.trim().is_empty() {
        return Err("Input path and save path are required".into());
    }

    let validated_save_path = validate_save_path(&options.save_path)?;
    let validated_sections = if let Some(sections) = &options.sections {
        if sections.is_empty() {
            vec![]
        } else {
            validate_sections(sections)?
        }
    } else {
        vec![]
    };

    Ok(ValidatedLocalProcessRequest {
        input_path: PathBuf::from(options.input_path.trim()),
        save_path: validated_save_path,
        sections: validated_sections,
    })
}

pub fn validate_youtube_url(input: &str) -> Result<String, String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return Err("URL must be a non-empty string".into());
    }

    let parsed = Url::parse(trimmed).map_err(|_| "Invalid URL format".to_string())?;
    let host = parsed
        .host_str()
        .ok_or_else(|| "Invalid URL format".to_string())?;
    let normalized_host = host.trim_start_matches("www.");

    let is_allowed = ALLOWED_YOUTUBE_HOSTS
        .iter()
        .any(|allowed| normalized_host.eq_ignore_ascii_case(allowed));

    if !is_allowed {
        return Err("URL must be a valid YouTube URL".into());
    }

    Ok(trimmed.to_string())
}

pub fn validate_save_path(save_path: &str) -> Result<PathBuf, String> {
    let home_dir = resolve_home_dir()?;
    validate_save_path_for_home(save_path, &home_dir)
}

fn resolve_home_dir() -> Result<PathBuf, String> {
    if let Some(home) = env::var_os("HOME") {
        return Ok(PathBuf::from(home));
    }
    if let Some(home) = env::var_os("USERPROFILE") {
        return Ok(PathBuf::from(home));
    }
    Err("Could not resolve user home directory".into())
}

fn validate_save_path_for_home(save_path: &str, home_dir: &Path) -> Result<PathBuf, String> {
    let trimmed = save_path.trim();
    if trimmed.is_empty() {
        return Err("Save path must be a non-empty string".into());
    }

    let raw_path = Path::new(trimmed);
    if raw_path
        .components()
        .any(|component| matches!(component, Component::ParentDir))
    {
        return Err("Invalid save path".into());
    }

    let resolved = if raw_path.is_absolute() {
        raw_path.to_path_buf()
    } else {
        env::current_dir()
            .map_err(|_| "Unable to resolve current directory".to_string())?
            .join(raw_path)
    };

    if !resolved.starts_with(home_dir) {
        return Err("Save path must be within user home directory".into());
    }

    Ok(resolved)
}

fn validate_legacy_start_end(start_time: Option<i64>, end_time: Option<i64>) -> Result<(), String> {
    validate_non_negative("Start time", start_time, None)?;
    validate_non_negative("End time", end_time, None)?;

    if let (Some(start), Some(end)) = (start_time, end_time) {
        if start >= end {
            return Err("End time must be greater than start time".into());
        }
    }
    Ok(())
}

fn validate_sections(sections: &[VideoSection]) -> Result<Vec<VideoSection>, String> {
    for (index, section) in sections.iter().enumerate() {
        let section_number = index + 1;

        if index > 0 && section.start.is_none() {
            return Err(format!(
                "Start time of section {} cannot be empty",
                section_number
            ));
        }

        if index < sections.len() - 1 && section.end.is_none() {
            return Err(format!(
                "End time of section {} cannot be empty (it has a next section)",
                section_number
            ));
        }

        validate_non_negative("Start time", section.start, Some(section_number))?;
        validate_non_negative("End time", section.end, Some(section_number))?;

        if let (Some(start), Some(end)) = (section.start, section.end) {
            if start >= end {
                return Err(format!(
                    "End time must be greater than start time in section {}",
                    section_number
                ));
            }
        }

        if index < sections.len() - 1 {
            let next_start = sections[index + 1].start;
            if let (Some(end), Some(next_start)) = (section.end, next_start) {
                if next_start < end {
                    return Err(format!(
            "Start time of section {} ({}s) cannot be before end time of section {} ({}s)",
            section_number + 1,
            next_start,
            section_number,
            end
          ));
                }
            }
        }
    }

    Ok(sections.to_vec())
}

fn validate_non_negative(
    field_name: &str,
    value: Option<i64>,
    section_number: Option<usize>,
) -> Result<(), String> {
    if let Some(value) = value {
        if value < 0 {
            if let Some(section_number) = section_number {
                return Err(format!(
                    "{} of section {} must be a non-negative integer",
                    field_name, section_number
                ));
            }
            return Err(format!("{} must be a non-negative integer", field_name));
        }
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Arc::new(DownloadState::default()))
        .plugin(tauri_plugin_dialog::init())
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .targets([
                    tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
                    tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir {
                        file_name: Some("main".into()),
                    }),
                ])
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            extract_video_info,
            download_video,
            process_local_video,
            cancel_download,
            get_log_info
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_youtube_urls() {
        let valid = validate_youtube_url("https://www.youtube.com/watch?v=abc123");
        assert!(valid.is_ok());
        assert_eq!(
            valid.expect("expected valid URL"),
            "https://www.youtube.com/watch?v=abc123"
        );
    }

    #[test]
    fn rejects_non_youtube_urls() {
        let err = validate_youtube_url("https://example.com/watch?v=abc123");
        assert_eq!(
            err.expect_err("expected invalid host"),
            "URL must be a valid YouTube URL"
        );
    }

    #[test]
    fn rejects_save_path_outside_home() {
        let home = test_home_dir();
        let outside = test_outside_home_path();
        let err = validate_save_path_for_home(&outside, &home);
        assert_eq!(
            err.expect_err("expected outside-home rejection"),
            "Save path must be within user home directory"
        );
    }

    #[test]
    fn accepts_save_path_inside_home() {
        let home = test_home_dir();
        let inside = home.join("Downloads").join("video.mp4");
        let result = validate_save_path_for_home(&inside.to_string_lossy(), &home);
        assert!(result.is_ok());
    }

    #[test]
    fn rejects_sections_with_missing_start_after_first() {
        let sections = vec![
            VideoSection {
                start: Some(0),
                end: Some(10),
            },
            VideoSection {
                start: None,
                end: Some(20),
            },
        ];
        let err = validate_sections(&sections);
        assert_eq!(
            err.expect_err("expected missing start to fail"),
            "Start time of section 2 cannot be empty"
        );
    }

    #[test]
    fn rejects_overlapping_sections() {
        let sections = vec![
            VideoSection {
                start: Some(0),
                end: Some(20),
            },
            VideoSection {
                start: Some(19),
                end: Some(30),
            },
        ];
        let err = validate_sections(&sections);
        assert_eq!(
            err.expect_err("expected overlap to fail"),
            "Start time of section 2 (19s) cannot be before end time of section 1 (20s)"
        );
    }

    #[test]
    fn rejects_legacy_invalid_range() {
        let err = validate_legacy_start_end(Some(30), Some(30));
        assert_eq!(
            err.expect_err("expected range validation to fail"),
            "End time must be greater than start time"
        );
    }

    #[test]
    fn validates_download_input_with_sections() {
        let home = resolve_home_dir().expect("home dir should resolve");
        let options = DownloadOptions {
            url: "https://youtu.be/abc123".into(),
            save_path: home
                .join("Downloads/video.mp4")
                .to_string_lossy()
                .to_string(),
            start_time: None,
            end_time: None,
            sections: Some(vec![
                VideoSection {
                    start: Some(0),
                    end: Some(10),
                },
                VideoSection {
                    start: Some(20),
                    end: None,
                },
            ]),
        };

        let validated = validate_download_input(&options).expect("expected valid download options");
        assert_eq!(validated.sections.len(), 2);
    }

    #[test]
    fn rejects_empty_local_input_path() {
        let home = resolve_home_dir().expect("home dir should resolve");
        let options = ProcessLocalOptions {
            input_path: "   ".into(),
            save_path: home
                .join("Downloads/video.mp4")
                .to_string_lossy()
                .to_string(),
            sections: None,
        };

        let err = validate_local_process_input(&options);
        assert_eq!(
            err.expect_err("expected local input validation to fail"),
            "Input path and save path are required"
        );
    }

    #[test]
    fn resolves_dev_python_script_path_from_repo_root() {
        let repo_root = project_root();
        let path = resolve_dev_python_script_path(&repo_root);
        assert!(path.ends_with(Path::new("python").join("downloader.py")));
        assert!(path.exists(), "expected script path to exist: {path:?}");
    }

    #[test]
    fn parses_json_payload_with_non_json_prefix() {
        let payload =
            "INFO: preparing download\n{\"success\":true,\"file_path\":\"/tmp/a.mp4\",\"file_size\":1}\n";
        let parsed = parse_json_payload(payload).expect("expected parser to find trailing JSON");
        assert_eq!(
            parsed.get("success").and_then(|value| value.as_bool()),
            Some(true)
        );
    }

    #[test]
    fn parses_progress_line_payload() {
        let line = r#"{"type":"progress","percent":42.5,"downloaded_bytes":10,"total_bytes":20,"speed":"1MiB/s","eta":"00:10"}"#;
        let parsed = parse_progress_line(line).expect("expected progress payload");
        assert_eq!(parsed.percent, Some(42.5));
        assert_eq!(parsed.downloaded_bytes, Some(10));
        assert_eq!(parsed.total_bytes, Some(20));
    }

    #[test]
    fn parses_progress_line_without_percent_uses_bytes() {
        let line = r#"{"type":"progress","percent":null,"downloaded_bytes":25,"total_bytes":100}"#;
        let parsed = parse_progress_line(line).expect("expected progress payload");
        assert_eq!(parsed.percent, Some(25.0));
        assert_eq!(parsed.downloaded_bytes, Some(25));
        assert_eq!(parsed.total_bytes, Some(100));
    }

    #[test]
    fn maps_spawn_not_found_error_to_helpful_message() {
        let err = std::io::Error::new(std::io::ErrorKind::NotFound, "missing");
        let message = map_spawn_error(
            "Failed to start download process",
            Path::new("python3"),
            &err,
        );
        assert!(message.contains("Python executable not found"));
    }

    fn test_home_dir() -> PathBuf {
        #[cfg(target_os = "windows")]
        {
            PathBuf::from(r"C:\Users\tester")
        }
        #[cfg(not(target_os = "windows"))]
        {
            PathBuf::from("/Users/tester")
        }
    }

    fn test_outside_home_path() -> String {
        #[cfg(target_os = "windows")]
        {
            String::from(r"D:\video.mp4")
        }
        #[cfg(not(target_os = "windows"))]
        {
            String::from("/tmp/video.mp4")
        }
    }
}
