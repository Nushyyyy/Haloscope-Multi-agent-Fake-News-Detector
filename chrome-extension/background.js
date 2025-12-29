// Background service worker for Chrome extension
// Handles long-running tasks and extension lifecycle

chrome.runtime.onInstalled.addListener(() => {
  console.log('Haloscope extension installed');
});

// Optional: Add context menu for right-click analysis
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "analyzeWithHaloscope",
    title: "Analyze with Haloscope",
    contexts: ["page", "link"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "analyzeWithHaloscope") {
    // Open popup or trigger analysis
    chrome.action.openPopup();
  }
});