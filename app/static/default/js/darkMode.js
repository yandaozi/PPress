// 检查系统主题偏好
const systemPrefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

// 从 cookie 获取用户主题设置
function getThemePreference() {
    const darkMode = document.cookie.split('; ').find(row => row.startsWith('darkMode='));
    if (darkMode) {
        return darkMode.split('=')[1] === 'true';
    }
    return systemPrefersDark; // 如果没有 cookie，使用系统偏好
}

// 设置主题
function setTheme(isDark) {
    //console.log('Setting theme:', isDark ? 'dark' : 'light');
    const html = document.documentElement;
    
    if (isDark) {
        html.classList.add('dark');
        document.body.classList.add('dark');
    } else {
        html.classList.remove('dark');
        document.body.classList.remove('dark');
    }
    
    // 强制重新应用样式
    document.body.style.backgroundColor = '';
    document.body.offsetHeight;
    
    // 保存设置到 cookie
    document.cookie = `darkMode=${isDark}; max-age=31536000; path=/`;
    
    // 更新图标
    const darkIcon = document.getElementById('theme-toggle-dark-icon');
    const lightIcon = document.getElementById('theme-toggle-light-icon');
    
    if (!darkIcon || !lightIcon) {
        console.error('Theme icons not found!');
        return;
    }
    
    if (isDark) {
        darkIcon.classList.add('hidden');
        lightIcon.classList.remove('hidden');
    } else {
        lightIcon.classList.add('hidden');
        darkIcon.classList.remove('hidden');
    }
    
    //console.log('Theme updated:', isDark ? 'dark' : 'light');
    //console.log('Dark class present:', html.classList.contains('dark'));
}

// 初始化主题
function initTheme() {
    //console.log('Initializing theme...');
    const isDark = getThemePreference();
    setTheme(isDark);
}

// 在全局作用域定义 toggleTheme 函数
window.toggleTheme = function() {
    //console.log('Toggle theme clicked!');
    const isDark = document.documentElement.classList.contains('dark');
    setTheme(!isDark);
};

// 初始化主题
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
} else {
    initTheme();
} 