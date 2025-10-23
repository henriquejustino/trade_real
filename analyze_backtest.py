#!/usr/bin/env python3
"""
Analisa resultados do backtest e mostra estatísticas detalhadas
"""

import json
import sys
from pathlib import Path
import pandas as pd


def analyze_backtest():
    """Analisa resultados do backtest"""
    
    print("=" * 70)
    print("ANÁLISE DE BACKTEST")
    print("=" * 70)
    
    # 1. Verificar se arquivos existem
    results_file = Path("reports/backtest_results.json")
    trades_file = Path("reports/backtest_trades.csv")
    
    if not results_file.exists():
        print("\n❌ Arquivo de resultados não encontrado: reports/backtest_results.json")
        print("   Execute o backtest primeiro: python bot_main.py → opção 1")
        return False
    
    # 2. Carregar resultados
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
    except Exception as e:
        print(f"\n❌ Erro ao ler resultados: {e}")
        return False
    
    # 3. Mostrar resumo
    print("\n" + "-" * 70)
    print("RESUMO GERAL")
    print("-" * 70)
    
    print(f"\n💰 CAPITAL:")
    print(f"   Inicial:  ${results['initial_capital']:,.2f}")
    print(f"   Final:    ${results['final_capital']:,.2f}")
    print(f"   PnL:      ${results['total_pnl']:,.2f} ({results['total_pnl_percent']:+.2f}%)")
    
    print(f"\n📊 TRADES:")
    print(f"   Total:           {results['total_trades']}")
    print(f"   Vencedores:      {results['winning_trades']}")
    print(f"   Perdedores:      {results['losing_trades']}")
    print(f"   Win Rate:        {results['win_rate']:.2f}%")
    
    if results['total_trades'] == 0:
        print("\n⚠️  ATENÇÃO: NENHUM TRADE FOI EXECUTADO!")
        print("\nPossíveis causas:")
        print("   1. Estratégia não encontrou sinais fortes suficientes")
        print("   2. Threshold de sinal muito alto (strength > 0.6)")
        print("   3. Período de dados inadequado")
        print("   4. Pares escolhidos não tiveram oportunidades")
        print("\nSugestões:")
        print("   1. Reduza o threshold em config/settings.py")
        print("   2. Teste com apenas 1 par: TRADING_PAIRS = ['BTCUSDT']")
        print("   3. Use estratégia mais agressiva: STRATEGY_MODE = 'breakout'")
        print("   4. Aumente o período: BACKTEST_START_DATE = '2023-01-01'")
        return False
    
    print(f"\n💵 PnL POR TRADE:")
    print(f"   Média (Wins):    ${results['avg_win']:,.2f}")
    print(f"   Média (Losses):  ${results['avg_loss']:,.2f}")
    print(f"   Maior Win:       ${results['largest_win']:,.2f}")
    print(f"   Maior Loss:      ${results['largest_loss']:,.2f}")
    print(f"   Profit Factor:   {results['profit_factor']:.2f}")
    
    print(f"\n📈 MÉTRICAS DE RISCO:")
    print(f"   Sharpe Ratio:    {results['sharpe_ratio']:.2f}")
    print(f"   Sortino Ratio:   {results['sortino_ratio']:.2f}")
    print(f"   Max Drawdown:    {results['max_drawdown']:.2f}%")
    
    # 4. Análise da equity curve
    print("\n" + "-" * 70)
    print("EVOLUÇÃO DO CAPITAL")
    print("-" * 70)
    
    equity = results['equity_curve']
    print(f"\n   Máximo:   ${max(equity):,.2f}")
    print(f"   Mínimo:   ${min(equity):,.2f}")
    print(f"   Atual:    ${equity[-1]:,.2f}")
    
    # 5. Análise de trades (se existir CSV)
    if trades_file.exists():
        try:
            df_trades = pd.read_csv(trades_file)
            
            print("\n" + "-" * 70)
            print("ANÁLISE POR PAR")
            print("-" * 70)
            
            for symbol in df_trades['symbol'].unique():
                trades_symbol = df_trades[df_trades['symbol'] == symbol]
                total = len(trades_symbol)
                wins = len(trades_symbol[trades_symbol['pnl'] > 0])
                losses = len(trades_symbol[trades_symbol['pnl'] < 0])
                win_rate = (wins / total * 100) if total > 0 else 0
                total_pnl = trades_symbol['pnl'].sum()
                
                print(f"\n   {symbol}:")
                print(f"      Trades: {total} | Wins: {wins} | Losses: {losses}")
                print(f"      Win Rate: {win_rate:.1f}% | PnL: ${total_pnl:,.2f}")
            
            print("\n" + "-" * 70)
            print("MELHORES E PIORES TRADES")
            print("-" * 70)
            
            # Top 3 melhores
            best = df_trades.nlargest(3, 'pnl')[['symbol', 'side', 'pnl', 'pnl_percent']]
            print("\n   🏆 TOP 3 MELHORES:")
            for idx, row in best.iterrows():
                print(f"      {row['symbol']} {row['side']}: ${row['pnl']:.2f} ({row['pnl_percent']:+.2f}%)")
            
            # Top 3 piores
            worst = df_trades.nsmallest(3, 'pnl')[['symbol', 'side', 'pnl', 'pnl_percent']]
            print("\n   📉 TOP 3 PIORES:")
            for idx, row in worst.iterrows():
                print(f"      {row['symbol']} {row['side']}: ${row['pnl']:.2f} ({row['pnl_percent']:+.2f}%)")
                
        except Exception as e:
            print(f"\n⚠️  Não foi possível analisar trades detalhados: {e}")
    
    # 6. Avaliação geral
    print("\n" + "=" * 70)
    print("AVALIAÇÃO")
    print("=" * 70)
    
    score = 0
    max_score = 5
    
    # Critério 1: Lucratividade
    if results['total_pnl_percent'] > 0:
        print("\n✅ Estratégia lucrativa (+1 ponto)")
        score += 1
    else:
        print("\n❌ Estratégia com prejuízo (0 pontos)")
    
    # Critério 2: Win rate
    if results['win_rate'] > 55:
        print("✅ Win rate acima de 55% (+1 ponto)")
        score += 1
    elif results['win_rate'] > 50:
        print("⚠️  Win rate acima de 50% (+0.5 pontos)")
        score += 0.5
    else:
        print("❌ Win rate abaixo de 50% (0 pontos)")
    
    # Critério 3: Profit factor
    if results['profit_factor'] > 1.5:
        print("✅ Profit factor > 1.5 (+1 ponto)")
        score += 1
    elif results['profit_factor'] > 1.0:
        print("⚠️  Profit factor > 1.0 (+0.5 pontos)")
        score += 0.5
    else:
        print("❌ Profit factor < 1.0 (0 pontos)")
    
    # Critério 4: Sharpe ratio
    if results['sharpe_ratio'] > 1.0:
        print("✅ Sharpe ratio > 1.0 (+1 ponto)")
        score += 1
    elif results['sharpe_ratio'] > 0.5:
        print("⚠️  Sharpe ratio > 0.5 (+0.5 pontos)")
        score += 0.5
    else:
        print("❌ Sharpe ratio < 0.5 (0 pontos)")
    
    # Critério 5: Max drawdown
    if results['max_drawdown'] < 15:
        print("✅ Max drawdown < 15% (+1 ponto)")
        score += 1
    elif results['max_drawdown'] < 25:
        print("⚠️  Max drawdown < 25% (+0.5 pontos)")
        score += 0.5
    else:
        print("❌ Max drawdown > 25% (0 pontos)")
    
    print(f"\n📊 PONTUAÇÃO FINAL: {score}/{max_score}")
    
    if score >= 4:
        print("\n🎉 EXCELENTE! Estratégia pronta para testnet")
    elif score >= 3:
        print("\n✅ BOM! Considere ajustes antes do testnet")
    elif score >= 2:
        print("\n⚠️  REGULAR. Precisa de otimização")
    else:
        print("\n❌ RUIM. Revise a estratégia completamente")
    
    print("\n" + "=" * 70)
    
    return True


def main():
    """Executa análise"""
    try:
        success = analyze_backtest()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()