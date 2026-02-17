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
            return false;
        }
        return true;
    },

    logout() {
        this.clear();
        window.location.href = PAGES.LOGIN;
    },

    async login(username, password) {
        const res = await API.post('/auth_login', { username, password });
        if (res.token) {
            this.setAuth(res.token, res.user);
        }
        return res;
    },

    async register(data) {
        const res = await API.post('/auth_register', data);
        if (res.token) {
            this.setAuth(res.token, res.user);
        }
        return res;
    },

    async fetchMe() {
        try {
            const res = await API.get('/auth_me');
            if (res.user) {
                localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(res.user));
            }
            return res.user;
        } catch (e) {
            return null;
        }
    }
};
