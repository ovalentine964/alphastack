import { invoke } from "@tauri-apps/api/tauri";
import { sendNotification } from "@tauri-apps/plugin-notification";
import { Store } from "@tauri-apps/plugin-store";

let store: Store | null = null;

async function getStore(): Promise<Store> {
  if (!store) {
    store = await Store.load("settings.json");
  }
  return store;
}

export const tauriBridge = {
  /**
   * Send a native OS notification.
   */
  async sendNotification(title: string, body: string): Promise<void> {
    try {
      sendNotification({ title, body });
    } catch (err) {
      console.error("Notification failed:", err);
      // Fallback: use Tauri command
      await invoke("notify", {
        payload: { title, body },
      });
    }
  },

  /**
   * Toggle main window visibility.
   */
  async toggleWindow(): Promise<boolean> {
    return invoke<boolean>("toggle_window");
  },

  /**
   * Get the application version.
   */
  async getAppVersion(): Promise<string> {
    return invoke<string>("get_app_version");
  },

  /**
   * Get system info (OS, arch, desktop environment).
   */
  async getSystemInfo(): Promise<{
    os: string;
    arch: string;
    desktop: string;
  }> {
    return invoke("get_system_info");
  },

  /**
   * Persist a setting value.
   */
  async setSetting<T>(key: string, value: T): Promise<void> {
    const s = await getStore();
    await s.set(key, value);
    await s.save();
  },

  /**
   * Read a persisted setting value.
   */
  async getSetting<T>(key: string): Promise<T | null> {
    const s = await getStore();
    return (await s.get<T>(key)) ?? null;
  },

  /**
   * Delete a persisted setting.
   */
  async deleteSetting(key: string): Promise<void> {
    const s = await getStore();
    await s.delete(key);
    await s.save();
  },

  /**
   * Open an external URL in the default browser.
   */
  async openUrl(url: string): Promise<void> {
    const { open } = await import("@tauri-apps/api/shell");
    await open(url);
  },

  /**
   * Minimize the window.
   */
  async minimizeWindow(): Promise<void> {
    const { appWindow } = await import("@tauri-apps/api/window");
    await appWindow.minimize();
  },

  /**
   * Toggle fullscreen.
   */
  async toggleFullscreen(): Promise<void> {
    const { appWindow } = await import("@tauri-apps/api/window");
    const isFullscreen = await appWindow.isFullscreen();
    await appWindow.setFullscreen(!isFullscreen);
  },

  /**
   * Close the window (hides to tray).
   */
  async closeToTray(): Promise<void> {
    const { appWindow } = await import("@tauri-apps/api/window");
    await appWindow.hide();
  },

  // ── Secure storage helpers ───────────────────────────────────

  /**
   * Save API credentials securely.
   */
  async saveCredentials(creds: {
    binanceApiKey?: string;
    binanceApiSecret?: string;
    mimoApiKey?: string;
  }): Promise<void> {
    const s = await getStore();
    if (creds.binanceApiKey !== undefined)
      await s.set("binanceApiKey", creds.binanceApiKey);
    if (creds.binanceApiSecret !== undefined)
      await s.set("binanceApiSecret", creds.binanceApiSecret);
    if (creds.mimoApiKey !== undefined)
      await s.set("mimoApiKey", creds.mimoApiKey);
    await s.save();
  },

  /**
   * Load API credentials.
   */
  async loadCredentials(): Promise<{
    binanceApiKey: string;
    binanceApiSecret: string;
    mimoApiKey: string;
  }> {
    return {
      binanceApiKey:
        (await this.getSetting<string>("binanceApiKey")) ?? "",
      binanceApiSecret:
        (await this.getSetting<string>("binanceApiSecret")) ?? "",
      mimoApiKey:
        (await this.getSetting<string>("mimoApiKey")) ?? "",
    };
  },

  /**
   * Clear all stored credentials.
   */
  async clearCredentials(): Promise<void> {
    await this.deleteSetting("binanceApiKey");
    await this.deleteSetting("binanceApiSecret");
    await this.deleteSetting("mimoApiKey");
    await this.deleteSetting("authToken");
  },
};
