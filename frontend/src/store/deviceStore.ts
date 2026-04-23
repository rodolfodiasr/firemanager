import { create } from "zustand";
import type { Device } from "../types/device";
import { devicesApi } from "../api/devices";

interface DeviceState {
  devices: Device[];
  selectedDeviceId: string | null;
  loading: boolean;
  fetchDevices: () => Promise<void>;
  selectDevice: (id: string | null) => void;
}

export const useDeviceStore = create<DeviceState>((set) => ({
  devices: [],
  selectedDeviceId: null,
  loading: false,

  fetchDevices: async () => {
    set({ loading: true });
    try {
      const devices = await devicesApi.list();
      set({ devices });
    } finally {
      set({ loading: false });
    }
  },

  selectDevice: (id) => set({ selectedDeviceId: id }),
}));
