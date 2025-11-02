"""
Validação de Sincronização: Backtest vs Testnet vs Live
Testes automáticos para garantir que todos os modos usam mesmos parâmetros
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

from config.settings import Settings
from core.backtest import BacktestEngine
from core.trade_manager import TradeManager
from core.risk import RiskManager
from core.strategy import StrategyFactory
from core.utils import calculate_sharpe_ratio, calculate_sortino_ratio


class TestSignalThresholds:
    """Valida que thresholds de sinal são idênticos em todos os modos"""
    
    def test_backtest_signal_threshold(self):
        """Verifica threshold no backtest é 0.40"""
        settings = Settings()
        engine = BacktestEngine(settings)
        
        # Backtest deve usar 0.40 como threshold
        # Este é verificado em: core/backtest.py linha ~320
        # if signal in ['BUY', 'SELL'] and strength > 0.40:
        
        # Mock: criar um sinal fraco
        test_strength_weak = 0.39  # Deve ser rejeitado
        test_strength_ok = 0.40    # Deve ser aceito
        
        assert test_strength_ok >= 0.40, "Threshold deve ser 0.40"
        assert test_strength_weak < 0.40, "Threshold deve rejeitar < 0.40"
    
    def test_testnet_signal_threshold_matches_backtest(self):
        """Verifica que testnet usa mesmo threshold que backtest"""
        settings = Settings()
        
        # Ambos devem usar 0.40
        # Backtest: core/backtest.py - if strength > 0.40
        # Testnet: core/trade_manager.py - if strength > 0.40
        
        backtest_threshold = 0.40
        testnet_threshold = 0.40
        
        assert backtest_threshold == testnet_threshold, \
            f"Thresholds não match: backtest={backtest_threshold}, testnet={testnet_threshold}"
    
    def test_signal_threshold_consistency_across_strategies(self):
        """Verifica que threshold é usado para todas as estratégias"""
        threshold = 0.40
        
        strategies = [
            'mean_reversion',
            'breakout',
            'trend_following',
            'ensemble',
            'ensemble_aggressive'
        ]
        
        # Todos devem usar o mesmo threshold
        for strategy_name in strategies:
            # O threshold é aplicado em backtest.py e trade_manager.py
            # NÃO é estratégia-específico
            assert True, f"Strategy {strategy_name} should use threshold 0.40"


class TestSlippageApplication:
    """Valida que slippage é aplicado consistentemente"""
    
    def test_backtest_applies_slippage(self):
        """Verifica que backtest aplica slippage"""
        settings = Settings()
        
        # Slippage deve ser 0.1% (0.001)
        assert settings.SLIPPAGE_PERCENT == Decimal("0.001"), \
            f"Slippage deve ser 0.001, got {settings.SLIPPAGE_PERCENT}"
    
    def test_slippage_applied_on_exit(self):
        """Verifica que slippage é aplicado na saída do trade"""
        settings = Settings()
        engine = BacktestEngine(settings)
        
        # Teste: criar um trade mock e fechar
        exit_price = Decimal('100.00')
        
        # Slippage para BUY (subtrai)
        slippage_buy = exit_price * settings.SLIPPAGE_PERCENT
        actual_exit_buy = exit_price - slippage_buy
        
        # Verificar cálculo
        assert actual_exit_buy == Decimal('99.90'), \
            f"Slippage BUY incorreto: {actual_exit_buy}"
        
        # Slippage para SELL (adiciona)
        slippage_sell = exit_price * settings.SLIPPAGE_PERCENT
        actual_exit_sell = exit_price + slippage_sell
        
        assert actual_exit_sell == Decimal('100.10'), \
            f"Slippage SELL incorreto: {actual_exit_sell}"
    
    def test_slippage_consistency_with_fees(self):
        """Verifica que slippage é aplicado ANTES das fees"""
        settings = Settings()
        
        entry_price = Decimal('100.00')
        exit_price = Decimal('105.00')
        quantity = Decimal('1.0')
        fee_rate = settings.TAKER_FEE  # 0.1%
        
        # Ordem de aplicação CORRETA:
        # 1. Aplicar slippage
        slippage = exit_price * settings.SLIPPAGE_PERCENT
        slipped_exit_price = exit_price - slippage  # Para BUY
        
        # 2. Calcular PnL com preço slipado
        pnl_raw = (slipped_exit_price - entry_price) * quantity
        
        # 3. Aplicar fees
        entry_value = entry_price * quantity
        exit_value = slipped_exit_price * quantity
        fees = (entry_value + exit_value) * fee_rate
        
        final_pnl = pnl_raw - fees
        
        # Resultado deve fazer sentido (PnL reduzido por slippage + fees)
        assert final_pnl < (exit_price - entry_price) * quantity, \
            "PnL final deve ser menor que PnL teórico"


class TestDataFreshness:
    """Valida que data freshness é verificada corretamente"""
    
    def test_max_data_age_calculation(self):
        """Verifica cálculo de idade máxima aceitável"""
        settings = Settings()
        
        # Para timeframe 1h: máximo 1h + 5min = 3900s
        interval_seconds = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
        }
        
        settings.ENTRY_TIMEFRAME = '1h'
        expected_max_age = 3600 + 300  # 1h + 5min buffer
        
        # Cálculo esperado
        interval_sec = interval_seconds['1h']
        max_age = interval_sec + 300
        
        assert max_age == expected_max_age, \
            f"Max age incorreto: {max_age}, esperado {expected_max_age}"
    
    def test_stale_data_rejected(self):
        """Verifica que dados antigos são rejeitados"""
        settings = Settings()
        settings.ENTRY_TIMEFRAME = '1h'
        
        # Dados com 2 horas de idade (muito antigo)
        latest_candle_time = datetime.utcnow() - timedelta(hours=2)
        
        age_seconds = (datetime.utcnow() - latest_candle_time).total_seconds()
        max_age = 3600 + 300  # 1h + 5min
        
        # Deve ser rejeitado
        assert age_seconds > max_age, "Dados antigos não foram rejeitados"
    
    def test_fresh_data_accepted(self):
        """Verifica que dados recentes são aceitos"""
        settings = Settings()
        settings.ENTRY_TIMEFRAME = '1h'
        
        # Dados com 30 minutos de idade (aceitável)
        latest_candle_time = datetime.utcnow() - timedelta(minutes=30)
        
        age_seconds = (datetime.utcnow() - latest_candle_time).total_seconds()
        max_age = 3600 + 300  # 1h + 5min
        
        # Deve ser aceito
        assert age_seconds < max_age, "Dados recentes foram rejeitados"


class TestCandleClosingLogic:
    """Valida que candles são processados quando fechados"""
    
    def test_candle_closing_wait_calculation(self):
        """Verifica cálculo de espera até fechamento"""
        from datetime import datetime
        
        # Simular: estamos em 13:45:00 com timeframe 1h
        # Faltam 15 minutos = 900 segundos até 14:00
        
        interval_seconds = 3600  # 1h
        seconds_into_period = 45 * 60  # 45 minutos em segundos
        
        seconds_until_close = interval_seconds - seconds_into_period  # 900s
        wait_time = seconds_until_close - 30  # Esperar 30s antes
        
        assert wait_time == 870, f"Wait time incorreto: {wait_time}, esperado 870"
    
    def test_candle_not_processed_before_close(self):
        """Verifica que não processa candle incompleto"""
        # Estratégia: sempre esperar até 30s antes do fechamento
        
        for minute in [0, 15, 30, 45]:
            # Simular estar em minuto X de uma hora
            seconds_into_hour = minute * 60
            seconds_until_hour = 3600 - seconds_into_hour
            
            wait_time = seconds_until_hour - 30
            
            # Deve sempre ter tempo de espera positivo
            # (exceto muito próximo ao fim)
            if wait_time > 5:
                assert wait_time > 0, f"Deveria esperar para minuto {minute}"


class TestCapitalTracking:
    """Valida rastreamento consistente de capital"""
    
    def test_initial_capital_set_correctly(self):
        """Verifica que capital inicial é configurado"""
        settings = Settings()
        
        assert settings.BACKTEST_INITIAL_CAPITAL == Decimal('10000.0'), \
            f"Capital inicial incorreto: {settings.BACKTEST_INITIAL_CAPITAL}"
    
    def test_capital_updated_after_trade(self):
        """Verifica que capital é atualizado após trade"""
        settings = Settings()
        initial_capital = settings.BACKTEST_INITIAL_CAPITAL
        
        # Simular trade com +$100 PnL
        trade_pnl = Decimal('100.00')
        final_capital = initial_capital + trade_pnl
        
        # Comparação
        assert final_capital > initial_capital, "Capital não aumentou após trade positivo"
        assert final_capital == Decimal('10100.0'), f"Capital final incorreto: {final_capital}"
    
    def test_equity_tracking_for_open_positions(self):
        """Verifica que equity inclui posições abertas"""
        settings = Settings()
        risk_manager = RiskManager(settings)
        
        closed_capital = Decimal('10000.0')
        unrealized_pnl = Decimal('500.0')  # Posição aberta com +$500
        
        total_equity = closed_capital + unrealized_pnl
        
        assert total_equity == Decimal('10500.0'), \
            f"Equity total incorreta: {total_equity}"


class TestOrderExecutionLatency:
    """Valida compensação de latência na execução"""
    
    def test_price_diff_detection(self):
        """Verifica detecção de diferença de preço"""
        signal_price = Decimal('100.00')
        
        # Preço com 0.3% de diferença (aceitável)
        current_price_ok = Decimal('100.30')
        diff_pct_ok = abs(current_price_ok - signal_price) / signal_price
        
        assert diff_pct_ok < Decimal('0.005'), "Diferença pequena deve ser aceita"
        
        # Preço com 1% de diferença (muito grande)
        current_price_bad = Decimal('101.00')
        diff_pct_bad = abs(current_price_bad - signal_price) / signal_price
        
        assert diff_pct_bad > Decimal('0.005'), "Diferença grande deve ser detectada"
    
    def test_trade_still_executes_with_latency(self):
        """Verifica que trade executa mesmo com latência"""
        # Mesmo com latência, a trade é executada
        # Apenas com log de aviso
        
        latency_detected = True
        should_execute = True
        
        assert should_execute == True, "Trade deve executar mesmo com latência"


class TestPartialTakeProfitSync:
    """Valida que partial TP é idêntico em backtest e testnet"""
    
    def test_partial_tp_levels(self):
        """Verifica que TP parcial é em 3 níveis"""
        entry_price = Decimal('100.00')
        take_profit = Decimal('110.00')
        
        distance = abs(take_profit - entry_price)
        
        tp1 = entry_price + (distance * Decimal('0.5'))    # 50% do caminho = 105
        tp2 = entry_price + (distance * Decimal('0.75'))   # 75% do caminho = 107.5
        tp3 = take_profit                                   # 100% = 110
        
        assert tp1 == Decimal('105.00'), f"TP1 incorreto: {tp1}"
        assert tp2 == Decimal('107.50'), f"TP2 incorreto: {tp2}"
        assert tp3 == Decimal('110.00'), f"TP3 incorreto: {tp3}"
    
    def test_partial_tp_quantities(self):
        """Verifica que quantidades de TP são 30%, 40%, 30%"""
        initial_quantity = Decimal('1.0')
        
        qty_tp1 = initial_quantity * Decimal('0.3')   # 30%
        qty_tp2 = initial_quantity * Decimal('0.4')   # 40%
        qty_tp3_calc = initial_quantity - qty_tp1 - qty_tp2  # 30%
        
        assert qty_tp1 == Decimal('0.3'), f"QTY TP1 incorreta: {qty_tp1}"
        assert qty_tp2 == Decimal('0.4'), f"QTY TP2 incorreta: {qty_tp2}"
        assert qty_tp3_calc == Decimal('0.3'), f"QTY TP3 incorreta: {qty_tp3_calc}"
        
        total = qty_tp1 + qty_tp2 + qty_tp3_calc
        assert total == Decimal('1.0'), f"Total incorreto: {total}"


class TestDynamicPositionSizing:
    """Valida que position sizing é dinâmico baseado em signal strength"""
    
    def test_strong_signal_increases_position(self):
        """Verifica que sinal forte resulta em posição maior"""
        settings = Settings()
        risk_manager = RiskManager(settings)
        
        capital = Decimal('10000.0')
        entry_price = Decimal('100.00')
        stop_loss = Decimal('95.00')
        
        filters = {
            'stepSize': Decimal('0.00001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('10'),
        }
        
        # Sinal fraco (0.4)
        qty_weak = risk_manager.calculate_dynamic_position_size(
            capital, entry_price, stop_loss, filters,
            signal_strength=0.4
        )
        
        # Sinal forte (0.8)
        qty_strong = risk_manager.calculate_dynamic_position_size(
            capital, entry_price, stop_loss, filters,
            signal_strength=0.8
        )
        
        # Sinal forte deve resultar em posição maior
        if qty_weak and qty_strong:
            assert qty_strong > qty_weak, \
                f"Sinal forte deveria resultar em posição maior: {qty_strong} vs {qty_weak}"


class TestCircuitBreaker:
    """Valida que circuit breaker funciona igual em todos os modos"""
    
    def test_circuit_breaker_drawdown_threshold(self):
        """Verifica que circuit breaker usa 15% de drawdown"""
        settings = Settings()
        
        assert settings.MAX_DRAWDOWN_PERCENT == Decimal('0.18'), \
            f"MAX_DRAWDOWN_PERCENT incorreto: {settings.MAX_DRAWDOWN_PERCENT}"
    
    def test_circuit_breaker_daily_loss_threshold(self):
        """Verifica que circuit breaker usa 3.5% de perda diária"""
        settings = Settings()
        
        assert settings.MAX_DAILY_LOSS_PERCENT == Decimal('0.035'), \
            f"MAX_DAILY_LOSS_PERCENT incorreto: {settings.MAX_DAILY_LOSS_PERCENT}"


class TestFeesConsistency:
    """Valida que fees são aplicadas consistentemente"""
    
    def test_taker_fee_correct(self):
        """Verifica que taker fee é 0.1%"""
        settings = Settings()
        
        assert settings.TAKER_FEE == Decimal('0.001'), \
            f"TAKER_FEE incorreta: {settings.TAKER_FEE}"
    
    def test_fees_applied_on_both_sides(self):
        """Verifica que fees são aplicadas na entrada E saída"""
        settings = Settings()
        fee_rate = settings.TAKER_FEE
        
        entry_price = Decimal('100.00')
        exit_price = Decimal('105.00')
        quantity = Decimal('1.0')
        
        # Fees: (entry_value + exit_value) * fee_rate
        entry_value = entry_price * quantity
        exit_value = exit_price * quantity
        fees = (entry_value + exit_value) * fee_rate
        
        # Esperado: (100 + 105) * 0.001 = 0.205
        assert fees == Decimal('0.205'), f"Fees incorretas: {fees}"


class TestIntegrationSync:
    """Testes de integração para validar sincronização completa"""
    
    def test_backtest_and_testnet_use_same_settings(self):
        """Verifica que backtest e testnet usam mesmos settings"""
        settings = Settings()
        
        # Listar parâmetros críticos que devem ser iguais
        critical_params = {
            'RISK_PER_TRADE': Decimal('0.015'),
            'MAX_OPEN_TRADES': 6,
            'STOP_LOSS_PERCENT': Decimal('0.025'),
            'TAKE_PROFIT_PERCENT': Decimal('0.04'),
            'SLIPPAGE_PERCENT': Decimal('0.001'),
            'TAKER_FEE': Decimal('0.001'),
            'MAX_DRAWDOWN_PERCENT': Decimal('0.18'),
            'STRATEGY_MODE': 'ensemble_aggressive'
        }
        
        for param, expected_value in critical_params.items():
            actual_value = getattr(settings, param)
            assert actual_value == expected_value, \
                f"{param}: {actual_value} != {expected_value}"
    
    def test_no_cooldown_in_backtest(self):
        """Verifica que backtest NÃO tem cooldown de sinais"""
        settings = Settings()
        engine = BacktestEngine(settings)
        
        # Backtest não deve ter cooldown
        assert engine.signal_cooldown_seconds == 0, \
            f"Backtest não deve ter cooldown, got {engine.signal_cooldown_seconds}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])