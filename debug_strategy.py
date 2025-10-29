#!/usr/bin/env python3
"""
Debug script - Testa se estratégia gera sinais
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.exchange import BinanceExchange
from core.strategy import StrategyFactory, MultiTimeframeAnalyzer
from config.settings import Settings
from datetime import datetime
import pandas as pd


def test_strategy():
    """Testa estratégia diretamente"""
    
    print("=" * 70)
    print("DEBUG STRATEGY")
    print("=" * 70)
    
    try:
        settings = Settings()
        api_key, api_secret = settings.get_api_credentials(testnet=True)
        exchange = BinanceExchange(api_key, api_secret, testnet=True)
        
        print(f"\n✓ Conectado ao testnet")
        print(f"Strategy: {settings.STRATEGY_MODE}")
        print(f"Primary TF: {settings.PRIMARY_TIMEFRAME}")
        print(f"Entry TF: {settings.ENTRY_TIMEFRAME}")
        
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    # Criar estratégia
    strategy = StrategyFactory.create_strategy(settings.STRATEGY_MODE)
    print(f"✓ Estratégia carregada: {strategy.name}")
    
    # Teste 1: Dados brutos
    print("\n" + "-" * 70)
    print("TESTE 1: Carregar dados brutos")
    print("-" * 70)
    
    try:
        entry_df = exchange.get_klines("BTCUSDT", "5m", limit=500)
        print(f"✓ Carregou {len(entry_df)} candles para BTCUSDT 5m")
        print(f"  Primeiro: {entry_df.index[0]}")
        print(f"  Último:   {entry_df.index[-1]}")
        print(f"\nÚltimo candle:")
        print(entry_df.tail(3))
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return
    
    # Teste 2: Adicionar indicadores
    print("\n" + "-" * 70)
    print("TESTE 2: Adicionar indicadores")
    print("-" * 70)
    
    try:
        df_with_indicators = strategy.add_indicators(entry_df)
        print(f"✓ Indicadores adicionados")
        print(f"\nColunas disponíveis:")
        for col in df_with_indicators.columns:
            print(f"  - {col}")
        
        print(f"\nÚltimos valores de indicadores:")
        indicator_cols = [col for col in df_with_indicators.columns if col not in ['open', 'high', 'low', 'close', 'volume']]
        print(df_with_indicators[indicator_cols].tail(5))
        
    except Exception as e:
        print(f"❌ Erro ao adicionar indicadores: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Teste 3: Gerar sinal
    print("\n" + "-" * 70)
    print("TESTE 3: Gerar sinal")
    print("-" * 70)
    
    try:
        signal, strength = strategy.generate_signal(entry_df)
        print(f"✓ Sinal gerado!")
        print(f"  Signal: {signal}")
        print(f"  Strength: {strength:.4f}")
        
        if strength == 0.0:
            print(f"\n⚠️  STRENGTH é 0! Estratégia não encontrou padrão.")
            print(f"   Isto é o PROBLEMA!")
        
    except Exception as e:
        print(f"❌ Erro ao gerar sinal: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Teste 4: Testar múltiplos pares
    print("\n" + "-" * 70)
    print("TESTE 4: Testar múltiplos pares")
    print("-" * 70)
    
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]
    
    for symbol in symbols:
        try:
            df = exchange.get_klines(symbol, "5m", limit=500)
            signal, strength = strategy.generate_signal(df)
            
            print(f"{symbol:10s} | Signal={signal:5s} | Strength={strength:.4f}")
            
        except Exception as e:
            print(f"{symbol:10s} | ERROR: {str(e)[:40]}")
    
    # Teste 5: Testar com timeframes diferentes
    print("\n" + "-" * 70)
    print("TESTE 5: Testar com timeframes diferentes")
    print("-" * 70)
    
    timeframes = ["1m", "5m", "15m", "1h", "4h"]
    symbol = "BTCUSDT"
    
    for tf in timeframes:
        try:
            df = exchange.get_klines(symbol, tf, limit=500)
            signal, strength = strategy.generate_signal(df)
            
            print(f"{tf:5s} | Candles={len(df):3d} | Signal={signal:5s} | Strength={strength:.4f}")
            
        except Exception as e:
            print(f"{tf:5s} | ERROR: {str(e)[:40]}")
    
    # Teste 6: Multi-timeframe
    print("\n" + "-" * 70)
    print("TESTE 6: Multi-timeframe Analysis")
    print("-" * 70)
    
    try:
        primary_df = exchange.get_klines("BTCUSDT", "4h", limit=500)
        entry_df = exchange.get_klines("BTCUSDT", "1h", limit=500)
        
        mtf_analyzer = MultiTimeframeAnalyzer(
            primary_timeframe="4h",
            entry_timeframe="1h",
            strategy=strategy,
            require_alignment=settings.REQUIRE_MTF_ALIGNMENT
        )
        
        signal, strength, metadata = mtf_analyzer.analyze(primary_df, entry_df)
        
        print(f"✓ Multi-timeframe analysis:")
        print(f"  Final Signal: {signal}")
        print(f"  Final Strength: {strength:.4f}")
        print(f"  Metadata: {metadata}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("FIM DO DEBUG")
    print("=" * 70)


if __name__ == "__main__":
    test_strategy()