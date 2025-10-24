#!/usr/bin/env python3
"""
Script para comparar diferentes configurações de estratégia
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime


def update_config(strategy_mode, require_alignment):
    """Atualiza config/settings.py com nova configuração"""
    settings_path = Path("config/settings.py")
    
    if not settings_path.exists():
        print(f"❌ Arquivo não encontrado: {settings_path}")
        return False
    
    # Ler arquivo
    content = settings_path.read_text(encoding='utf-8')
    
    # Substituir STRATEGY_MODE
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if line.strip().startswith('STRATEGY_MODE'):
            new_lines.append(f'    STRATEGY_MODE: str = "{strategy_mode}"')
        elif line.strip().startswith('REQUIRE_MTF_ALIGNMENT'):
            new_lines.append(f'    REQUIRE_MTF_ALIGNMENT: bool = {require_alignment}')
        else:
            new_lines.append(line)
    
    # Escrever de volta
    settings_path.write_text('\n'.join(new_lines), encoding='utf-8')
    print(f"✅ Config atualizada: {strategy_mode}, alignment={require_alignment}")
    return True


def run_backtest():
    """Executa o backtest"""
    print("\n🔬 Executando backtest...")
    
    try:
        # Executar bot_main.py com input "1" para backtest
        result = subprocess.run(
            [sys.executable, "bot_main.py"],
            input="1\n",
            text=True,
            capture_output=True,
            timeout=900,
            encoding="utf-8",
            errors="ignore"
        )
        
        if result.returncode == 0:
            print("✅ Backtest concluído")
            return True
        else:
            print(f"❌ Backtest falhou: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Backtest timeout (>10 minutos)")
        return False
    except Exception as e:
        print(f"❌ Erro ao executar backtest: {e}")
        return False


def load_results():
    """Carrega resultados do backtest"""
    results_path = Path("reports/backtest_results.json")
    
    if not results_path.exists():
        print(f"❌ Resultados não encontrados: {results_path}")
        return None
    
    try:
        with open(results_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erro ao ler resultados: {e}")
        return None


def save_results(strategy_name, results):
    """Salva resultados com nome específico"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON
    json_path = Path(f"reports/backtest_{strategy_name}_{timestamp}.json")
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # CSV
    csv_src = Path("reports/backtest_trades.csv")
    if csv_src.exists():
        csv_dst = Path(f"reports/backtest_{strategy_name}_{timestamp}.csv")
        csv_dst.write_text(csv_src.read_text())
    
    print(f"✅ Resultados salvos: {json_path}")


