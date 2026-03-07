use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(
        std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR must be set for build"),
    );
    let resources_root = manifest_dir.join("resources");
    for resource_dir in ["python", "ffmpeg", "jsruntime"] {
        fs::create_dir_all(resources_root.join(resource_dir))
            .unwrap_or_else(|error| panic!("failed to create resources/{resource_dir}: {error}"));
    }

    tauri_build::build()
}
