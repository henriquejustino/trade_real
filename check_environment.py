#!/usr/bin/env python3
"""
Script para verificar o ambiente antes de executar o bot
"""

import sys
import os

def check_python_version():
    """Verifica versão do Python"""
    print("=" * 60)
    print("VERIFICAÇÃO DE AMBIENTE")
    print("=" * 60)
    
    version = sys.version_info
    print(f"\n✓ Python Version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ ERRO: Python 3.10 ou superior é necessário")
        return False
    
    if version.minor == 10:
        print("⚠️  AVISO: Python 3.10 detectado. Recomendado: Python 3.11+")
        print("   Algumas features podem ter problemas de compatibilidade")
    
    return True


def check_required_modules():
    """Verifica se módulos necessários estão instalados"""
    print("\n" + "-" * 60)
    print("VERIFICANDO MÓDULOS NECESSÁRIOS")
    print("-" * 60)
    
    required_modules = [
        'binance',
        'ccxt',
        'pandas',
        'numpy',
        'ta',
        'sqlalchemy',
        'dotenv',
        'pydantic',
        'matplotlib',
        'requests'
    ]
    
    missing = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError:
            print(f"❌ {module} - NÃO INSTALADO")
            missing.append(module)
    
    if missing:
        print(f"\n❌ Módulos faltando: {', '.join(missing)}")
        print("\nPara instalar:")
        print("pip install -r requirements.txt")
        return False
    
    return True


def check_directory_structure():
    """Verifica estrutura de diretórios"""
    print("\n" + "-" * 60)
    print("VERIFICANDO ESTRUTURA DE DIRETÓRIOS")
    print("-" * 60)
    
    required_dirs = ['core', 'db', 'config', 'data', 'reports', 'reports/logs']
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✓ {dir_path}/")
        else:
            print(f"⚠️  {dir_path}/ - Será criado automaticamente")
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"   → Criado: {dir_path}/")
            except Exception as e:
                print(f"   ❌ Erro ao criar: {e}")
    
    return True


def check_env_file():
    """Verifica arquivo .env"""
    print("\n" + "-" * 60)
    print("VERIFICANDO ARQUIVO .env")
    print("-" * 60)
    
    if not os.path.exists('.env'):
        print("❌ Arquivo .env não encontrado")
        print("\nPara criar:")
        print("1. Copie o template:")
        if sys.platform == "win32":
            print("   copy config\\.env.example .env")
        else:
            print("   cp config/.env.example .env")
        print("2. Edite o arquivo .env e adicione suas API keys")
        return False
    
    print("✓ Arquivo .env encontrado")
    
    # Verificar se tem chaves configuradas
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_API_SECRET', '')
        
        if not api_key or not api_secret or api_key == 'your_binance_api_key_here':
            print("⚠️  API Keys não configuradas ou usando valores padrão")
            print("   Edite o arquivo .env com suas chaves reais")
            return False
        
        print("✓ API Keys configuradas")
        
    except Exception as e:
        print(f"⚠️  Erro ao verificar .env: {e}")
    
    return True


def check_imports():
    """Testa imports principais do projeto"""
    print("\n" + "-" * 60)
    print("TESTANDO IMPORTS DO PROJETO")
    print("-" * 60)
    
    imports_to_test = [
        ('config.settings', 'Settings'),
        ('db.models', 'Trade'),
        ('core.utils', 'setup_logging'),
        ('core.exchange', 'BinanceExchange'),
        ('core.strategy', 'StrategyFactory'),
        ('core.risk', 'RiskManager'),
    ]
    
    failed = []
    
    for module_name, class_name in imports_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✓ {module_name}.{class_name}")
        except Exception as e:
            print(f"❌ {module_name}.{class_name} - {type(e).__name__}: {e}")
            failed.append(module_name)
    
    if failed:
        print(f"\n❌ Imports falharam: {', '.join(failed)}")
        return False
    
    return True


def main():
    """Executa todas as verificações"""
    
    checks = [
        ("Versão Python", check_python_version),
        ("Módulos Necessários", check_required_modules),
        ("Estrutura de Diretórios", check_directory_structure),
        ("Arquivo .env", check_env_file),
        ("Imports do Projeto", check_imports),
    ]
    
    results = []
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"\n❌ ERRO em {check_name}: {e}")
            results.append((check_name, False))
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DA VERIFICAÇÃO")
    print("=" * 60)
    
    all_passed = True
    for check_name, result in results:
        status = "✓ PASSOU" if result else "❌ FALHOU"
        print(f"{status} - {check_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ AMBIENTE OK! Você pode executar o bot:")
        print("\n   python bot_main.py")
    else:
        print("❌ AMBIENTE COM PROBLEMAS")
        print("\nResolva os problemas acima antes de executar o bot")
        print("\nPara ajuda, consulte:")
        print("  - QUICKSTART.md")
        print("  - TROUBLESHOOTING.md")
        print("  - README.md")
    
    print("=" * 60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)