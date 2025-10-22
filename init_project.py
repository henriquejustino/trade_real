#!/usr/bin/env python3
"""
Script de inicialização do projeto
Cria estrutura de diretórios e arquivos necessários
"""

import os
import sys
from pathlib import Path


def create_directory_structure():
    """Cria estrutura de diretórios"""
    print("Criando estrutura de diretórios...")
    
    directories = [
        'core',
        'db',
        'config',
        'data',
        'reports',
        'reports/logs',
        'tests'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Criado: {directory}/")
        else:
            print(f"  ✓ Existe: {directory}/")


def create_init_files():
    """Cria arquivos __init__.py necessários"""
    print("\nCriando arquivos __init__.py...")
    
    init_files = [
        'core/__init__.py',
        'db/__init__.py',
        'config/__init__.py',
        'tests/__init__.py'
    ]
    
    for init_file in init_files:
        path = Path(init_file)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('"""Module initialization"""\n')
            print(f"  ✓ Criado: {init_file}")
        else:
            print(f"  ✓ Existe: {init_file}")


def create_env_file():
    """Cria arquivo .env se não existir"""
    print("\nVerificando arquivo .env...")
    
    env_path = Path('.env')
    env_example_path = Path('config/.env.example')
    
    if env_path.exists():
        print("  ✓ Arquivo .env já existe")
        return
    
    if env_example_path.exists():
        # Copiar do exemplo
        content = env_example_path.read_text()
        env_path.write_text(content)
        print("  ✓ Arquivo .env criado a partir do template")
        print("  ⚠️  IMPORTANTE: Edite o arquivo .env com suas API keys!")
    else:
        # Criar template básico
        template = """# Binance API Configuration
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here

# Testnet API Configuration
TESTNET_API_KEY=your_testnet_api_key_here
TESTNET_API_SECRET=your_testnet_api_secret_here

# Database
DATABASE_URL=sqlite:///db/state.db

# Notifications (Optional)
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

SLACK_ENABLED=false
SLACK_WEBHOOK_URL=
"""
        env_path.write_text(template)
        print("  ✓ Arquivo .env criado com template básico")
        print("  ⚠️  IMPORTANTE: Edite o arquivo .env com suas API keys!")


def create_gitignore():
    """Cria .gitignore se não existir"""
    print("\nVerificando .gitignore...")
    
    gitignore_path = Path('.gitignore')
    
    if gitignore_path.exists():
        print("  ✓ Arquivo .gitignore já existe")
        return
    
    content = """# Python
__pycache__/
*.py[cod]
*.so
.Python
*.egg-info/

# Virtual Environment
venv/
env/
ENV/

# Environment variables
.env

# Database
*.db
*.sqlite
db/state.db

# Logs
*.log
reports/logs/

# Data
data/*.csv
data/*.json

# Reports
reports/*.html
reports/*.pdf
reports/*.png
reports/*.json
reports/*.csv

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
"""
    
    gitignore_path.write_text(content)
    print("  ✓ Arquivo .gitignore criado")


def verify_python_version():
    """Verifica versão do Python"""
    print("\nVerificando versão do Python...")
    
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("  ❌ ERRO: Python 3.10 ou superior é necessário")
        print("     Sua versão: {}.{}.{}".format(version.major, version.minor, version.micro))
        return False
    
    if version.minor == 10:
        print("  ⚠️  Python 3.10 detectado. Funciona, mas 3.11+ é recomendado")
    else:
        print("  ✓ Versão adequada")
    
    return True


def check_dependencies():
    """Verifica se dependências estão instaladas"""
    print("\nVerificando dependências básicas...")
    
    required = ['dotenv', 'pydantic', 'sqlalchemy']
    missing = []
    
    for module in required:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError:
            print(f"  ❌ {module} não instalado")
            missing.append(module)
    
    if missing:
        print(f"\n  Para instalar dependências faltantes:")
        print(f"  pip install {' '.join(missing)}")
        print(f"\n  Ou instale tudo:")
        print(f"  pip install -r requirements.txt")
        return False
    
    return True


def main():
    """Executa inicialização"""
    print("=" * 60)
    print("INICIALIZAÇÃO DO PROJETO - BINANCE TRADING BOT")
    print("=" * 60)
    
    # Verificar Python
    if not verify_python_version():
        print("\n❌ Versão do Python incompatível. Atualize antes de continuar.")
        return False
    
    # Criar estrutura
    create_directory_structure()
    create_init_files()
    create_env_file()
    create_gitignore()
    
    # Verificar dependências
    deps_ok = check_dependencies()
    
    print("\n" + "=" * 60)
    print("INICIALIZAÇÃO CONCLUÍDA")
    print("=" * 60)
    
    if deps_ok:
        print("\n✅ Projeto inicializado com sucesso!")
        print("\nPróximos passos:")
        print("1. Edite o arquivo .env com suas API keys")
        print("2. Execute: python check_environment.py")
        print("3. Execute: python bot_main.py")
    else:
        print("\n⚠️  Projeto inicializado, mas faltam dependências")
        print("\nPróximos passos:")
        print("1. Execute: pip install -r requirements.txt")
        print("2. Edite o arquivo .env com suas API keys")
        print("3. Execute: python check_environment.py")
        print("4. Execute: python bot_main.py")
    
    print("\n" + "=" * 60 + "\n")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInicialização cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRO durante inicialização: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)