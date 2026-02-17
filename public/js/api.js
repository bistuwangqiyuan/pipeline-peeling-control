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
                    if (!window.location.pathname.includes('index.html') && window.location.pathname !== '/') {
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
};
