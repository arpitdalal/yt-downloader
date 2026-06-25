use log::{info, warn};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::env;
use std::io::{BufRead, BufReader, Read};
use std::path::{Component, Path, PathBuf};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager, State};
use url::Url;

const ALLOWED_YOUTUBE_HOSTS: [&str; 4] = [
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
];

const SUPPORTED_COOKIE_BROWSERS: [&str; 10] = [
    "arc", "brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale",
];

type SharedDownloadState = Arc<DownloadState>;
const COOKIE_SOURCE_CACHE_TTL: Duration = Duration::from_secs(30);
const MAX_COOKIE_SOURCE_ATTEMPTS: usize = 6;

struct DownloadState {
    current_process: Mutex<Option<Child>>,
    is_canceled: AtomicBool,
    cookie_sources_cache: Mutex<Option<CookieSourceCache>>,
}

#[derive(Debug, Clone)]
struct CookieSourceCache {
    catalog: CookieSourceCatalog,
    fetched_at: Instant,
}

impl Default for DownloadState {
    fn default() -> Self {
        Self {
            current_process: Mutex::new(None),
            is_canceled: AtomicBool::new(false),
            cookie_sources_cache: Mutex::new(None),
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
    pub view_count: Option<i64>,
    pub upload_date: Option<String>,
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
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct YouTubeAuthStatus {
    /// True if a supported browser is configured for cookie access.
    pub connected: bool,
    /// First detected/supported browser name (e.g. "chrome").
    pub detected_browser: Option<String>,
    /// True if bundled/system JS runtime for yt-dlp fetch_pot is available.
    pub js_runtime_available: bool,
    /// JS runtime name used for fetch_pot (e.g. "deno", "node").
    pub js_runtime_name: Option<String>,
    /// Whether fetch_pot integration is enabled.
    pub fetch_pot_enabled: bool,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CookieSource {
    pub id: String,
    pub browser: String,
    pub browser_label: String,
    #[serde(default)]
    pub profile: Option<String>,
    #[serde(default)]
    pub profile_label: Option<String>,
    #[serde(default)]
    pub container: Option<String>,
    #[serde(default)]
    pub keyring: Option<String>,
    pub available: bool,
    pub has_youtube_cookies: bool,
    pub has_youtube_auth_cookies: bool,
    #[serde(default)]
    pub last_error: Option<String>,
    pub priority: i64,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CookieSourceCatalog {
    pub sources: Vec<CookieSource>,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CookieSelection {
    pub mode: String,
    #[serde(default)]
    pub source_id: Option<String>,
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
    #[serde(default)]
    pub cookie_selection: Option<CookieSelection>,
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
struct PythonCookieSourcesResponse {
    success: bool,
    sources: Option<Vec<CookieSource>>,
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
async fn extract_video_info(
    app: AppHandle,
    state: State<'_, SharedDownloadState>,
    url: String,
    cookie_selection: Option<CookieSelection>,
) -> Result<VideoInfo, String> {
    let shared_state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        run_extract_video_info(app, shared_state, url, cookie_selection)
    })
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

#[tauri::command]
fn get_youtube_auth_status(app: AppHandle) -> Result<YouTubeAuthStatus, String> {
    Ok(detected_browser_auth_status(get_js_runtime_path(&app)))
}

#[tauri::command]
fn list_youtube_cookie_sources(
    app: AppHandle,
    state: State<'_, SharedDownloadState>,
    force_refresh: Option<bool>,
) -> Result<CookieSourceCatalog, String> {
    let shared_state = state.inner().clone();
    load_cookie_source_catalog(&app, &shared_state, force_refresh.unwrap_or(false))
}

fn run_extract_video_info(
    app: AppHandle,
    state: SharedDownloadState,
    url: String,
    cookie_selection: Option<CookieSelection>,
) -> Result<VideoInfo, String> {
    let validated_url = validate_youtube_url(&url).map_err(|e| format!("Invalid input: {e}"))?;
    let python_path = get_python_path(&app)?;
    let script_path = get_python_script_path(&app)?;
    validate_python_path_for_mode(&python_path)?;

    let args = vec![
        script_path.to_string_lossy().to_string(),
        "--validate".to_string(),
        validated_url.clone(),
    ];

    let selected_cookie_sources = if browser_cookies_env_enabled() {
        resolve_cookie_sources_for_selection(&app, &state, cookie_selection.as_ref())?
    } else {
        None
    };
    let python_dir = get_python_working_dir(&python_path);
    let env_overrides = yt_dlp_env_overrides(
        &app,
        None,
        cookie_selection.as_ref(),
        selected_cookie_sources.as_deref(),
    )?;
    info!("Extract video info started: url={}", validated_url);
    let child = spawn_python_process(
        "Failed to start download process",
        &python_path,
        &args,
        python_dir.as_deref(),
        &env_overrides,
    )?;
    let output = run_untracked_process(child)?;
    if !output.status.success() {
        let stderr = output.stderr.trim();
        let message = if stderr.is_empty() {
            format!("Process exited with code {}", output.status)
        } else {
            stderr.to_string()
        };
        warn!("Extract video info failed: {message}");
        if is_youtube_auth_verification_error(&message) {
            warn!(
                "Extract video info auth error (YouTube bot check) for url={}",
                validated_url
            );
            return Err(format!("YOUTUBE_AUTH: {message}"));
        }
        return Err(format!("Python process failed: {message}"));
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
    let validated_url = validated.url.clone();

    let args = vec![
        script_path.to_string_lossy().to_string(),
        validated_url.clone(),
        "false".to_string(),
        "bestvideo*+bestaudio".to_string(),
        sections_json,
        validated.save_path.to_string_lossy().to_string(),
    ];

    let selected_cookie_sources = if browser_cookies_env_enabled() {
        resolve_cookie_sources_for_selection(&app, &state, options.cookie_selection.as_ref())?
    } else {
        None
    };
    let python_dir = get_python_working_dir(&python_path);
    let env_overrides = download_env_overrides(
        &app,
        &ffmpeg_path,
        options.cookie_selection.as_ref(),
        selected_cookie_sources.as_deref(),
    )?;
    info!(
        "Download started: url={} save_path={} sections={}",
        validated_url,
        validated.save_path.to_string_lossy(),
        validated.sections.len()
    );
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
        warn!("Download failed: {message}");
        if is_youtube_auth_verification_error(&message) {
            warn!("Download auth error (YouTube bot check).");
            return Err(format!("YOUTUBE_AUTH: {message}"));
        }
        return Err(format!("Download process failed: {message}"));
    }

    parse_download_result(&output.stdout, "Download failed")
}

fn load_cookie_source_catalog(
    app: &AppHandle,
    state: &SharedDownloadState,
    force_refresh: bool,
) -> Result<CookieSourceCatalog, String> {
    if !force_refresh {
        if let Ok(guard) = state.cookie_sources_cache.lock() {
            if let Some(cache) = guard.as_ref() {
                if cache.fetched_at.elapsed() < COOKIE_SOURCE_CACHE_TTL {
                    return Ok(cache.catalog.clone());
                }
            }
        }
    }

    let catalog = fetch_cookie_source_catalog_from_python(app)?;
    let mut guard = state
        .cookie_sources_cache
        .lock()
        .map_err(|_| "Failed to acquire cookie source cache lock".to_string())?;
    *guard = Some(CookieSourceCache {
        catalog: catalog.clone(),
        fetched_at: Instant::now(),
    });
    Ok(catalog)
}

fn fetch_cookie_source_catalog_from_python(app: &AppHandle) -> Result<CookieSourceCatalog, String> {
    let python_path = get_python_path(app)?;
    let script_path = get_python_script_path(app)?;
    validate_python_path_for_mode(&python_path)?;

    let args = vec![
        script_path.to_string_lossy().to_string(),
        "--list-cookie-sources".to_string(),
    ];
    let python_dir = get_python_working_dir(&python_path);
    let child = spawn_python_process(
        "Failed to inspect cookie sources",
        &python_path,
        &args,
        python_dir.as_deref(),
        &[],
    )?;
    let output = run_untracked_process(child)?;
    if !output.status.success() {
        let structured_error = parse_json_payload(&output.stdout)
            .ok()
            .and_then(|value| serde_json::from_value::<PythonCookieSourcesResponse>(value).ok())
            .filter(|response| !response.success)
            .and_then(|response| response.error);
        let stderr = output.stderr.trim();
        let message = structured_error.unwrap_or_else(|| {
            if stderr.is_empty() {
                format!("Process exited with code {}", output.status)
            } else {
                stderr.to_string()
            }
        });
        return Err(format!("Failed to list cookie sources: {message}"));
    }

    let value = parse_json_payload(&output.stdout)
        .map_err(|error| format!("Failed to parse cookie source response: {error}"))?;
    let response: PythonCookieSourcesResponse = serde_json::from_value(value)
        .map_err(|error| format!("Failed to decode cookie source response: {error}"))?;
    if !response.success {
        return Err(response
            .error
            .unwrap_or_else(|| "Failed to list cookie sources".to_string()));
    }
    Ok(CookieSourceCatalog {
        sources: response.sources.unwrap_or_default(),
    })
}

fn resolve_cookie_sources_for_selection(
    app: &AppHandle,
    state: &SharedDownloadState,
    selection: Option<&CookieSelection>,
) -> Result<Option<Vec<CookieSource>>, String> {
    let Some(selection) = selection else {
        return Ok(None);
    };

    let mode = parse_cookie_selection_mode(&selection.mode)?;
    let mut sources = match load_cookie_source_catalog(app, state, false) {
        Ok(catalog) => catalog.sources,
        Err(error) => {
            if mode == "manual" {
                return Err(error);
            }
            warn!(
                "Cookie source auto selection failed, continuing without explicit sources: {error}"
            );
            return Ok(None);
        }
    };
    sources.sort_by_key(|source| source.priority);

    if mode == "manual" {
        let source_id = selection
            .source_id
            .as_ref()
            .map(|id| id.trim())
            .filter(|id| !id.is_empty())
            .ok_or_else(|| "Manual cookie selection requires sourceId".to_string())?;
        let source = sources
            .into_iter()
            .find(|candidate| candidate.id == source_id)
            .ok_or_else(|| format!("Selected cookie source not found: {source_id}"))?;
        if !source.available {
            let reason = source.last_error.as_deref().unwrap_or("unknown reason");
            return Err(format!(
                "Selected cookie source is unavailable: {} ({reason})",
                source.browser_label
            ));
        }
        return Ok(Some(vec![source]));
    }

    let auto_sources: Vec<CookieSource> = sources
        .into_iter()
        .filter(|source| source.available)
        .take(MAX_COOKIE_SOURCE_ATTEMPTS)
        .collect();
    Ok(Some(auto_sources))
}

fn parse_cookie_selection_mode(mode: &str) -> Result<&'static str, String> {
    if mode.eq_ignore_ascii_case("manual") {
        return Ok("manual");
    }
    if mode.eq_ignore_ascii_case("auto") {
        return Ok("auto");
    }
    Err(format!("Unsupported cookie selection mode: {mode}"))
}

fn default_cookie_browser_list() -> &'static str {
    if cfg!(target_os = "macos") {
        "arc,chrome,safari,firefox,edge,brave,chromium,opera,vivaldi"
    } else if cfg!(target_os = "windows") {
        "edge,chrome,firefox,brave,chromium,opera,vivaldi,whale"
    } else {
        "chrome,firefox,chromium,edge,brave,opera,vivaldi"
    }
}

fn push_cookie_selection_env_overrides(
    env_overrides: &mut Vec<(&'static str, String)>,
    selection: &CookieSelection,
    selected_cookie_sources: Option<&[CookieSource]>,
) -> Result<(), String> {
    let mode = parse_cookie_selection_mode(&selection.mode)?;
    let enable_browser_cookies =
        env::var("YT_DLP_ENABLE_BROWSER_COOKIES").unwrap_or_else(|_| "true".to_string());
    let cookies_enabled = env_truthy_from_value(&enable_browser_cookies, true);
    env_overrides.push(("YT_DLP_ENABLE_BROWSER_COOKIES", enable_browser_cookies));
    env_overrides.push(("YT_DLP_COOKIE_SELECTION_MODE", mode.to_string()));
    if cookies_enabled {
        if let Some(explicit_sources) =
            selected_cookie_sources.filter(|sources| !sources.is_empty())
        {
            let explicit_sources_json =
                serde_json::to_string(explicit_sources).unwrap_or_else(|_| "[]".to_string());
            env_overrides.push(("YT_DLP_COOKIE_SOURCES_JSON", explicit_sources_json));
        }
    }
    Ok(())
}

fn yt_dlp_env_overrides(
    app: &AppHandle,
    ffmpeg_path: Option<&Path>,
    cookie_selection: Option<&CookieSelection>,
    selected_cookie_sources: Option<&[CookieSource]>,
) -> Result<Vec<(&'static str, String)>, String> {
    let mut env_overrides = Vec::new();
    if let Some(path) = ffmpeg_path {
        env_overrides.push(("FFMPEG_PATH", path.to_string_lossy().to_string()));
    }

    if let Some(selection) = cookie_selection {
        push_cookie_selection_env_overrides(
            &mut env_overrides,
            selection,
            selected_cookie_sources,
        )?;
    } else {
        let enable_browser_cookies =
            env::var("YT_DLP_ENABLE_BROWSER_COOKIES").unwrap_or_else(|_| "true".to_string());
        env_overrides.push(("YT_DLP_ENABLE_BROWSER_COOKIES", enable_browser_cookies));
        let cookies_browser = env::var("YT_DLP_COOKIES_BROWSER")
            .unwrap_or_else(|_| default_cookie_browser_list().to_string());
        env_overrides.push(("YT_DLP_COOKIES_BROWSER", cookies_browser));
    }

    let enable_fetch_pot =
        env::var("YT_DLP_ENABLE_FETCH_POT").unwrap_or_else(|_| "true".to_string());
    env_overrides.push(("YT_DLP_ENABLE_FETCH_POT", enable_fetch_pot));

    let disable_post_compat_normalization = env::var("YT_DLP_DISABLE_POST_COMPAT_NORMALIZATION")
        .unwrap_or_else(|_| "false".to_string());
    env_overrides.push((
        "YT_DLP_DISABLE_POST_COMPAT_NORMALIZATION",
        disable_post_compat_normalization,
    ));

    if let Some((runtime_path, runtime_name)) = get_js_runtime_path(app) {
        env_overrides.push((
            "YT_DLP_JS_RUNTIME_PATH",
            runtime_path.to_string_lossy().to_string(),
        ));
        env_overrides.push(("YT_DLP_JS_RUNTIME_NAME", runtime_name));
    }
    Ok(env_overrides)
}

fn download_env_overrides(
    app: &AppHandle,
    ffmpeg_path: &Path,
    cookie_selection: Option<&CookieSelection>,
    selected_cookie_sources: Option<&[CookieSource]>,
) -> Result<Vec<(&'static str, String)>, String> {
    yt_dlp_env_overrides(
        app,
        Some(ffmpeg_path),
        cookie_selection,
        selected_cookie_sources,
    )
}

/// Returns auth/runtime status based on configured browser list and runtime discovery.
fn cookie_browser_candidates() -> Vec<String> {
    let raw = env::var("YT_DLP_COOKIES_BROWSER").unwrap_or_default();
    let requested: Vec<String> = raw
        .split(|c: char| c == ',' || c.is_ascii_whitespace())
        .filter_map(|token| {
            let trimmed = token.trim().to_ascii_lowercase();
            if trimmed.is_empty() {
                None
            } else {
                Some(trimmed)
            }
        })
        .collect();

    let mut candidates: Vec<String> = if requested.is_empty() {
        default_cookie_browser_list()
            .split(',')
            .map(|token| token.trim().to_ascii_lowercase())
            .filter(|token| !token.is_empty())
            .collect()
    } else {
        requested
    };

    for candidate in &mut candidates {
        if candidate == "google-chrome" {
            *candidate = "chrome".to_string();
        } else if candidate == "msedge" {
            *candidate = "edge".to_string();
        }
    }

    let mut unique: Vec<String> = Vec::new();
    for candidate in candidates {
        if !SUPPORTED_COOKIE_BROWSERS.contains(&candidate.as_str()) {
            continue;
        }
        if !unique.iter().any(|value| value == &candidate) {
            unique.push(candidate);
        }
    }
    unique
}

fn user_home_dir() -> Option<PathBuf> {
    env::var_os("HOME")
        .map(PathBuf::from)
        .or_else(|| env::var_os("USERPROFILE").map(PathBuf::from))
}

#[cfg(target_os = "macos")]
fn arc_cookie_store_exists(user_data_dir: &Path) -> bool {
    if user_data_dir.join("Default").join("Cookies").is_file() {
        return true;
    }

    let entries = match std::fs::read_dir(user_data_dir) {
        Ok(entries) => entries,
        Err(_) => return false,
    };

    for entry in entries.flatten() {
        let file_type = match entry.file_type() {
            Ok(file_type) => file_type,
            Err(_) => continue,
        };
        if !file_type.is_dir() {
            continue;
        }

        let profile_name = entry.file_name();
        let profile_name = profile_name.to_string_lossy();
        if !profile_name.starts_with("Profile") {
            continue;
        }

        if entry.path().join("Cookies").is_file() {
            return true;
        }
    }

    false
}

#[cfg(target_os = "macos")]
fn browser_cookie_store_exists(browser: &str) -> bool {
    let home = match user_home_dir() {
        Some(home) => home,
        None => return false,
    };

    match browser {
        "arc" => arc_cookie_store_exists(&home.join("Library/Application Support/Arc/User Data")),
        "chrome" => home
            .join("Library/Application Support/Google/Chrome")
            .exists(),
        "safari" => home
            .join("Library/Safari/Cookies/Cookies.binarycookies")
            .exists()
            || home
                .join("Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies")
                .exists(),
        "firefox" => home
            .join("Library/Application Support/Firefox/Profiles")
            .exists(),
        "edge" => home
            .join("Library/Application Support/Microsoft Edge")
            .exists(),
        "brave" => home
            .join("Library/Application Support/BraveSoftware/Brave-Browser")
            .exists(),
        "chromium" => home
            .join("Library/Application Support/Chromium")
            .exists(),
        "opera" => home
            .join("Library/Application Support/com.operasoftware.Opera")
            .exists(),
        "vivaldi" => home
            .join("Library/Application Support/Vivaldi")
            .exists(),
        _ => false,
    }
}

#[cfg(target_os = "windows")]
fn browser_cookie_store_exists(browser: &str) -> bool {
    let local_app_data = env::var_os("LOCALAPPDATA").map(PathBuf::from);
    let roaming_app_data = env::var_os("APPDATA").map(PathBuf::from);

    match browser {
        "edge" => local_app_data
            .as_ref()
            .map(|root| root.join("Microsoft/Edge/User Data").exists())
            .unwrap_or(false),
        "chrome" => local_app_data
            .as_ref()
            .map(|root| root.join("Google/Chrome/User Data").exists())
            .unwrap_or(false),
        "firefox" => roaming_app_data
            .as_ref()
            .map(|root| root.join("Mozilla/Firefox/Profiles").exists())
            .unwrap_or(false),
        "brave" => local_app_data
            .as_ref()
            .map(|root| root.join("BraveSoftware/Brave-Browser/User Data").exists())
            .unwrap_or(false),
        "chromium" => local_app_data
            .as_ref()
            .map(|root| root.join("Chromium/User Data").exists())
            .unwrap_or(false),
        "opera" => roaming_app_data
            .as_ref()
            .map(|root| root.join("Opera Software/Opera Stable").exists())
            .unwrap_or(false),
        "vivaldi" => local_app_data
            .as_ref()
            .map(|root| root.join("Vivaldi/User Data").exists())
            .unwrap_or(false),
        "whale" => local_app_data
            .as_ref()
            .map(|root| root.join("Naver/Naver Whale/User Data").exists())
            .unwrap_or(false),
        _ => false,
    }
}

#[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
fn browser_cookie_store_exists(browser: &str) -> bool {
    let home = match user_home_dir() {
        Some(home) => home,
        None => return false,
    };

    match browser {
        "chrome" => home.join(".config/google-chrome").exists(),
        "firefox" => home.join(".mozilla/firefox").exists(),
        "chromium" => home.join(".config/chromium").exists(),
        "edge" => home.join(".config/microsoft-edge").exists(),
        "brave" => home.join(".config/BraveSoftware/Brave-Browser").exists(),
        "opera" => home.join(".config/opera").exists(),
        "vivaldi" => home.join(".config/vivaldi").exists(),
        _ => false,
    }
}

fn detect_available_cookie_browser() -> Option<String> {
    cookie_browser_candidates()
        .into_iter()
        .find(|browser| browser_cookie_store_exists(browser))
}

fn detected_browser_auth_status(js_runtime: Option<(PathBuf, String)>) -> YouTubeAuthStatus {
    let browser_cookies_enabled = env_truthy("YT_DLP_ENABLE_BROWSER_COOKIES", true);
    let detected_browser = detect_available_cookie_browser();
    let fetch_pot_enabled = env_truthy("YT_DLP_ENABLE_FETCH_POT", true);
    YouTubeAuthStatus {
        connected: browser_cookies_enabled && detected_browser.is_some(),
        detected_browser,
        js_runtime_available: js_runtime.is_some(),
        js_runtime_name: js_runtime.map(|(_, name)| name),
        fetch_pot_enabled,
    }
}

fn is_youtube_auth_verification_error(message: &str) -> bool {
    let lowered = message.to_lowercase();
    lowered.contains("sign in to confirm you’re not a bot")
        || lowered.contains("sign in to confirm you're not a bot")
        || lowered.contains("use --cookies-from-browser or --cookies for the authentication")
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
    let mut env_overrides = vec![("FFMPEG_PATH", ffmpeg_path.to_string_lossy().to_string())];
    let disable_post_compat_normalization = env::var("YT_DLP_DISABLE_POST_COMPAT_NORMALIZATION")
        .unwrap_or_else(|_| "false".to_string());
    env_overrides.push((
        "YT_DLP_DISABLE_POST_COMPAT_NORMALIZATION",
        disable_post_compat_normalization,
    ));
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
            }
            if is_quality_debug_line(&line) || is_auth_debug_line(&line) {
                info!("{line}");
            } else if line.starts_with("ERROR:") {
                warn!("python stderr: {line}");
            }
        }
        output
    });

    let status = loop {
        let maybe_status = {
            let mut guard = state
                .current_process
                .lock()
                .map_err(|_| "Failed to acquire process lock".to_string())?;
            let process = guard
                .as_mut()
                .ok_or_else(|| "Process state lost before completion".to_string())?;
            process
                .try_wait()
                .map_err(|error| format!("Failed waiting for python process: {error}"))?
        };

        if let Some(status) = maybe_status {
            break status;
        }
        thread::sleep(std::time::Duration::from_millis(150));
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

fn is_auth_debug_line(line: &str) -> bool {
    let value: Value = match serde_json::from_str(line.trim()) {
        Ok(value) => value,
        Err(_) => return false,
    };
    matches!(
        value.get("type").and_then(|value| value.as_str()),
        Some("auth_debug")
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
    if !python_executable_works(python_path) {
        return Err(format!(
            "Configuration error: Python executable is not runnable at: {}. \
The bundled runtime likely does not match this OS/architecture.",
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

fn env_truthy_from_value(value: &str, _default: bool) -> bool {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return false;
    }
    matches!(
        trimmed.to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on"
    )
}

fn browser_cookies_env_enabled() -> bool {
    env_truthy("YT_DLP_ENABLE_BROWSER_COOKIES", true)
}

fn env_truthy(var_name: &str, default: bool) -> bool {
    match env::var(var_name) {
        Ok(value) => env_truthy_from_value(&value, default),
        Err(_) => default,
    }
}

fn normalize_runtime_name(raw: &str) -> Option<String> {
    let lowered = raw.trim().to_ascii_lowercase();
    match lowered.as_str() {
        "deno" => Some("deno".into()),
        "node" | "nodejs" => Some("node".into()),
        _ => None,
    }
}

fn infer_runtime_name_from_path(path: &Path) -> Option<String> {
    let file_name = path
        .file_name()
        .map(|value| value.to_string_lossy().to_ascii_lowercase())
        .unwrap_or_else(|| path.to_string_lossy().to_ascii_lowercase());
    if file_name.contains("deno") {
        return Some("deno".into());
    }
    if file_name.contains("node") {
        return Some("node".into());
    }
    None
}

fn runtime_from_env_override() -> Option<(PathBuf, String)> {
    let runtime_path = env::var_os("YT_DLP_JS_RUNTIME_PATH")?;
    let path = PathBuf::from(runtime_path);
    let path_str = path.to_string_lossy().to_string();
    let valid_path =
        path.exists() || (path.components().count() == 1 && command_available(&path_str));
    if !valid_path {
        return None;
    }

    let runtime_name = env::var("YT_DLP_JS_RUNTIME_NAME")
        .ok()
        .and_then(|value| normalize_runtime_name(&value))
        .or_else(|| infer_runtime_name_from_path(&path))?;
    Some((path, runtime_name))
}

fn packaged_js_runtime_path(app: &AppHandle) -> Option<(PathBuf, String)> {
    let resource_dir = app.path().resource_dir().ok()?;
    let (name, path) = if cfg!(target_os = "macos") {
        (
            "deno".to_string(),
            resource_dir.join("jsruntime").join("deno"),
        )
    } else if cfg!(target_os = "windows") {
        (
            "node".to_string(),
            resource_dir.join("jsruntime").join("node.exe"),
        )
    } else {
        (
            "node".to_string(),
            resource_dir.join("jsruntime").join("node"),
        )
    };
    if command_available(&path.to_string_lossy()) {
        return Some((path, name));
    }
    None
}

fn resolve_dev_js_runtime_path() -> Option<(PathBuf, String)> {
    if let Some(runtime) = runtime_from_env_override() {
        return Some(runtime);
    }

    let bundled_runtime = if cfg!(target_os = "macos") {
        (
            project_root()
                .join("src-tauri")
                .join("resources")
                .join("jsruntime")
                .join("deno"),
            "deno".to_string(),
        )
    } else if cfg!(target_os = "windows") {
        (
            project_root()
                .join("src-tauri")
                .join("resources")
                .join("jsruntime")
                .join("node.exe"),
            "node".to_string(),
        )
    } else {
        (
            project_root()
                .join("src-tauri")
                .join("resources")
                .join("jsruntime")
                .join("node"),
            "node".to_string(),
        )
    };

    if bundled_runtime.0.exists() && command_available(&bundled_runtime.0.to_string_lossy()) {
        return Some((bundled_runtime.0, bundled_runtime.1));
    }

    let runtime_candidates: &[(&str, &str)] = if cfg!(target_os = "macos") {
        &[("deno", "deno"), ("node", "node")]
    } else {
        &[("node", "node"), ("deno", "deno")]
    };
    for (name, candidate) in runtime_candidates {
        if command_available(candidate) {
            return Some((PathBuf::from(candidate), (*name).to_string()));
        }
    }

    None
}

fn get_js_runtime_path(app: &AppHandle) -> Option<(PathBuf, String)> {
    if let Some(runtime) = runtime_from_env_override() {
        return Some(runtime);
    }

    if is_dev_mode() {
        return resolve_dev_js_runtime_path();
    }

    packaged_js_runtime_path(app)
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

    // Keep dev runtime aligned with packaged runtime when resources are present.
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
    if bundled_python.exists() && python_executable_works(&bundled_python) {
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
        if path.exists()
            || (path.components().count() == 1 && command_available(&path.to_string_lossy()))
        {
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

fn python_executable_works(path: &Path) -> bool {
    Command::new(path)
        .arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
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

    let input_path = PathBuf::from(options.input_path.trim());
    if !input_path.exists() || !input_path.is_file() {
        return Err("Input file not found".into());
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
        input_path,
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
            get_log_info,
            get_youtube_auth_status,
            list_youtube_cookie_sources
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;

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
            cookie_selection: None,
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
    fn rejects_missing_local_input_file() {
        let home = resolve_home_dir().expect("home dir should resolve");
        let missing = env::temp_dir().join(format!(
            "yt-downloader-missing-input-{}-{}.mp4",
            std::process::id(),
            std::thread::current().name().unwrap_or("test")
        ));
        if missing.exists() {
            let _ = std::fs::remove_file(&missing);
        }
        let options = ProcessLocalOptions {
            input_path: missing.to_string_lossy().to_string(),
            save_path: home
                .join("Downloads/video.mp4")
                .to_string_lossy()
                .to_string(),
            sections: None,
        };

        let err = validate_local_process_input(&options);
        assert_eq!(
            err.expect_err("expected local input validation to fail"),
            "Input file not found"
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
    fn parses_python_extract_response_with_video_metadata_fields() {
        let payload = serde_json::json!({
            "success": true,
            "video_info": {
                "id": "abc123",
                "title": "Video",
                "duration": 120,
                "is_live": false,
                "is_scheduled": false,
                "scheduled_start_time": null,
                "thumbnail": null,
                "uploader": "Uploader",
                "view_count": 42,
                "upload_date": "20260101"
            },
            "error": null
        });

        let parsed: PythonExtractResponse =
            serde_json::from_value(payload).expect("response should deserialize");
        let info = parsed.video_info.expect("video info should exist");
        assert_eq!(info.view_count, Some(42));
        assert_eq!(info.upload_date.as_deref(), Some("20260101"));
    }

    #[test]
    fn video_info_defaults_optional_metadata_when_missing() {
        let payload = serde_json::json!({
            "id": "abc123",
            "title": "Video",
            "duration": null,
            "is_live": false,
            "is_scheduled": false,
            "scheduled_start_time": null,
            "thumbnail": null,
            "uploader": null
        });

        let parsed: VideoInfo =
            serde_json::from_value(payload).expect("video info should deserialize");
        assert_eq!(parsed.view_count, None);
        assert_eq!(parsed.upload_date, None);
    }

    #[test]
    fn recognizes_auth_debug_lines() {
        assert!(is_auth_debug_line(
            r#"{"type":"auth_debug","event":"extract_attempt"}"#
        ));
        assert!(!is_auth_debug_line(
            r#"{"type":"quality_debug","event":"x"}"#
        ));
    }

    #[test]
    fn recognizes_youtube_auth_verification_errors() {
        assert!(is_youtube_auth_verification_error(
            "Sign in to confirm you're not a bot"
        ));
        assert!(is_youtube_auth_verification_error(
            "Use --cookies-from-browser or --cookies for the authentication"
        ));
        assert!(!is_youtube_auth_verification_error("network timeout"));
    }

    #[test]
    fn detected_browser_auth_status_returns_runtime_status() {
        let status = detected_browser_auth_status(Some((PathBuf::from("node"), "node".into())));
        assert!(status.js_runtime_available);
        assert_eq!(status.js_runtime_name.as_deref(), Some("node"));
        assert_eq!(
            status.fetch_pot_enabled,
            env_truthy("YT_DLP_ENABLE_FETCH_POT", true)
        );
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn arc_cookie_store_exists_requires_cookie_db_file() {
        let root = env::temp_dir().join(format!(
            "yt-downloader-arc-cookie-test-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("Profile 1")).expect("failed to create profile dir");
        assert!(!arc_cookie_store_exists(&root));

        std::fs::create_dir_all(root.join("Default")).expect("failed to create default dir");
        std::fs::File::create(root.join("Default").join("Cookies"))
            .expect("failed to create cookies db");
        assert!(arc_cookie_store_exists(&root));
        std::fs::remove_file(root.join("Default").join("Cookies"))
            .expect("failed to remove default cookies db");
        std::fs::File::create(root.join("Profile 1").join("Cookies"))
            .expect("failed to create profile cookies db");
        assert!(arc_cookie_store_exists(&root));

        let _ = std::fs::remove_dir_all(&root);
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

    #[test]
    fn env_truthy_from_value_handles_common_false_values() {
        assert!(!super::env_truthy_from_value("false", true));
        assert!(!super::env_truthy_from_value("0", true));
        assert!(!super::env_truthy_from_value("off", true));
        assert!(super::env_truthy_from_value("true", false));
        assert!(!super::env_truthy_from_value("", true));
    }

    #[test]
    #[serial]
    fn cookie_selection_env_skips_sources_when_cookies_disabled() {
        let previous = env::var("YT_DLP_ENABLE_BROWSER_COOKIES").ok();
        unsafe {
            env::set_var("YT_DLP_ENABLE_BROWSER_COOKIES", "false");
        }

        let selection = CookieSelection {
            mode: "auto".to_string(),
            source_id: None,
        };
        let sources = [CookieSource {
            id: "chrome_default".to_string(),
            browser: "chrome".to_string(),
            browser_label: "Chrome".to_string(),
            profile: None,
            profile_label: None,
            container: None,
            keyring: None,
            available: true,
            has_youtube_cookies: true,
            has_youtube_auth_cookies: true,
            last_error: None,
            priority: 0,
        }];
        let mut env_overrides = Vec::new();
        super::push_cookie_selection_env_overrides(&mut env_overrides, &selection, Some(&sources))
            .expect("cookie env overrides");

        assert!(env_overrides
            .iter()
            .any(|(key, value)| *key == "YT_DLP_ENABLE_BROWSER_COOKIES" && value == "false"));
        assert!(!env_overrides
            .iter()
            .any(|(key, _)| *key == "YT_DLP_COOKIE_SOURCES_JSON"));

        match previous {
            Some(value) => unsafe {
                env::set_var("YT_DLP_ENABLE_BROWSER_COOKIES", value);
            },
            None => unsafe {
                env::remove_var("YT_DLP_ENABLE_BROWSER_COOKIES");
            },
        }
    }
}
