const Auth = {
    getToken() {
        return localStorage.getItem(CONFIG.TOKEN_KEY);
    },

    getUser() {
        const data = localStorage.getItem(CONFIG.USER_KEY);
        return data ? JSON.parse(data) : null;
    },

    setAuth(token, user) {
        localStorage.setItem(CONFIG.TOKEN_KEY, token);
        localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
    },

    clear() {
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        localStorage.removeItem(CONFIG.USER_KEY);
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    isAdmin() {
        const user = this.getUser();
        return user && user.role === 'admin';
    },

    // 是否具有写权限（管理员或持有授权码 test12 的用户）
    canWrite() {
        const user = this.getUser();
        return !!(user && (user.role === 'admin' || user.has_write_access));
    },

    requireAuth() {
        if (!this.isLoggedIn()) {
            window.location.href = PAGES.LOGIN;
            return false;
        }
        return true;
    },

    requireAdmin() {
        if (!this.isAdmin()) {
            Utils.showToast('需要管理员权限', 'error');
            setTimeout(() => window.location.href = PAGES.DASHBOARD, 1200);
            return false;
        }
        return true;
    },

    // 写操作守卫：游客或无授权用户提示并阻止
    requireWrite() {
        if (!this.canWrite()) {
            Utils.showToast('需要管理员或授权码(test12)权限，请登录', 'warning');
            return false;
        }
        return true;
    },

    logout() {
        this.clear();
        window.location.href = PAGES.HOME;
    },

    async login(username, password) {
        const res = await API.post('/auth/login', { username, password });
        if (res.token) {
            this.setAuth(res.token, res.user);
            try { await this.fetchMe(); } catch (e) {}
        }
        return res;
    },

    async register(data) {
        const res = await API.post('/auth/register', data);
        if (res.token) {
            this.setAuth(res.token, res.user);
        }
        return res;
    },

    async fetchMe() {
        try {
            const res = await API.get('/auth/me');
            if (res.user) {
                localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(res.user));
            }
            return res.user;
        } catch (e) {
            return null;
        }
    }
};
