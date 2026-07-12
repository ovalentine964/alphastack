import { create } from "zustand";

interface SystemInfo {
  os: string;
  arch: string;
  desktop: string;
}

interface AppState {
  appVersion: string | null;
  systemInfo: SystemInfo | null;
  sidebarCollapsed: boolean;

  setAppVersion: (version: string) => void;
  setSystemInfo: (info: SystemInfo) => void;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  appVersion: null,
  systemInfo: null,
  sidebarCollapsed: false,

  setAppVersion: (version) => set({ appVersion: version }),
  setSystemInfo: (info) => set({ systemInfo: info }),
  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
