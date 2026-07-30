@echo off
chcp 65001 > nul
echo ========================================
echo 启动后端服务
echo ========================================
cd /d "d:\Microcontroller\agent\Cuoti-Pro-main\Cuoti-Pro-main\backend"
start "Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 5 /nobreak > nul

echo.
echo ========================================
echo 测试后端健康检查
echo ========================================
curl -s http://127.0.0.1:8000/ 2>nul
if errorlevel 1 (
    echo [错误] 后端未启动或无响应
    pause
    exit /b 1
)

echo.
echo ========================================
echo 测试创建会话接口 (需要token)
echo ========================================
echo 提示: 如果返回401，需要先登录获取token
echo.

REM 尝试从localStorage读取token（需要手动复制粘贴）
set /p TOKEN="请粘贴您的JWT token (或按Enter跳过): "

if "%TOKEN%"=="" (
    echo [跳过] 未提供token，无法测试需要认证的接口
    echo 请在浏览器中:
    echo   1. 打开 http://localhost:5173
    echo   2. 登录后按F12打开开发者工具
    echo   3. Console执行: localStorage.getItem('token'^)
    echo   4. 复制token重新运行此脚本
) else (
    curl -X POST "http://127.0.0.1:8000/api/agent/sessions?title=测试会话" ^
         -H "Authorization: Bearer %TOKEN%" ^
         -H "Content-Type: application/json" ^
         -w "\nHTTP Status: %%{http_code}\n"
)

echo.
echo ========================================
echo 启动前端服务
echo ========================================
cd /d "d:\Microcontroller\agent\Cuoti-Pro-main\Cuoti-Pro-main\frontend (2)\frontend"
start "Frontend" cmd /k "pnpm dev"

echo.
echo ========================================
echo 服务已启动
echo ========================================
echo 后端: http://127.0.0.1:8000
echo 前端: http://localhost:5173
echo API文档: http://127.0.0.1:8000/docs
echo.
echo 请在浏览器中访问前端并测试创建会话功能
echo 如果遇到500错误，请查看后端窗口的完整错误堆栈
echo.
pause
