const supabase = require("./utils/supabase");

App({
  globalData: {
    session: null
  },

  onLaunch() {
    this.globalData.session = supabase.getSession();
  },

  setSession(session) {
    this.globalData.session = session;
    supabase.saveSession(session);
  },

  clearSession() {
    this.globalData.session = null;
    supabase.clearSession();
  }
});
