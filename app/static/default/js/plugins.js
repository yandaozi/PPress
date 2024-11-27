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

// 确认卸载插件
function confirmUninstall(form) {
    showAlert('确定要卸载该插件吗？', 'warning', '确认', function() {
        handleFormSubmit(form);
    });
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