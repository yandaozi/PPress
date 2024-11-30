import base64
import hashlib
import json

class CopyrightEncryptor:
    @staticmethod
    def encrypt_html(text):
        # 构建HTML
        html = f'''
        <div class="copyright-info">
            {text}
        </div>
        '''
        return html

    @staticmethod 
    def get_copyright():
        text = '''
        <div class="text-center text-gray-500 text-sm">
            <p onclick='window.location.href="\u0068\u0074\u0074\u0070\u0073\u003a\u002f\u002f\u0067\u0069\u0074\u0068\u0075\u0062\u002e\u0063\u006f\u006d\u002f\u004b\u007a\u004d\u006e\u004c\u007a\u002f\u0050\u0050\u0072\u0065\u0073\u0073"'>\u00a9\u0020\u0032\u0030\u0032\u0034\u0020\u0050\u0050\u0072\u0065\u0073\u0073\u0020\u7248\u6743\u6240\u6709 version 0.1</p>
        </div>
        '''
        return CopyrightEncryptor.encrypt_html(text) 