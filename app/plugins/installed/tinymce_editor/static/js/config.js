
// TinyMCE 默认配置
window.TINYMCE_CONFIG = {
    // 基础配置
    language: 'zh_CN',
    branding: false,
    
    // 插件配置
    /*plugins: [
        'advlist',
        'anchor',
        'autolink',
        'autoresize',
        'autosave',
        'charmap',
        'code',
        'codesample',
        'directionality',
        'emoticons',
        'fullscreen',
        'help',
        'image',
        'importcss',
        'insertdatetime',
        'link',
        'lists',
        'media',
        'nonbreaking',
        'pagebreak',
        'preview',
        'quickbars',
        'save',
        'searchreplace',
        'visualblocks',
        'visualchars',
        'wordcount'
    ],*/
    
    // 工具栏配置
    toolbar: [
        {
            name: 'history', items: ['undo', 'redo']
        },
        {
            name: 'styles', items: ['formatselect', 'fontselect', 'fontsizeselect']
        },
        {
            name: 'formatting',
            items: ['bold', 'italic', 'underline', 'strikethrough', 'forecolor', 'backcolor']
        },
        {
            name: 'alignment',
            items: ['alignleft', 'aligncenter', 'alignright', 'alignjustify']
        },
        {
            name: 'indentation',
            items: ['outdent', 'indent']
        },
        {
            name: 'lists',
            items: ['bullist', 'numlist']
        },
        {
            name: 'insert',
            items: ['link', 'image', 'media', 'codesample', 'charmap', 'emoticons']
        },
        {
            name: 'tools',
            items: ['searchreplace', 'preview', 'code', 'fullscreen']
        }
    ],
    
    // 菜单配置
    menubar: 'file edit view insert format tools',
    menu: {
        file: {
            title: '文件',
            items: 'newdocument restoredraft | preview | print'
        },
        edit: {
            title: '编辑',
            items: 'undo redo | cut copy paste pastetext | selectall searchreplace'
        },
        view: {
            title: '视图',
            items: 'code | visualaid visualchars visualblocks | spellchecker | preview fullscreen'
        },
        insert: {
            title: '插入',
            items: 'image link media codesample | charmap emoticons hr | pagebreak nonbreaking anchor | insertdatetime'
        },
        format: {
            title: '格式',
            items: 'bold italic underline strikethrough superscript subscript | blocks fontfamily fontsize | forecolor backcolor | removeformat'
        },
        tools: {
            title: '工具',
            items: 'spellchecker wordcount code'
        }
    },
    
    // 代码示例配置
    codesample_languages: [
        { text: 'HTML/XML', value: 'markup' },
        { text: 'JavaScript', value: 'javascript' },
        { text: 'CSS', value: 'css' },
        { text: 'PHP', value: 'php' },
        { text: 'Python', value: 'python' },
        { text: 'Java', value: 'java' },
        { text: 'C', value: 'c' },
        { text: 'C++', value: 'cpp' }
    ],

    // 监听主题变化
    /*setup: function(editor) {
        // 等待编辑器初始化完成后再设置初始主题
        editor.on('init', function() {
            // 设置初始主题
            const isDark = document.documentElement.classList.contains('dark');
            if (isDark) {
                editor.dom.addClass(editor.getBody(), 'dark-theme');
                editor.getBody().setAttribute('data-mce-style',
                    'overflow-y: hidden; padding-left: 1px; padding-right: 1px; min-height: inherit; background: #1f2937;'
                );
            }
        });

        // 监听主题变化
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'class') {
                    const isDark = document.documentElement.classList.contains('dark');
                    const content = editor.getContent();
                    editor.setContent(''); // 临时清空内容
                    if (isDark) {
                        editor.dom.addClass(editor.getBody(), 'dark-theme');
                        editor.getBody().setAttribute('data-mce-style',
                            'overflow-y: hidden; padding-left: 1px; padding-right: 1px; min-height: inherit; background: #1f2937;'
                        );
                    } else {
                        editor.dom.removeClass(editor.getBody(), 'dark-theme');
                        editor.getBody().setAttribute('data-mce-style',
                            'overflow-y: hidden; padding-left: 1px; padding-right: 1px; min-height: inherit;'
                        );
                    }
                    editor.setContent(content); // 恢复内容
                }
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class']
        });
    }
*/
}; 