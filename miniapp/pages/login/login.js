const supabase = require("../../utils/supabase");

Page({
  data: {
    email: "",
    password: "",
    loading: false
  },

  onLoad() {
    if (supabase.getSession()?.access_token) {
      wx.redirectTo({ url: "/pages/home/home" });
    }
  },

  onEmailInput(event) {
    this.setData({ email: event.detail.value.trim() });
  },

  onPasswordInput(event) {
    this.setData({ password: event.detail.value });
  },

  async login() {
    if (!this.data.email || !this.data.password) {
      wx.showToast({ title: "请输入邮箱和密码", icon: "none" });
      return;
    }
    this.setData({ loading: true });
    try {
      const session = await supabase.signInWithPassword(this.data.email, this.data.password);
      getApp().setSession(session);
      wx.redirectTo({ url: "/pages/home/home" });
    } catch (error) {
      wx.showModal({ title: "登录失败", content: error.message, showCancel: false });
    } finally {
      this.setData({ loading: false });
    }
  }
});
