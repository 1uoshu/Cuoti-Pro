const WebSocket = require('ws');

const TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg1Mzc3Mjg5LCJqdGkiOiJXN1pnai1hZUtnWl9WUElCM2JNUE9lRGtOWEtfdVBDUiIsInR5cCI6ImFjY2VzcyJ9.jLl2jREHf0pwIFV7kyTs7-2uM2gnC5g1Holm_H6HySA";
const SESSION_ID = 9;

const ws = new WebSocket(`ws://localhost:8000/api/agent/ws?session_id=${SESSION_ID}&token=${TOKEN}`);

ws.on('open', () => {
    console.log('WebSocket connected');

    // 等待1秒后发送消息
    setTimeout(() => {
        const message = {
            type: 'chat.message',
            content: '[用户上传了文件，未附带文字说明]'
        };
        console.log('Sending message:', message);
        ws.send(JSON.stringify(message));
    }, 1000);
});

ws.on('message', (data) => {
    const msg = JSON.parse(data);
    console.log('Received:', msg.type, msg.data ? JSON.stringify(msg.data).substring(0, 100) : '');
});

ws.on('error', (error) => {
    console.error('WebSocket error:', error.message);
});

ws.on('close', () => {
    console.log('WebSocket closed');
    process.exit(0);
});

// 30秒后自动关闭
setTimeout(() => {
    console.log('Timeout, closing...');
    ws.close();
}, 30000);
