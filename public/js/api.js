const API = {
    async request(method, endpoint, data = null) {
        const url = CONFIG.API_BASE + endpoint;
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const token = localStorage.getItem(CONFIG.TOKEN_KEY);
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            const result = await response.json();

            if (!response.ok) {
                if (response.status === 401) {
                    Auth.clear();
                    const path = window.location.pathname;
                    const isPublicPage = path === '/' || path === '/index.html'
                        || path.includes('login') || path.includes('register');
                    if (!isPublicPage) {
                        window.location.href = PAGES.LOGIN;
                    }
                }
                throw new Error(result.error || `请求失败 (${response.status})`);
            }

            return result;
        } catch (error) {
            if (error.message.includes('Failed to fetch')) {
                throw new Error('网络连接失败，请检查网络');
            }
            throw error;
        }
    },

    get(endpoint) {
        return this.request('GET', endpoint);
    },

    post(endpoint, data) {
        return this.request('POST', endpoint, data);
    },

    put(endpoint, data) {
        return this.request('PUT', endpoint, data);
    },

    delete(endpoint) {
        return this.request('DELETE', endpoint);
    },

    // 带鉴权头的文件下载（CSV / docx / zip），window.open 无法携带 token 时使用
    async download(endpoint, fallbackName = 'download') {
        const url = CONFIG.API_BASE + endpoint;
        const headers = {};
        const token = localStorage.getItem(CONFIG.TOKEN_KEY);
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const resp = await fetch(url, { headers });
        if (!resp.ok) {
            let msg = `下载失败 (${resp.status})`;
            try { const j = await resp.json(); msg = j.error || msg; } catch (e) {}
            throw new Error(msg);
        }
        const disp = resp.headers.get('Content-Disposition') || '';
        const m = disp.match(/filename=([^;]+)/);
        const name = m ? decodeURIComponent(m[1].trim().replace(/"/g, '')) : fallbackName;
        const blob = await resp.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 4000);
    },
};
