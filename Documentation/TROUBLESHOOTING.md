# 🔧 Guia de Solução de Problemas

## 🚨 Problemas Comuns e Soluções

### 1. Erros de Instalação

#### ❌ "Python version too old"

**Erro:**
```
Error: Python 3.11 or higher is required
Current version: 3.9.x
```

**Solução:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv

# macOS (usando Homebrew)
brew install python@3.11

# Windows
# Baixe de https://www.python.org/downloads/
```

#### ❌ "pip: command not found"

**Solução:**
```bash
# Linux
sudo apt install python3-pip

# macOS
python3 -m ensurepip

# Windows
python -m ensurepip --upgrade
```

#### ❌ "Failed to install TA-Lib"

**Erro:**
```
error: Microsoft Visual C++ 14.0 or greater is required
```

**Solução (Windows):**
```bash
# Instalar Microsoft C++ Build Tools
# https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Ou usar ta ao invés de ta-lib
pip install ta
# (já incluído em requirements.txt)
```

**Solução (Linux):**
```bash
sudo apt-get install build-essential
```

---

### 2. Erros de Configuração

#### ❌ "API keys not configured"

**Erro:**
```
ValueError: Binance API keys not configured
```

**Solução:**
```bash
# 1. Verifique se .env existe
ls -la .env

# 2. Se não existir, crie
cp config/.env.example .env

# 3. Edite e adicione suas chaves
nano .env

# 4. Verifique o conteúdo (sem mostrar secrets)
grep "API_KEY" .env | cut -d'=' -f1
```

#### ❌ "Invalid API key"

**Erro:**
```
BinanceAPIException: Invalid API-key, IP, or permissions
```

**Soluções possíveis:**

1. **Verificar chaves:**
```bash
# As chaves devem ter 64 caracteres
echo $BINANCE_API_KEY | wc -c
```

2. **Verificar permissões na Binance:**
   - Acesse Binance → API Management
   - Verifique se API está ativada
   - Confirme que "Enable Spot & Margin Trading" está marcado

3. **Verificar restrições de IP:**
   - Se configurou IP whitelist, adicione seu IP atual
   - Ou remova restrição de IP (menos seguro)

4. **Gerar novas chaves:**
   - Às vezes chaves antigas expiram
   - Gere novas e atualize .env

---

### 3. Erros de Conexão

#### ❌ "Connection refused" ou "Timeout"

**Erro:**
```
requests.exceptions.ConnectionError: Connection refused
```

**Diagnóstico:**
```bash
# 1. Testar conectividade básica
ping api.binance.com

# 2. Testar API
curl https://api.binance.com/api/v3/ping

# 3. Verificar proxy/firewall
env | grep -i proxy
```

**Soluções:**

1. **Problema de internet:**
```bash
# Reiniciar conexão de rede
sudo systemctl restart NetworkManager  # Linux
```

2. **Firewall bloqueando:**
```bash
# Permitir saída para Binance
sudo ufw allow out to api.binance.com
```

3. **Binance em manutenção:**
   - Verifique: https://www.binance.com/en/support/announcement
   - Aguarde conclusão da manutenção

#### ❌ "Rate limit exceeded"

**Erro:**
```
BinanceAPIException: Too many requests
```

**Solução:**
```python
# Em config/settings.py, ajuste:
MAX_REQUESTS_PER_MINUTE = 800  # Reduzir de 1200
RATE_LIMIT_BUFFER = 0.5  # Mais conservador (50%)
```

---

### 4. Erros de Trading

#### ❌ "Position size too small"

**Erro:**
```
Position size too small after applying filters
```

**Causas:**
- Capital insuficiente
- minNotional muito alto
- Preço do ativo muito alto

**Soluções:**

1. **Aumentar capital:**
```python
# Em config/settings.py
BACKTEST_INITIAL_CAPITAL = Decimal("50000")  # De 10000 para 50000
```

2. **Reduzir mínimo:**
```python
MIN_POSITION_SIZE_USD = Decimal("5.0")  # De 10 para 5
```

3. **Escolher pares mais baratos:**
```python
TRADING_PAIRS = ["ADAUSDT", "DOGEUSDT"]  # Em vez de BTCUSDT
```

#### ❌ "Filter validation failed"

**Erro:**
```
Quantity 0.123456789 does not comply with step size 0.001
```

**Solução:**
O bot já faz isso automaticamente, mas se erro persistir:

```python
# Em core/utils.py, a função round_down já corrige
# Verifique se está sendo chamada corretamente
```

#### ❌ "Insufficient balance"

**Erro:**
```
BinanceAPIException: Account has insufficient balance
```

**Soluções:**

1. **Verificar saldo:**
```bash
# No Python shell
from core.exchange import BinanceExchange
exchange = BinanceExchange(api_key, api_secret)
account = exchange.get_account()
for balance in account['balances']:
    if float(balance['free']) > 0:
        print(f"{balance['asset']}: {balance['free']}")
