// 确认重载插件
function confirmReload(form) {
    showAlert(
        '重载插件将重新加载插件的配置信息与已设置内容，确定要继续吗？',
        'warning', 
        '确认重载', 
        function() {
            handleFormSubmit(form);
        }
    );
}

// 处理表单提交
function handleFormSubmit(form) {
    const formData = new FormData(form);
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert(data.message, 'success', '成功');
            setTimeout(() => window.location.reload(), 300);
        } else {
            showAlert(data.message, 'error', '错误');
        }
    })
    .catch(error => {
        showAlert('操作失败：' + error.message, 'error', '错误');
    });
}

// 认卸载插件
function confirmUninstall(form) {
    showAlert(
        '确定要卸载该插件吗？此操作不可恢复！', 
        'warning', 
        '确认卸载', 
        function() {
            handleFormSubmit(form);
        }
    );
}

// 初始化文件上传处理
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('plugin-file');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            e.preventDefault();
            const form = this.closest('form');
            if (form && this.files.length > 0) {
                handleFormSubmit(form);
            }
        });
    }
});

// 打开插件设置
async function openPluginSettings(pluginName) {
    try {
        // 先检查插件是否有设置页面
        const response = await fetch(`plugins/${pluginName}/settings/check`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            // 如果有设置页面，跳转过去
            window.location.href = `plugins/${pluginName}/settings`;
        } else {
            // 如果没有设置页面，显示提示
            showToast(data.message || '该插件没有设置页面', 'error');
        }
    } catch (error) {
        console.error('Error checking plugin settings:', error);
        showToast('检查插件设置失败', 'error');
    }
}

// 关闭设置弹窗
function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
    document.getElementById('settings-content').innerHTML = '';
}

// 显示提示信息
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 transform transition-all duration-300 ${
        type === 'error' ? 'bg-red-500 text-white' : 'bg-blue-500 text-white'
    }`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // 淡入效果
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    }, 100);
    
    // 3秒后淡出
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(1rem)';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
    if(type!='error'){
        setTimeout(() => {
            window.location.reload();
        }, 300);
    }

}

// 处理表单提交
async function handleFormSubmit(form) {
    try {
        const formData = new FormData(form);
        const response = await fetch(form.action, {
            method: form.method,
            body: formData
        });
        
        const data = await response.json();
        showToast(data.message, data.status);
        
        if (data.status === 'success' && data.reload_required) {
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    } catch (error) {
        console.error('Error submitting form:', error);
        showToast('操作失败', 'error');
    }
}

// 处理设置表单提交
async function handleSettingsSubmit(form) {
    try {
        const formData = new FormData(form);
        const response = await fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        const data = await response.json();
        showToast(data.message, data.status);
        
        if (data.status === 'success') {
            // 延迟一下再刷新，让用户看到成功提示
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showToast('保存设置失败', 'error');
    }
} 