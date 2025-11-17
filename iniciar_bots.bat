@echo off
REM =================================================================
REM == Script para iniciar todos os bots e o agendador do sistema  ==
REM == ATUALIZADO para incluir o duvidas_bot.py                   ==
REM =================================================================

title Painel de Controle dos Bots

echo.
echo ===========================================
echo   INICIANDO SERVICOS EM JANELAS SEPARADAS
echo ===========================================
echo.

REM -- Bot da Fila Telefônica (bot.py) --
echo [1/7] Iniciando o Bot da Fila Telefonica...
start "Bot - Fila Telefonica" cmd /k "venv\Scripts\activate && python bot.py"
timeout /t 2 >nul

REM -- Bot de Lembretes (lembrete_bot.py) --
echo [2/7] Iniciando o Bot de Lembretes...
start "Bot - Lembretes" cmd /k "venv\Scripts\activate && python lembrete_bot.py"
timeout /t 2 >nul

REM -- Bot de Tickets (ticket_bot.py) --
echo [3/7] Iniciando o Bot de Tickets...
start "Bot - Tickets" cmd /k "venv\Scripts\activate && python ticket_bot.py"
timeout /t 2 >nul

REM -- Bot de Queries (query_bot.py) --
echo [4/7] Iniciando o Bot de Queries...
start "Bot - Queries" cmd /k "venv\Scripts\activate && python query_bot.py"
timeout /t 2 >nul

REM -- Bot de Notificações Gerais (bot_notificacoes.py) --
echo [5/7] Iniciando o Bot de Notificacoes Gerais...
start "Bot - Notificacoes" cmd /k "venv\Scripts\activate && python bot_notificacoes.py"
timeout /t 2 >nul

REM -- Bot de Dúvidas (duvidas_bot.py) --
echo [6/7] Iniciando o Bot de Duvidas...
start "Bot - Duvidas" cmd /k "venv\Scripts\activate && python duvidas_bot.py"
timeout /t 2 >nul

REM -- Agendador de Lembretes (scheduler.py) --
echo [7/7] Iniciando o Agendador de Lembretes...
start "Agendador - Lembretes" cmd /k "venv\Scripts\activate && python scheduler.py"

echo.
echo ===========================================
echo   TODOS OS BOTS FORAM INICIADOS!
echo   Verifique as 7 novas janelas que abriram.
echo ===========================================
echo.

timeout /t 5 >nul