```

2. **Depositar fundos:**
   - Acesse Binance e deposite USDT
   - Aguarde confirmação

3. **Ajustar risk:**
```python
RISK_PER_TRADE = Decimal("0.01")  # 1% ao invés de 2%
```

---

### 5. Erros de Database

#### ❌ "Database locked"

**Erro:**
```
sqlite3.OperationalError: database is locked
```

**Solução:**
```bash
# 1. Verificar processos usando o DB
lsof db/state.db

# 2. Matar processo travado
kill -9 <PID>

# 3. Se persistir, recriar DB
mv db/state.db db/state.db.backup
python bot_main.py  # Recriará automaticamente
```

#### ❌ "No such table"

**Erro:**
```
sqlalchemy.exc.OperationalError: no such table: trades
```

**Solução:**
```bash
# Deletar e recriar database
rm db/state.db
python bot_main.py  # Tabelas serão criadas automaticamente
```

---

### 6. Erros de Backtest

#### ❌ "Not enough data"

**Erro:**
```
ValueError: Need at least 200 candles for strategy
```

**Solução:**
```python
# Aumentar período de backtest
BACKTEST_START_DATE = "2023-01-01"  # Ao invés de 2024-01-01
```

#### ❌ "Failed to fetch historical data"

**Erro:**
```
Exception: Failed to load data for BTCUSDT
```

**Soluções:**

1. **Verificar símbolo:**
```python
# Símbolo deve ser válido na Binance
TRADING_PAIRS = ["BTCUSDT"]  # Correto
# TRADING_PAIRS = ["BTC-USDT"]  # Errado
```

2. **Limpar cache:**
```bash
rm data/*.csv
# Bot irá redownload
```

3. **Baixar manualmente:**
```python
from core.exchange import BinanceExchange
exchange = BinanceExchange("", "")  # Sem API keys para dados públicos
df = exchange.get_klines("BTCUSDT", "1h", limit=1000)
df.to_csv("data/BTCUSDT_1h.csv")
```

---

### 7. Erros de Notificação

#### ❌ "Telegram: Unauthorized"

**Erro:**
```
telegram.error.Unauthorized: Forbidden
```

**Solução:**
```bash
# 1. Verificar token
echo $TELEGRAM_BOT_TOKEN

# 2. Testar bot
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# 3. Gerar novo token com @BotFather se necessário
```

#### ❌ "Chat not found"

**Erro:**
```
telegram.error.BadRequest: Chat not found
```

**Solução:**
```bash
# 1. Verificar chat ID
echo $TELEGRAM_CHAT_ID

# 2. Iniciar conversa com bot
# Abra Telegram, busque seu bot, clique em START

# 3. Obter chat ID correto
# Use @userinfobot no Telegram
```

---

### 8. Erros de Performance

#### ❌ "Bot muito lento"

**Sintomas:**
- Demora para processar
- High CPU usage
- Memory leaks

**Soluções:**

1. **Reduzir pares:**
```python
TRADING_PAIRS = ["BTCUSDT", "ETHUSDT"]  # Ao invés de 10 pares
```

2. **Aumentar intervalo:**
```python
# Em trade_manager.py, linha do time.sleep
time.sleep(300)  # 5 minutos ao invés de 60 segundos
```

3. **Desabilitar logs detalhados:**
```python
LOG_LEVEL = "INFO"  # Ao invés de DEBUG
```

4. **Limpar logs antigos:**
```bash
find reports/logs/ -name "*.log" -mtime +7 -delete
```

---

### 9. Erros do Docker

#### ❌ "Cannot connect to Docker daemon"

**Erro:**
```
docker: Cannot connect to the Docker daemon
```

**Solução:**
```bash
# Iniciar Docker
sudo systemctl start docker

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker

# Verificar
docker ps
```

#### ❌ "Port already in use"

**Erro:**
```
Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Solução:**
```bash
# 1. Encontrar processo usando a porta
sudo lsof -i :8080

# 2. Matar processo
sudo kill -9 <PID>

# 3. Ou mudar porta no docker-compose.yml
ports:
  - "8081:8080"  # Ao invés de 8080:8080
```

---

### 10. Circuit Breaker Ativado

#### ⚠️ "Circuit breaker triggered"

**Mensagem:**
```
🚨 CIRCUIT BREAKER TRIGGERED: Drawdown 16.5% exceeds limit
```

**O que fazer:**

1. **Analisar o que aconteceu:**
```bash
# Ver últimos trades
sqlite3 db/state.db "SELECT * FROM trades ORDER BY entry_time DESC LIMIT 20;"

# Ver performance
sqlite3 db/state.db "SELECT * FROM performance ORDER BY date DESC LIMIT 7;"
```

2. **Revisar estratégia:**
   - Mercado mudou?
   - Parâmetros adequados?
   - Muita volatilidade?

3. **Ajustar configuração:**
```python
# Mais conservador
RISK_PER_TRADE = Decimal("0.01")  # 1%
MAX_OPEN_TRADES = 2  # Menos posições simultâneas
STOP_LOSS_PERCENT = Decimal("0.015")  # Stop mais apertado (1.5%)
```

4. **Reiniciar após ajustes:**
```bash
# O bot precisa ser reiniciado manualmente após circuit breaker
python bot_main.py
```

---

## 🔍 Ferramentas de Diagnóstico

### Verificar Estado do Bot

```bash
# Ver se está rodando
ps aux | grep bot_main

# Ver uso de recursos
top -p $(pgrep -f bot_main)

# Ver conexões de rede
sudo netstat -tunap | grep python
```

### Analisar Logs

```bash
# Últimas 100 linhas
tail -n 100 reports/logs/trading_bot.log

# Apenas erros
grep ERROR reports/logs/trading_bot.log

# Erros nas últimas 24h
find reports/logs/ -name "*.log" -mtime -1 -exec grep ERROR {} \;

# Seguir log em tempo real
tail -f reports/logs/trading_bot.log
```

### Inspecionar Database

```bash
# Abrir SQLite
sqlite3 db/state.db

# Comandos úteis:
.tables                              # Listar tabelas
.schema trades                       # Ver estrutura
SELECT COUNT(*) FROM trades;         # Total de trades
SELECT * FROM trades WHERE status='OPEN';  # Trades abertos
SELECT symbol, COUNT(*), SUM(pnl) FROM trades GROUP BY symbol;  # Por par
```

### Testar API

```python
# Python shell
from core.exchange import BinanceExchange
from config.settings import Settings

settings = Settings()
api_key, api_secret = settings.get_api_credentials(testnet=False)
exchange = BinanceExchange(api_key, api_secret)

# Testar conectividade
print(exchange.ping())  # Deve retornar True

# Ver saldo
account = exchange.get_account()
print(account['balances'])

# Testar ordem (testnet)
# exchange = BinanceExchange(api_key, api_secret, testnet=True)
# order = exchange.create_order("BTCUSDT", "BUY", "MARKET", 0.001, test=True)
```

---

## 📞 Onde Buscar Ajuda

### Documentação
- README.md - Guia completo
- QUICKSTART.md - Início rápido
- PROJECT_STRUCTURE.md - Arquitetura

### Logs
- `reports/logs/trading_bot.log` - Logs detalhados
- Console output - Mensagens importantes

### Binance
- Status: https://www.binance.com/en/support/announcement
- API Docs: https://binance-docs.github.io/apidocs/spot/en/
- Support: https://www.binance.com/en/support

### Python/Libraries
- python-binance: https://python-binance.readthedocs.io/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Pandas: https://pandas.pydata.org/docs/

---

## 🆘 Último Recurso

Se nada funcionar:

### Reset Completo

```bash
# 1. Backup de dados importantes
cp .env .env.backup
cp db/state.db db/state.db.backup

# 2. Limpar tudo
rm -rf venv/
rm -rf db/*.db
rm -rf reports/logs/*.log
rm -rf data/*.csv

# 3. Reinstalar
./install.sh

# 4. Restaurar .env
cp .env.backup .env

# 5. Testar
python bot_main.py
```

---

**💡 Dica:** Sempre mantenha backups regulares de `.env` e `db/state.db`!

**🔒 Lembre-se:** Nunca compartilhe logs que contenham API keys ou dados sensíveis!