def compare_results(all_results):
    """Compara e exibe resultados de todas as estratégias"""
    
    print("\n" + "=" * 90)
    print("COMPARAÇÃO DE ESTRATÉGIAS")
    print("=" * 90)
    
    # Header
    print(f"\n{'Estratégia':<25} {'Trades':<10} {'Win Rate':<12} {'P.Factor':<12} {'Retorno':<12} {'Max DD':<10}")
    print("-" * 90)
    
    # Dados
    for name, results in all_results.items():
        trades = results['total_trades']
        win_rate = results['win_rate']
        pf = results['profit_factor']
        ret = results['total_pnl_percent']
        dd = results['max_drawdown']
        
        print(f"{name:<25} {trades:<10} {win_rate:<11.2f}% {pf:<11.2f} {ret:<11.2f}% {dd:<9.2f}%")
    
    print("=" * 90)
    
    # Análise
    print("\n📊 ANÁLISE:")
    
    # Melhor retorno
    best_return = max(all_results.items(), key=lambda x: x[1]['total_pnl_percent'])
    print(f"\n🏆 Melhor Retorno: {best_return[0]} ({best_return[1]['total_pnl_percent']:.2f}%)")
    
    # Melhor win rate
    best_wr = max(all_results.items(), key=lambda x: x[1]['win_rate'])
    print(f"🎯 Melhor Win Rate: {best_wr[0]} ({best_wr[1]['win_rate']:.2f}%)")
    
    # Melhor profit factor
    best_pf = max(all_results.items(), key=lambda x: x[1]['profit_factor'])
    print(f"💰 Melhor Profit Factor: {best_pf[0]} ({best_pf[1]['profit_factor']:.2f})")
    
    # Menor drawdown
    best_dd = min(all_results.items(), key=lambda x: x[1]['max_drawdown'])
    print(f"🛡️  Menor Drawdown: {best_dd[0]} ({best_dd[1]['max_drawdown']:.2f}%)")
    
    # Mais trades
    most_trades = max(all_results.items(), key=lambda x: x[1]['total_trades'])
    print(f"📈 Mais Trades: {most_trades[0]} ({most_trades[1]['total_trades']})")
    
    # Recomendação
    print("\n" + "=" * 90)
    print("💡 RECOMENDAÇÃO:")
    print("=" * 90)
    
    # Pontuação composta
    scores = {}
    for name, results in all_results.items():
        score = 0
        
        # Retorno (40%)
        score += (results['total_pnl_percent'] / 100) * 40
        
        # Win rate (20%)
        score += (results['win_rate'] / 100) * 20
        
        # Profit factor (20%)
        score += min(results['profit_factor'] / 2, 1) * 20
        
        # Drawdown inverso (20%)
        score += (1 - results['max_drawdown'] / 100) * 20
        
        scores[name] = score
    
    # Melhor pontuação
    best_overall = max(scores.items(), key=lambda x: x[1])
    
    print(f"\n🌟 MELHOR NO GERAL: {best_overall[0]}")
    print(f"   Pontuação: {best_overall[1]:.2f}/100")
    
    print("\n📋 Pontuações:")
    for name, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        print(f"   {name:<25} {score:.2f}/100")
    
    print("\n" + "=" * 90)


def main():
    """Executa comparação de estratégias"""
    
    print("=" * 90)
    print("COMPARAÇÃO DE ESTRATÉGIAS - BINANCE TRADING BOT")
    print("=" * 90)
    
    # Configurações para testar
    configs = [
        ("breakout", False, "Breakout"),
        ("mean_reversion", False, "Mean Reversion"),
        ("trend_following", False, "Trend Following"),
        ("ensemble", False, "Ensemble Moderado"),
        ("ensemble_aggressive", False, "Ensemble Agressivo"),
        ("ensemble_ultra", False, "Ensemble Ultra"),
    ]
    
    all_results = {}
    
    for strategy_mode, require_alignment, display_name in configs:
        print(f"\n\n{'=' * 90}")
        print(f"TESTANDO: {display_name}")
        print(f"Configuração: strategy={strategy_mode}, alignment={require_alignment}")
        print("=" * 90)
        
        # Atualizar config
        if not update_config(strategy_mode, require_alignment):
            print(f"❌ Falha ao atualizar config para {display_name}")
            continue
        
        # Executar backtest
        if not run_backtest():
            print(f"❌ Falha ao executar backtest para {display_name}")
            continue
        
        # Carregar resultados
        results = load_results()
        if not results:
            print(f"❌ Falha ao carregar resultados para {display_name}")
            continue
        
        # Salvar com nome específico
        save_results(display_name.replace(" ", "_").lower(), results)
        
        # Armazenar para comparação
        all_results[display_name] = results
        
        # Resumo rápido
        print(f"\n📊 Resumo rápido:")
        print(f"   Trades: {results['total_trades']}")
        print(f"   Win Rate: {results['win_rate']:.2f}%")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
        print(f"   Retorno: {results['total_pnl_percent']:.2f}%")
        print(f"   Max DD: {results['max_drawdown']:.2f}%")
    
    # Comparação final
    if len(all_results) > 0:
        compare_results(all_results)
        
        # Salvar comparação
        comparison_file = Path(f"reports/strategy_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(comparison_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        print(f"\n💾 Comparação salva em: {comparison_file}")
    else:
        print("\n❌ Nenhum resultado válido para comparar")
    
    print("\n" + "=" * 90)
    print("COMPARAÇÃO CONCLUÍDA!")
    print("=" * 90)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Comparação interrompida pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)