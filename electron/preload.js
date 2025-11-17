const { contextBridge, ipcRenderer } = require("electron");

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld("electronAPI", {
  extractVideoInfo: (url) => ipcRenderer.invoke("extract-video-info", url),
  showSaveDialog: (options) => ipcRenderer.invoke("show-save-dialog", options),
  downloadVideo: (options) => ipcRenderer.invoke("download-video", options),
  cancelDownload: () => ipcRenderer.invoke("cancel-download"),
  onDownloadProgress: (callback) => {
    ipcRenderer.on("download-progress", (event, data) => callback(data));
  },
  removeDownloadProgressListener: () => {
    ipcRenderer.removeAllListeners("download-progress");
  },
});
