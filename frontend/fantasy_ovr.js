(()=>{
// Legacy ESPN Fantasy OVR renderer disabled.
// The active roster presentation and Live Series ratings are handled by
// live_ovr_display.js. Keeping the old MutationObserver, 500ms repaint loop,
// retry timers, and duplicate dashboard/API requests caused unnecessary main-
// thread work and could make the browser report that the page stopped responding.
window.FANTASY_OVR_READY=false;
window.FANTASY_OVR_DISABLED=true;
window.refreshFantasyOVR=async()=>false;
})();
