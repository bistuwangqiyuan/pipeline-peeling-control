const Utils = {
    formatDate(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        return d.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },

    formatDateShort(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        return d.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatNumber(n, decimals = 2) {
        if (n == null || isNaN(n)) return '-';
        return Number(n).toFixed(decimals);
    },

    formatForce(n) {
        if (n == null || isNaN(n)) return '-';
        return Number(n).toFixed(1) + ' N';
    },

    showToast(message, type = 'info') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
        toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;

        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(50px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    statusBadge(status) {
        const label = STATUS_LABELS[status] || status;
        return `<span class="badge badge-${status}">${label}</span>`;
    },

    roleBadge(role) {
        const label = ROLE_LABELS[role] || role;
        return `<span class="badge badge-${role}">${label}</span>`;
    },

    confirm(message) {
        return window.confirm(message);
    },

    debounce(fn, delay = 300) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    },

    getQueryParam(name) {
        const params = new URLSearchParams(window.location.search);
        return params.get(name);
    },

    setQueryParam(name, value) {
        const url = new URL(window.location);
        url.searchParams.set(name, value);
        window.history.replaceState({}, '', url);
    },

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    },

    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    },

    initDB() {
        return API.request('GET', '/init_db');
    }
};
