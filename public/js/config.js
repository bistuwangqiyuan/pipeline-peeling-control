const CONFIG = {
    API_BASE: '/api',
    POLLING_INTERVAL: 200,        // 实时刷新 200ms（论文 3.2.2 / 5.4）
    STRIP_COUNT: 30,              // 大屏最多展示 30 条带
    PIPE_DIAMETER: 1016,          // 管道直径 mm
    LAYER_WIDTH: 600,             // 防腐层宽度 mm
    LAYER_THICKNESS: 1.0,         // 防腐层厚度 mm
    STRIP_WIDTH: 20,              // 每条带宽度 mm
    PEEL_SPEED: 10,               // 标准剥离速度 mm/min
    FORCE_SENSOR_RANGE: 1000,     // S 型传感器量程 N
    GOOD_BOND_PLATFORM: 96,       // 良好粘接平台力值 N
    PASS_THRESHOLD: 70,           // 合格剥离力阈值 N
    FORCE_ALARM_HIGH: 120,        // 剥离力上限报警 N
    FORCE_ALARM_LOW: 5,           // 剥离力下限报警 N
    TOKEN_KEY: 'peeling_token',
    USER_KEY: 'peeling_user',
};

const PAGES = {
    HOME: '/index.html',
    LOGIN: '/login.html',
    REGISTER: '/register.html',
    DASHBOARD: '/dashboard.html',
    CONTROL: '/control.html',
    PROJECTS: '/projects.html',
    ANALYSIS: '/analysis.html',
    REPORTS: '/reports.html',
    USERS: '/users.html',
    SETTINGS: '/settings.html',
    METROLOGY: '/metrology.html',
};

const STATUS_LABELS = {
    created: '已创建',
    pending: '待执行',
    running: '运行中',
    completed: '已完成',
    aborted: '已中止',
    in_progress: '进行中',
};

const ROLE_LABELS = {
    admin: '管理员',
    user: '普通用户',
    guest: '游客',
};
