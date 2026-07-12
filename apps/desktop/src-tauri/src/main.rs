// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;

use commands::{notify, toggle_window, get_app_version, get_system_info};
use tauri::{
    CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem,
};

fn build_system_tray() -> SystemTray {
    let show = CustomMenuItem::new("show".to_string(), "Show AlphaStack");
    let hide = CustomMenuItem::new("hide".to_string(), "Hide");
    let dashboard = CustomMenuItem::new("dashboard".to_string(), "Dashboard");
    let portfolio = CustomMenuItem::new("portfolio".to_string(), "Portfolio");
    let settings = CustomMenuItem::new("settings".to_string(), "Settings");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");

    let tray_menu = SystemTrayMenu::new()
        .add_item(show)
        .add_item(hide)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(dashboard)
        .add_item(portfolio)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(settings)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit);

    SystemTray::new().with_menu(tray_menu).with_menu_on_left_click(false)
}

fn main() {
    env_logger::init();

    let tray = build_system_tray();

    tauri::Builder::default()
        .system_tray(tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick {
                position: _,
                size: _,
                ..
            } => {
                let window = app.get_window("main").unwrap();
                let _ = window.show();
                let _ = window.set_focus();
            }
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "show" => {
                    let window = app.get_window("main").unwrap();
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                "hide" => {
                    let window = app.get_window("main").unwrap();
                    let _ = window.hide();
                }
                "dashboard" => {
                    let window = app.get_window("main").unwrap();
                    let _ = window.eval("window.location.hash = '#/dashboard'");
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                "portfolio" => {
                    let window = app.get_window("main").unwrap();
                    let _ = window.eval("window.location.hash = '#/portfolio'");
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                "settings" => {
                    let window = app.get_window("main").unwrap();
                    let _ = window.eval("window.location.hash = '#/settings'");
                    let _ = window.show();
                    let _ = window.set_focus();
                }
                "quit" => {
                    std::process::exit(0);
                }
                _ => {}
            },
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            notify,
            toggle_window,
            get_app_version,
            get_system_info,
        ])
        .setup(|app| {
            log::info!("AlphaStack Desktop starting...");
            log::info!(
                "Version: {}",
                app.config().package.version.as_deref().unwrap_or("dev")
            );
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running AlphaStack Desktop");
}
