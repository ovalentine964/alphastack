use serde::{Deserialize, Serialize};
use tauri::{command, AppHandle, Manager};

#[derive(Debug, Serialize, Deserialize)]
pub struct NotificationPayload {
    pub title: String,
    pub body: String,
    pub icon: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SystemInfo {
    pub os: String,
    pub arch: String,
    pub desktop: String,
}

/// Send a native desktop notification.
#[command]
pub async fn notify(payload: NotificationPayload, app: AppHandle) -> Result<(), String> {
    use tauri::api::notification::Notification;

    let mut builder = Notification::new(&app.config().tauri.bundle.identifier)
        .title(&payload.title)
        .body(&payload.body);

    if let Some(icon) = &payload.icon {
        builder = builder.icon(icon);
    }

    builder.show().map_err(|e| e.to_string())
}

/// Toggle the main window visibility.
#[command]
pub async fn toggle_window(app: AppHandle) -> Result<bool, String> {
    if let Some(window) = app.get_window("main") {
        if window.is_visible().unwrap_or(false) {
            window.hide().map_err(|e| e.to_string())?;
            Ok(false)
        } else {
            window.show().map_err(|e| e.to_string())?;
            window.set_focus().map_err(|e| e.to_string())?;
            Ok(true)
        }
    } else {
        Err("Main window not found".into())
    }
}

/// Return the app version string.
#[command]
pub async fn get_app_version(app: AppHandle) -> Result<String, String> {
    Ok(app
        .config()
        .package
        .version
        .clone()
        .unwrap_or_else(|| "0.0.0-dev".into()))
}

/// Return basic system information.
#[command]
pub async fn get_system_info() -> Result<SystemInfo, String> {
    Ok(SystemInfo {
        os: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        desktop: std::env::var("XDG_CURRENT_DESKTOP")
            .or_else(|_| std::env::var("DESKTOP_SESSION"))
            .unwrap_or_else(|_| "unknown".into()),
    })
}
